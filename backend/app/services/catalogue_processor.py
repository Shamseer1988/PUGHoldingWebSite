"""Render a Catalogue's PDF into WebP page images.

Uses PyMuPDF (``fitz``) to rasterise each PDF page at two resolutions:

  * Full-size: ~1600 px wide WebP, the canvas the viewer paints
    when the user is reading a page.
  * Thumbnail: ~280 px wide WebP, used in the page-strip + as the
    catalogue cover image.

Output files live under
``{settings.upload_dir}/catalogues/{catalogue_id}/`` and are
content-addressed via the catalogue id + page number — re-processing
overwrites in place, no orphans.

Processing runs **synchronously** inside the admin upload request.
For small flyers (under 30 pages) that completes in 5–15 seconds on
a modest server, which is acceptable for an admin operation. A
``processing_status`` column on the Catalogue row keeps the admin UI
informed when a process is mid-flight after a server restart.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.marketing import (
    CATALOGUE_FAILED,
    CATALOGUE_PROCESSING,
    CATALOGUE_READY,
    Catalogue,
    CataloguePage,
)


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


def storage_dir_for(catalogue_id: int) -> Path:
    """Return (and create) the on-disk directory for a catalogue's
    rendered pages. Lives under ``{upload_dir}/catalogues/<id>/``."""
    settings = get_settings()
    target = Path(settings.upload_dir) / "catalogues" / str(catalogue_id)
    target.mkdir(parents=True, exist_ok=True)
    return target


def public_url(relative_path: str) -> str:
    """Build the public URL for a file under the uploads mount."""
    return f"/api/v1/uploads/{relative_path.lstrip('/')}"


def process_catalogue(
    db: Session, catalogue: Catalogue, pdf_bytes: bytes
) -> ProcessResult:
    """Render ``pdf_bytes`` into WebP pages + thumbnails and persist
    one ``CataloguePage`` row per page.

    Called by the admin upload endpoint and by the "re-process"
    button. Side effects:

      * Wipes the catalogue's on-disk directory and the existing
        ``CataloguePage`` rows so re-runs don't leak old assets.
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

    storage = storage_dir_for(catalogue.id)
    # Wipe stale renders from a prior run so old pages don't linger
    # if the new PDF has fewer pages.
    if storage.exists():
        for f in storage.iterdir():
            if f.is_file() and (
                f.suffix.lower() == ".webp"
                or f.name.endswith(".pdf")
                or f.name.endswith(".thumb.webp")
            ):
                try:
                    f.unlink()
                except OSError:
                    pass

    # Drop old CataloguePage rows for this catalogue — the cascade
    # would handle file refs but the rows themselves are what the
    # viewer reads.
    for page in list(catalogue.pages):
        db.delete(page)
    db.flush()

    # Save the original PDF so customers can download it. The
    # admin-upload endpoint already wrote it once when receiving the
    # request, but we re-write here so process_catalogue is the
    # single source of truth for the on-disk layout.
    pdf_path = storage / "source.pdf"
    pdf_path.write_bytes(pdf_bytes)
    catalogue.file_size_bytes = len(pdf_bytes)
    catalogue.pdf_url = public_url(f"catalogues/{catalogue.id}/source.pdf")

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
            full_name = f"page_{page_number:03d}.webp"
            thumb_name = f"page_{page_number:03d}.thumb.webp"
            (storage / full_name).write_bytes(full_bytes)
            (storage / thumb_name).write_bytes(thumb_bytes)
            bytes_written += full_size + thumb_size

            image_url = public_url(f"catalogues/{catalogue.id}/{full_name}")
            thumb_url = public_url(f"catalogues/{catalogue.id}/{thumb_name}")

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


def delete_catalogue_files(catalogue_id: int) -> None:
    """Remove every rendered file for a catalogue. Called from the
    catalogue-delete endpoint so we don't leak disk space."""
    settings = get_settings()
    target = Path(settings.upload_dir) / "catalogues" / str(catalogue_id)
    if target.exists():
        try:
            shutil.rmtree(target)
        except OSError as exc:
            logger.warning(
                "Could not clean catalogue dir %s: %s", target, exc
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
    "delete_catalogue_files",
    "process_catalogue",
    "public_url",
    "storage_dir_for",
]
