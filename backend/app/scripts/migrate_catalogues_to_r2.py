"""One-shot: migrate locally stored catalogue + QR-logo files to R2.

Pre-R2, the catalogue processor wrote rendered WebP pages, source
PDFs and per-catalogue QR brand logos directly to the local upload
directory and hardcoded ``/api/v1/uploads/...`` URLs on the DB rows.
After the R2 storage migration those rows still carry the old URLs
but the bytes are inside the backend container's ``uploads_data``
Docker volume, not the R2 bucket — so the public viewer + admin
preview render as broken images.

This script walks every Catalogue row, finds the matching files on
disk, uploads them to the storage backend (R2 in production), and
rewrites the row + page URLs to whatever public URL the backend
returns. Same job for per-catalogue QR brand logos.

Run on the EC2 host once after deploying PR #24::

    docker compose -f docker-compose.prod.yml exec backend \\
        python -m app.scripts.migrate_catalogues_to_r2

Idempotent:
  * Rows whose URLs are already non-local (start with ``http``) are
    skipped — re-running won't re-upload anything.
  * Pages whose WebP file is missing on disk are logged as
    ``missing`` and the row is left untouched; the admin can
    re-upload that single catalogue from the UI.
  * Failures on individual catalogues don't abort the run — each is
    counted in the trailing summary.

Pass ``--dry-run`` to print what would happen without touching
storage or the database.
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
from app.models.marketing import Catalogue, CataloguePage
from app.services.catalogue_processor import (
    page_image_key,
    page_thumbnail_key,
    source_pdf_key,
)
from app.services.storage import get_storage


logger = logging.getLogger("migrate_catalogues_to_r2")


# A URL we wrote pre-R2 always starts with ``/api/v1/uploads/`` (the
# local FastAPI StaticFiles mount). Anything that already has an
# ``http`` scheme is either an R2 custom domain or the raw
# ``<account>.r2.cloudflarestorage.com`` form — both mean "already
# migrated, skip".
def _is_local_url(url: Optional[str]) -> bool:
    return bool(url) and url.startswith("/")


# QR-logo content-type lookup so the edge serves a correct
# ``Content-Type`` header (mirrors the upload endpoint).
_QR_LOGO_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


def _migrate_catalogue(
    db: Session, catalogue: Catalogue, upload_root: Path, *, dry_run: bool
) -> str:
    """Migrate one Catalogue's source PDF + every rendered page.

    Returns one of: ``"migrated"``, ``"skipped"``, ``"missing"``,
    ``"error"``.
    """
    if not _is_local_url(catalogue.pdf_url):
        return "skipped"

    cat_dir = upload_root / "catalogues" / str(catalogue.id)
    pdf_path = cat_dir / "source.pdf"
    if not pdf_path.exists():
        logger.warning(
            "catalogue %s: source.pdf missing at %s — re-upload via UI",
            catalogue.id,
            pdf_path,
        )
        return "missing"

    storage = get_storage()

    if dry_run:
        page_files = sorted(cat_dir.glob("page_*.webp"))
        logger.info(
            "catalogue %s [dry-run]: would upload source.pdf (%s bytes) + %s page files",
            catalogue.id,
            pdf_path.stat().st_size,
            len(page_files),
        )
        return "migrated"

    # Source PDF.
    try:
        pdf_bytes = pdf_path.read_bytes()
        new_pdf_url = storage.upload_sync(
            source_pdf_key(catalogue.id), pdf_bytes, "application/pdf"
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "catalogue %s: failed to upload source.pdf: %s", catalogue.id, exc
        )
        return "error"

    catalogue.pdf_url = new_pdf_url
    catalogue.file_size_bytes = len(pdf_bytes)

    # Walk the existing CataloguePage rows and upload each page +
    # thumbnail under the same deterministic keys the processor
    # writes new uploads to. Rewrite the row URLs to whatever the
    # backend returns.
    pages = (
        db.execute(
            select(CataloguePage)
            .where(CataloguePage.catalogue_id == catalogue.id)
            .order_by(CataloguePage.page_number.asc())
        )
        .scalars()
        .all()
    )

    cover_thumb_url: Optional[str] = None
    for page in pages:
        page_file = cat_dir / f"page_{page.page_number:03d}.webp"
        thumb_file = cat_dir / f"page_{page.page_number:03d}.thumb.webp"
        if not page_file.exists() or not thumb_file.exists():
            logger.warning(
                "catalogue %s page %s: webp file missing at %s — leaving row alone",
                catalogue.id,
                page.page_number,
                page_file,
            )
            continue
        try:
            page.image_url = storage.upload_sync(
                page_image_key(catalogue.id, page.page_number),
                page_file.read_bytes(),
                "image/webp",
            )
            page.thumbnail_url = storage.upload_sync(
                page_thumbnail_key(catalogue.id, page.page_number),
                thumb_file.read_bytes(),
                "image/webp",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "catalogue %s page %s: upload failed: %s",
                catalogue.id,
                page.page_number,
                exc,
            )
            return "error"
        if page.page_number == 1:
            cover_thumb_url = page.thumbnail_url

    if cover_thumb_url is not None:
        catalogue.cover_image_url = cover_thumb_url

    db.commit()
    logger.info(
        "catalogue %s (%s): %s pages migrated",
        catalogue.id,
        catalogue.slug,
        len(pages),
    )
    return "migrated"


def _migrate_qr_logo(
    db: Session, catalogue: Catalogue, upload_root: Path, *, dry_run: bool
) -> str:
    """Migrate one Catalogue's QR brand logo if it's still local.

    Returns ``"migrated"``, ``"skipped"``, ``"missing"`` or ``"error"``.
    """
    if not _is_local_url(catalogue.qr_logo_url):
        return "skipped"

    # The URL was written as ``/api/v1/uploads/qr-logos/{id}{ext}``.
    # Recover the extension off the URL itself rather than scanning
    # the directory so we know exactly which file the row pointed at.
    ext = Path(catalogue.qr_logo_url).suffix.lower()
    if ext not in _QR_LOGO_CONTENT_TYPES:
        logger.warning(
            "catalogue %s qr_logo_url has unknown extension %r — skipping",
            catalogue.id,
            ext,
        )
        return "missing"

    logo_path = upload_root / "qr-logos" / f"{catalogue.id}{ext}"
    if not logo_path.exists():
        logger.warning(
            "catalogue %s: qr logo missing at %s — re-upload via UI",
            catalogue.id,
            logo_path,
        )
        return "missing"

    if dry_run:
        logger.info(
            "catalogue %s [dry-run]: would upload qr logo (%s bytes)",
            catalogue.id,
            logo_path.stat().st_size,
        )
        return "migrated"

    try:
        new_url = get_storage().upload_sync(
            f"qr-logos/{catalogue.id}{ext}",
            logo_path.read_bytes(),
            _QR_LOGO_CONTENT_TYPES[ext],
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "catalogue %s: qr logo upload failed: %s", catalogue.id, exc
        )
        return "error"

    catalogue.qr_logo_url = new_url
    db.commit()
    logger.info("catalogue %s: qr logo migrated", catalogue.id)
    return "migrated"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move pre-R2 catalogue + QR-logo files into the storage backend."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without touching storage or the database.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
    )

    settings = get_settings()
    upload_root = Path(settings.upload_dir).resolve()
    if not upload_root.exists():
        logger.error("upload_dir %s does not exist — nothing to migrate", upload_root)
        return 1

    stats = {
        "catalogues_migrated": 0,
        "catalogues_skipped": 0,
        "catalogues_missing": 0,
        "catalogues_error": 0,
        "qr_logos_migrated": 0,
        "qr_logos_skipped": 0,
        "qr_logos_missing": 0,
        "qr_logos_error": 0,
    }

    db = SessionLocal()
    try:
        catalogues = (
            db.execute(select(Catalogue).order_by(Catalogue.id.asc()))
            .scalars()
            .all()
        )
        logger.info(
            "found %s catalogues; upload root %s; dry-run=%s",
            len(catalogues),
            upload_root,
            args.dry_run,
        )

        for catalogue in catalogues:
            outcome = _migrate_catalogue(
                db, catalogue, upload_root, dry_run=args.dry_run
            )
            stats[f"catalogues_{outcome}"] += 1

            qr_outcome = _migrate_qr_logo(
                db, catalogue, upload_root, dry_run=args.dry_run
            )
            stats[f"qr_logos_{qr_outcome}"] += 1
    finally:
        db.close()

    logger.info("migration summary: %s", stats)
    # Exit non-zero if anything errored so a CI / cron caller knows
    # something needs investigation. "missing" doesn't count — that's
    # legitimate operator workflow (admin re-uploads the affected row).
    return 1 if stats["catalogues_error"] or stats["qr_logos_error"] else 0


if __name__ == "__main__":
    sys.exit(main())
