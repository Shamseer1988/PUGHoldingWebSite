"""One-shot: migrate locally-stored CV files to the storage backend.

Pre-R2 the apply / HR upload flow wrote CV files directly to
``{upload_dir}/cvs/<hash>.<ext>`` and stored the public URL
``/api/v1/uploads/cvs/<hash>.<ext>`` on
``CandidateDocument.file_path``. The R2 refactor (preceding commit)
moves the WRITE path through ``get_storage().upload_sync(...)`` at
``career/cv/<hash>.<ext>``, but legacy rows still point at the local
URL and the bytes never reached the bucket.

This walks every ``CandidateDocument``, reads each legacy file off
disk, uploads it to R2 at the new key, and rewrites
``file_path`` to the storage key form. Idempotent — rows whose
``file_path`` already starts with ``career/cv/`` are skipped.

Run on the EC2 host once after deploying the storage refactor:

    # Preview — no changes
    docker compose -f docker-compose.prod.yml exec backend \\
        python -m app.scripts.migrate_cvs_to_r2

    # Apply: uploads + rewrites file_path, leaves local files alone
    docker compose -f docker-compose.prod.yml exec backend \\
        python -m app.scripts.migrate_cvs_to_r2 --apply

    # Apply + delete local file after each successful upload
    docker compose -f docker-compose.prod.yml exec backend \\
        python -m app.scripts.migrate_cvs_to_r2 --apply --purge

Defaults are non-destructive (``--dry-run`` is implicit). Per-row
failures don't abort the run — each row's outcome is counted in the
trailing summary and the exit code is non-zero only on real errors
(``missing`` files are reported but considered legitimate operator
workflow — those rows need a fresh upload via the admin UI).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.hr_ats import CandidateDocument
from app.services.cv_storage import CV_KEY_PREFIX
from app.services.storage import get_storage


logger = logging.getLogger("migrate_cvs_to_r2")


# CV content-type lookup so the edge serves a correct ``Content-Type``
# header when the browser fetches the pre-signed URL. Mirrors the
# allowlist in cv_storage.py — kept in sync deliberately so a future
# format addition has one place to update.
_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def _is_already_migrated(file_path: str) -> bool:
    """True when ``file_path`` is already in the modern storage-key form."""
    return (file_path or "").startswith(CV_KEY_PREFIX + "/")


def _basename(file_path: str) -> str:
    """Pull the bare ``<hash>.<ext>`` filename out of any historical
    layout the column might hold. Tolerates leading slashes, the
    legacy mount prefix, or the bare ``cvs/`` form some test
    fixtures dropped to disk before the StaticFiles mount existed."""
    s = (file_path or "").strip()
    legacy = "/api/v1/uploads/cvs/"
    if s.startswith(legacy):
        return s[len(legacy):]
    if s.startswith("cvs/"):
        return s[len("cvs/"):]
    # Last resort: take whatever's after the final ``/`` (or the
    # whole string if no slash).
    return Path(s).name


def _migrate_one(
    db: Session,
    doc: CandidateDocument,
    upload_root: Path,
    *,
    apply: bool,
    purge: bool,
) -> str:
    """Migrate one CV row. Returns ``migrated`` / ``skipped`` /
    ``missing`` / ``error``."""
    if _is_already_migrated(doc.file_path):
        return "skipped"

    basename = _basename(doc.file_path)
    if not basename:
        logger.warning(
            "document %s: empty file_path — leaving row alone", doc.id
        )
        return "missing"

    # Legacy on-disk location was always ``{upload_dir}/cvs/<basename>``.
    local_path = upload_root / "cvs" / basename
    if not local_path.exists():
        logger.warning(
            "document %s (candidate %s): local CV missing at %s — "
            "re-upload via the admin UI",
            doc.id,
            doc.candidate_id,
            local_path,
        )
        return "missing"

    ext = Path(basename).suffix.lstrip(".").lower()
    new_key = f"{CV_KEY_PREFIX}/{basename}"
    content_type = doc.mime_type or _CONTENT_TYPES.get(ext, "application/octet-stream")

    if not apply:
        logger.info(
            "document %s [dry-run]: would upload %s (%s bytes) → %s",
            doc.id,
            local_path,
            local_path.stat().st_size,
            new_key,
        )
        return "migrated"

    try:
        get_storage().upload_sync(new_key, local_path.read_bytes(), content_type)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "document %s: upload to storage failed: %s", doc.id, exc
        )
        return "error"

    doc.file_path = new_key
    db.commit()
    logger.info(
        "document %s (candidate %s): migrated → %s",
        doc.id,
        doc.candidate_id,
        new_key,
    )

    if purge:
        try:
            local_path.unlink()
        except OSError as exc:
            # Don't fail the migration on a cleanup hiccup — the row
            # is already on R2; the operator can sweep the old
            # directory by hand.
            logger.warning(
                "document %s: uploaded OK but local file unlink failed: %s",
                doc.id,
                exc,
            )

    return "migrated"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move pre-R2 candidate CV files into the storage backend."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Actually upload + rewrite ``file_path``. Without this flag "
            "the script runs in dry-run mode and only prints what would happen."
        ),
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help=(
            "After a successful per-row upload, delete the legacy local "
            "file. Only honoured together with --apply. The DB row is "
            "rewritten before the file is unlinked, so even an unclean "
            "interrupt won't leave the row pointing at a vanished file."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
    )

    settings = get_settings()
    upload_root = Path(settings.upload_dir).resolve()
    if not upload_root.exists():
        # Not fatal — an install that's already migrated + purged
        # legitimately has no ``upload_dir`` left. We still walk the
        # DB; every row will report ``missing`` and the operator
        # knows the cleanup is done.
        logger.warning(
            "upload_dir %s does not exist — every row will report missing",
            upload_root,
        )

    purge = bool(args.purge and args.apply)
    if args.purge and not args.apply:
        logger.warning("--purge ignored without --apply (dry-run mode)")

    stats = {
        "migrated": 0,
        "skipped": 0,
        "missing": 0,
        "error": 0,
    }

    db = SessionLocal()
    try:
        docs = (
            db.execute(select(CandidateDocument).order_by(CandidateDocument.id))
            .scalars()
            .all()
        )
        logger.info(
            "found %s CandidateDocument rows; upload_root=%s apply=%s purge=%s",
            len(docs),
            upload_root,
            args.apply,
            purge,
        )
        for doc in docs:
            outcome = _migrate_one(
                db, doc, upload_root, apply=args.apply, purge=purge
            )
            stats[outcome] += 1
    finally:
        db.close()

    logger.info("migration summary: %s", stats)
    return 1 if stats["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
