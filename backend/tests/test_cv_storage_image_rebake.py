"""Image uploads must be re-baked through Pillow so EXIF metadata is
stripped and malformed payloads pretending to be PNGs are rejected.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from app.services.cv_storage import CvUploadError, store_cv_bytes


def _png_with_text_chunks(text: str) -> bytes:
    """Build a tiny PNG with a custom tEXt chunk we want to verify is
    stripped after the rebake pass."""
    buf = io.BytesIO()
    img = Image.new("RGB", (2, 2), color=(0, 0, 0))
    from PIL.PngImagePlugin import PngInfo

    meta = PngInfo()
    meta.add_text("Comment", text)
    img.save(buf, format="PNG", pnginfo=meta)
    return buf.getvalue()


def _jpeg_with_exif() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (4, 4), color=(255, 0, 0))
    # Pillow will write a minimal EXIF block when ``exif`` kwarg is
    # supplied. Any non-empty bytes work for our "is EXIF preserved?"
    # before/after comparison.
    img.save(buf, format="JPEG", exif=b"Exif\x00\x00testtest")
    return buf.getvalue()


def _read_back(path_url: str) -> bytes:
    # The URL is /api/v1/uploads/cvs/<hash>.<ext> — locate the actual
    # file on disk via the storage path the test config uses.
    from app.core.config import get_settings

    settings = get_settings()
    name = path_url.rsplit("/", 1)[-1]
    p = Path(settings.upload_dir) / "cvs" / name
    return p.read_bytes()


class TestImageRebake:
    def test_png_rebake_strips_text_metadata(self, tmp_path, monkeypatch):
        # Force the upload dir to a clean tmp so this test doesn't
        # pollute the project tree.
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        from app.core.config import get_settings

        get_settings.cache_clear()
        try:
            payload = _png_with_text_chunks("MOM_VACATION_GPS_LOCATION")
            assert b"MOM_VACATION_GPS_LOCATION" in payload  # baseline

            meta = store_cv_bytes(payload, "selfie.png", "image/png")
            stored = _read_back(meta.url)
            # The text chunk should be gone after rebake.
            assert b"MOM_VACATION_GPS_LOCATION" not in stored
            # The stored bytes are still a valid PNG.
            Image.open(io.BytesIO(stored)).verify()
        finally:
            get_settings.cache_clear()

    def test_jpeg_rebake_strips_exif(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        from app.core.config import get_settings

        get_settings.cache_clear()
        try:
            payload = _jpeg_with_exif()
            assert b"testtest" in payload  # baseline EXIF tag value

            meta = store_cv_bytes(payload, "selfie.jpg", "image/jpeg")
            stored = _read_back(meta.url)
            assert b"testtest" not in stored
            Image.open(io.BytesIO(stored)).verify()
        finally:
            get_settings.cache_clear()

    def test_rejects_malformed_image_pretending_to_be_png(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        from app.core.config import get_settings

        get_settings.cache_clear()
        try:
            payload = b"not a png at all, just some bytes"
            with pytest.raises(CvUploadError):
                store_cv_bytes(payload, "evil.png", "image/png")
        finally:
            get_settings.cache_clear()

    def test_pdf_is_not_rebaked(self, tmp_path, monkeypatch):
        """PDF / DOC / DOCX bytes must be stored verbatim — the parser
        downstream needs the original file."""
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        from app.core.config import get_settings

        get_settings.cache_clear()
        try:
            # Minimal PDF magic + body.
            payload = b"%PDF-1.4\n%fake body\n%%EOF"
            meta = store_cv_bytes(payload, "cv.pdf", "application/pdf")
            stored = _read_back(meta.url)
            assert stored == payload
        finally:
            get_settings.cache_clear()
