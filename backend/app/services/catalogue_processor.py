"""Render a Catalogue's PDF into WebP page images.

Uses PyMuPDF (``fitz``) to rasterise each PDF page at two resolutions:

  * Full-size: ~1600 px wide WebP, the canvas the viewer paints
    when the user is reading a page.
  * Thumbnail: ~280 px wide WebP, used in the page-strip + as the
    catalogue cover image.

Storage layout — both the source PDF and the rendered pages are
pushed through the pluggable :mod:`app.services.storage` backend
under deterministic keys:

  ``catalogues/{catalogue_id}/source.pdf``
  ``catalogues/{catalogue_id}/page_{N:03d}.webp``
  ``catalogues/{catalogue_id}/page_{N:03d}.thumb.webp``

The backend (R2 or local disk) decides how that key resolves to a
public URL; the URL it returns is what we persist on the Catalogue
and CataloguePage rows.

Processing runs **synchronously** inside the admin upload request.
For small flyers (under 30 pages) that completes in 5–15 seconds on
a modest server, which is acceptable for an admin operation. A
``processing_status`` column on the Catalogue row keeps the admin UI
informed when a process is mid-flight after a server restart.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from PIL import Image
from sqlalchemy.orm import Session

from app.models.marketing import (
    CATALOGUE_FAILED,
    CATALOGUE_PROCESSING,
    CATALOGUE_READY,
    Catalogue,
    CataloguePage,
)
from app.services.storage import get_storage


logger = logging.getLogger(__name__)


# Render budgets — tuned for a typical hypermarket flyer (A4, mostly
# product photography). Bigger = sharper but heavier; this matches
# Calaméo's per-page payload roughly.
FULL_WIDTH_PX = 1600
THUMB_WIDTH_PX = 280
WEBP_QUALITY_FULL = 80
WEBP_QUALITY_THUMB = 70


class CatalogueProcessingError(RuntimeError):
    """Raised when a catalogue PDF can't be rendered. The Catalogue row's
    ``processing_status`` is flipped to ``failed`` and the underlying
    error message is stored on ``processing_error`` for admin display."""


@dataclass(slots=True)
class ProcessResult:
    page_count: int
    cover_image_url: Optional[str]
    bytes_written: int


# ---------------------------------------------------------------------------
# Key helpers — public so the admin endpoints can build the same keys when
# they need to fetch / delete an asset without going through the processor.
# ---------------------------------------------------------------------------


def source_pdf_key(catalogue_id: int) -> str:
    return f"catalogues/{catalogue_id}/source.pdf"


def page_image_key(catalogue_id: int, page_number: int) -> str:
    return f"catalogues/{catalogue_id}/page_{page_number:03d}.webp"


def page_thumbnail_key(catalogue_id: int, page_number: int) -> str:
    return f"catalogues/{catalogue_id}/page_{page_number:03d}.thumb.webp"


def process_catalogue(
    db: Session, catalogue: Catalogue, pdf_bytes: bytes
) -> ProcessResult:
    """Render ``pdf_bytes`` into WebP pages + thumbnails and persist
    one ``CataloguePage`` row per page.

    Called by the admin upload endpoint and by the "re-process"
    button. Side effects:

      * Drops the existing ``CataloguePage`` rows so re-runs don't
        leak stale viewer entries.
      * Pushes the source PDF + every page + every thumbnail to the
        configured storage backend. Public URLs returned by the
        backend are what land on the DB rows — works transparently
        against either local disk or Cloudflare R2.
      * Sets ``processing_status`` to ``processing`` for the duration,
        then ``ready`` (or ``failed`` with ``processing_error``).
      * Stamps ``processed_at`` + ``page_count`` + ``cover_image_url``
        on the catalogue row.

    Returns a ProcessResult; on failure raises
    :class:`CatalogueProcessingError` after the row has been marked
    failed (caller does not need to clean up).
    """
    if not pdf_bytes:
        catalogue.processing_status = CATALOGUE_FAILED
        catalogue.processing_error = "Uploaded PDF is empty."
        db.flush()
        raise CatalogueProcessingError(catalogue.processing_error)

    # Lazy-import PyMuPDF so the rest of the codebase imports cleanly
    # in environments where the package isn't installed (e.g. a slim
    # test container).
    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover
        catalogue.processing_status = CATALOGUE_FAILED
        catalogue.processing_error = (
            "PyMuPDF is not installed on the server. "
            "Run `pip install -r requirements.txt`."
        )
        db.flush()
        raise CatalogueProcessingError(catalogue.processing_error) from exc

    catalogue.processing_status = CATALOGUE_PROCESSING
    catalogue.processing_error = None
    db.flush()

    storage = get_storage()

    # Drop old CataloguePage rows for this catalogue. The processor
    # writes deterministic keys, so an upload's renders overwrite the
    # previous run's bytes in storage — no orphan-cleanup pass needed
    # for the new pages. Pages that no longer exist (PDF shrank) are
    # rare enough that we accept the orphan rather than running a
    # prefix-list across R2 on every re-render.
    for page in list(catalogue.pages):
        db.delete(page)
    db.flush()

    # Push the source PDF first so the reprocess endpoint can read it
    # back from the same place the public viewer downloads it from.
    try:
        pdf_url = storage.upload_sync(
            source_pdf_key(catalogue.id), pdf_bytes, "application/pdf"
        )
    except Exception as exc:  # noqa: BLE001
        catalogue.processing_status = CATALOGUE_FAILED
        catalogue.processing_error = f"Failed to upload source PDF: {exc}"
        db.flush()
        raise CatalogueProcessingError(catalogue.processing_error) from exc

    catalogue.file_size_bytes = len(pdf_bytes)
    catalogue.pdf_url = pdf_url

    bytes_written = len(pdf_bytes)
    cover_image_url: Optional[str] = None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        catalogue.processing_status = CATALOGUE_FAILED
        catalogue.processing_error = f"Could not open PDF: {exc}"
        db.flush()
        raise CatalogueProcessingError(catalogue.processing_error) from exc

    # Cache page_count BEFORE the finally block — PyMuPDF raises
    # ValueError("document closed") if accessed after .close().
    total_pages = doc.page_count
    try:
        for page_index in range(total_pages):
            page = doc.load_page(page_index)
            # PyMuPDF page.rect is in points (1pt = 1/72 inch).
            pdf_w = max(page.rect.width, 1.0)
            scale_full = FULL_WIDTH_PX / pdf_w
            scale_thumb = THUMB_WIDTH_PX / pdf_w

            # Full-size render
            full_pix = page.get_pixmap(
                matrix=fitz.Matrix(scale_full, scale_full),
                alpha=False,
            )
            full_bytes, full_size = _encode_webp(
                full_pix.samples,
                full_pix.width,
                full_pix.height,
                quality=WEBP_QUALITY_FULL,
            )

            # Thumbnail
            thumb_pix = page.get_pixmap(
                matrix=fitz.Matrix(scale_thumb, scale_thumb),
                alpha=False,
            )
            thumb_bytes, thumb_size = _encode_webp(
                thumb_pix.samples,
                thumb_pix.width,
                thumb_pix.height,
                quality=WEBP_QUALITY_THUMB,
            )

            page_number = page_index + 1
            image_url = storage.upload_sync(
                page_image_key(catalogue.id, page_number),
                full_bytes,
                "image/webp",
            )
            thumb_url = storage.upload_sync(
                page_thumbnail_key(catalogue.id, page_number),
                thumb_bytes,
                "image/webp",
            )
            bytes_written += full_size + thumb_size

            db.add(
                CataloguePage(
                    catalogue_id=catalogue.id,
                    page_number=page_number,
                    image_url=image_url,
                    thumbnail_url=thumb_url,
                    width=full_pix.width,
                    height=full_pix.height,
                    file_size_bytes=full_size,
                )
            )
            if page_number == 1:
                cover_image_url = thumb_url
    except Exception as exc:  # noqa: BLE001
        catalogue.processing_status = CATALOGUE_FAILED
        catalogue.processing_error = (
            f"Failed while rendering page {page_index + 1}: {exc}"
        )
        db.flush()
        raise CatalogueProcessingError(catalogue.processing_error) from exc
    finally:
        try:
            doc.close()
        except Exception:  # noqa: BLE001
            pass

    page_count = total_pages
    catalogue.page_count = page_count
    catalogue.cover_image_url = cover_image_url
    catalogue.processing_status = CATALOGUE_READY
    catalogue.processing_error = None
    catalogue.processed_at = datetime.now(timezone.utc)
    db.flush()

    return ProcessResult(
        page_count=page_count,
        cover_image_url=cover_image_url,
        bytes_written=bytes_written,
    )


def delete_catalogue_assets(catalogue_id: int, page_count: int) -> None:
    """Best-effort cleanup of every asset a catalogue uploaded.

    Called from the catalogue-delete endpoint AFTER the DB row + page
    rows have been removed. Walks the deterministic keys
    :func:`source_pdf_key` / :func:`page_image_key` /
    :func:`page_thumbnail_key` and deletes each — works against R2
    without needing a prefix-list call, and against local disk by
    just unlinking the files. Errors are logged + swallowed so a
    transient storage failure doesn't poison the user-facing delete.
    """
    storage = get_storage()
    keys = [source_pdf_key(catalogue_id)]
    for n in range(1, page_count + 1):
        keys.append(page_image_key(catalogue_id, n))
        keys.append(page_thumbnail_key(catalogue_id, n))
    for key in keys:
        try:
            storage.delete_sync(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to delete catalogue asset %s: %s", key, exc
            )


def _encode_webp(
    raw_rgb: bytes, width: int, height: int, *, quality: int
) -> tuple[bytes, int]:
    """Build a WebP from a Pixmap's raw RGB samples. Returns (bytes,
    byte_length)."""
    img = Image.frombytes("RGB", (width, height), raw_rgb)
    out = BytesIO()
    img.save(out, format="WEBP", quality=quality, method=4)
    data = out.getvalue()
    return data, len(data)


__all__ = [
    "CatalogueProcessingError",
    "FULL_WIDTH_PX",
    "ProcessResult",
    "THUMB_WIDTH_PX",
    "WEBP_QUALITY_FULL",
    "WEBP_QUALITY_THUMB",
    "delete_catalogue_assets",
    "page_image_key",
    "page_thumbnail_key",
    "process_catalogue",
    "source_pdf_key",
]
