"""One-shot script: generate WebP/JPEG variants for every existing
``cms_media_assets`` row whose ``variants`` is still NULL.

Run after deploying the image-optimization pipeline so pre-existing
uploads also benefit from the new responsive variants::

    cd /home/parisgroup/PugWebSite/backend
    .venv/bin/python -m app.scripts.backfill_image_variants

Idempotent — re-runs skip rows that already have variants and rows
whose source file is missing from disk. Videos and non-image kinds
are always skipped.

Prints a one-line per row so you can spot failures. Returns exit
code 0 on completion regardless of per-row errors; the missing /
failed rows are listed in the trailing summary.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.cms import MEDIA_KIND_IMAGE, MediaAsset
from app.services.image_optimization import optimize_image


logger = logging.getLogger("backfill_image_variants")


def _resolve_source(asset: MediaAsset, upload_root: Path) -> Path | None:
    """Locate the on-disk file backing this row.

    ``MediaAsset.url`` is of the form ``/api/v1/uploads/cms/<file>``
    — strip the URL prefix and join under the upload root.
    """
    if not asset.url:
        return None
    url = asset.url
    prefix = "/api/v1/uploads/"
    if not url.startswith(prefix):
        return None
    relative = url[len(prefix):]
    candidate = upload_root / relative
    return candidate if candidate.exists() else None


def main() -> int:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        level=logging.INFO,
    )
    settings = get_settings()
    upload_root = Path(settings.upload_dir).resolve()

    stats = {"processed": 0, "skipped": 0, "missing": 0, "errors": 0}

    with SessionLocal() as db:
        rows = (
            db.execute(
                select(MediaAsset)
                .where(MediaAsset.kind == MEDIA_KIND_IMAGE)
                .where(MediaAsset.variants.is_(None))
                .order_by(MediaAsset.id)
            )
            .scalars()
            .all()
        )
        logger.info(
            "found %d image assets without variants (upload_root=%s)",
            len(rows),
            upload_root,
        )

        for asset in rows:
            source = _resolve_source(asset, upload_root)
            if source is None:
                logger.warning(
                    "id=%d missing on disk (url=%s)", asset.id, asset.url
                )
                stats["missing"] += 1
                continue

            try:
                variant_set = optimize_image(
                    source,
                    public_base_url="/api/v1/uploads/cms",
                    mime_type=asset.mime_type,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("id=%d failed: %s", asset.id, exc)
                stats["errors"] += 1
                continue

            if variant_set is None:
                logger.info("id=%d skipped (unsupported/decoder-skip)", asset.id)
                stats["skipped"] += 1
                continue

            asset.variants = variant_set.as_dict()
            db.flush()
            stats["processed"] += 1
            logger.info("id=%d ✓", asset.id)

        db.commit()

    logger.info(
        "done — processed=%(processed)d skipped=%(skipped)d "
        "missing=%(missing)d errors=%(errors)d",
        stats,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
