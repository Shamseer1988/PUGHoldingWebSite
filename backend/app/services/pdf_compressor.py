"""PDF compression — rasterise each page to JPEG and rebuild a tiny PDF.

Used by the admin "PDF Compressor" tool to shrink hypermarket flyers
to under the 50 MB catalogue-upload cap (and into the kilobyte range
for fast public delivery). Designed for image-heavy PDFs — the
output discards any selectable text layer because hypermarket
flyers don't have one to begin with.

How it works:

  1. Open the source PDF with PyMuPDF.
  2. For each page, render it to a Pixmap at the chosen DPI.
  3. Re-encode the Pixmap to JPEG via Pillow with a chosen quality
     + progressive encoding for fast first-byte rendering.
  4. Insert the JPEG into a fresh PDF page at the original page
     dimensions.
  5. ``save(garbage=4, deflate=True, clean=True)`` strips orphaned
     objects and recompresses every stream.

Two knobs control the size/quality tradeoff:

  * ``target_dpi``    — rasterisation resolution. 72 DPI is the
                        natural PDF unit; rendering above that
                        upsamples but doesn't add detail.
  * ``jpeg_quality``  — Pillow JPEG quality, 1-95. 85 is the sweet
                        spot for product photography.

Three named presets matching the admin UI radio buttons:

  HIGH        180 DPI, q=92   — print-ready, modest savings
  BALANCED    120 DPI, q=85   — recommended for screen viewing
  AGGRESSIVE  100 DPI, q=75   — for very large originals
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO

from PIL import Image


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompressionPreset:
    name: str
    target_dpi: int
    jpeg_quality: int


PRESET_HIGH = CompressionPreset("high", target_dpi=180, jpeg_quality=92)
PRESET_BALANCED = CompressionPreset("balanced", target_dpi=120, jpeg_quality=85)
PRESET_AGGRESSIVE = CompressionPreset("aggressive", target_dpi=100, jpeg_quality=75)
PRESETS = {
    "high": PRESET_HIGH,
    "balanced": PRESET_BALANCED,
    "aggressive": PRESET_AGGRESSIVE,
}


@dataclass(slots=True)
class CompressionResult:
    page_count: int
    original_size_bytes: int
    compressed_size_bytes: int
    preset_name: str

    @property
    def reduction_ratio(self) -> float:
        if not self.original_size_bytes:
            return 0.0
        return 1.0 - (self.compressed_size_bytes / self.original_size_bytes)


class PdfCompressionError(RuntimeError):
    """Raised when the source PDF can't be opened or compressed."""


def compress_pdf(
    pdf_bytes: bytes,
    *,
    preset: CompressionPreset = PRESET_BALANCED,
) -> tuple[bytes, CompressionResult]:
    """Compress a PDF and return (new bytes, stats).

    Raises :class:`PdfCompressionError` for any malformed input;
    the endpoint maps that to HTTP 400 / 500 appropriately.
    """
    if not pdf_bytes:
        raise PdfCompressionError("Source PDF is empty.")

    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise PdfCompressionError(
            "PyMuPDF is not installed on the server."
        ) from exc

    try:
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise PdfCompressionError(f"Could not open PDF: {exc}") from exc

    dst = fitz.open()
    page_count = src.page_count
    try:
        # PDF default is 72 DPI; ``zoom`` ≥ 1 oversamples the source
        # at a higher resolution. Going above 200 burns CPU + bytes
        # without visible improvement for screen viewing.
        zoom = preset.target_dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        for page_index in range(page_count):
            page = src.load_page(page_index)
            pix = page.get_pixmap(matrix=matrix, alpha=False)

            # Pixmap -> Pillow -> JPEG bytes. ``optimize=True`` does
            # an extra entropy pass for ~5% additional savings;
            # ``progressive=True`` is a no-cost win for slow
            # connections.
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            jpeg_buf = BytesIO()
            img.save(
                jpeg_buf,
                format="JPEG",
                quality=preset.jpeg_quality,
                optimize=True,
                progressive=True,
            )
            jpeg_bytes = jpeg_buf.getvalue()

            # Stamp the JPEG onto a new page at the ORIGINAL pdf
            # dimensions so the output paginates identically to the
            # source — preserves printer / sharing expectations.
            new_page = dst.new_page(
                width=page.rect.width, height=page.rect.height
            )
            new_page.insert_image(new_page.rect, stream=jpeg_bytes)
    finally:
        try:
            src.close()
        except Exception:  # noqa: BLE001
            pass

    out_buf = BytesIO()
    try:
        dst.save(out_buf, garbage=4, deflate=True, clean=True)
    finally:
        try:
            dst.close()
        except Exception:  # noqa: BLE001
            pass

    compressed_bytes = out_buf.getvalue()
    return (
        compressed_bytes,
        CompressionResult(
            page_count=page_count,
            original_size_bytes=len(pdf_bytes),
            compressed_size_bytes=len(compressed_bytes),
            preset_name=preset.name,
        ),
    )


__all__ = [
    "CompressionPreset",
    "CompressionResult",
    "PRESETS",
    "PRESET_AGGRESSIVE",
    "PRESET_BALANCED",
    "PRESET_HIGH",
    "PdfCompressionError",
    "compress_pdf",
]
