"""PDF Compressor — service + endpoint tests."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.services.pdf_compressor import (
    PRESETS,
    CompressionPreset,
    PdfCompressionError,
    compress_pdf,
)


ADMIN_LOGIN = "/api/v1/admin/auth/login"
ENDPOINT = "/api/v1/admin/marketing/pdf-compressor"


def _login_super(client: TestClient, password: str) -> dict:
    resp = client.post(
        ADMIN_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_pdf_with_a_large_raster(page_count: int = 2) -> bytes:
    """Build a PDF whose pages embed full-bleed raster images so the
    compressor has something meaningful to shrink. Plain vector
    pages don't benefit from rasterise+JPEG, so a heavier source
    keeps the size-reduction assertion realistic.
    """
    import fitz
    from PIL import Image

    # Build one chunky JPEG to embed on every page (1500x2000, lots of
    # detail to keep file size up).
    img = Image.new("RGB", (1500, 2000), (200, 30, 30))
    # Add a noisy pattern so JPEG can't collapse it to a tiny size.
    for y in range(0, 2000, 4):
        for x in range(0, 1500, 4):
            img.putpixel((x, y), ((x * 53) % 256, (y * 31) % 256, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    jpg_bytes = buf.getvalue()

    doc = fitz.open()
    for i in range(page_count):
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=jpg_bytes)
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def _grant_marketing_perm(db_session, seed_auth) -> None:
    from app.auth.permissions import PERM_MARKETING_CATALOGUES_MANAGE
    from app.models.auth import Permission, SCOPE_SYSTEM

    role = seed_auth["roles"]["Super Admin"]
    perm = (
        db_session.query(Permission)
        .filter_by(key=PERM_MARKETING_CATALOGUES_MANAGE)
        .first()
    )
    if perm is None:
        perm = Permission(
            key=PERM_MARKETING_CATALOGUES_MANAGE,
            scope=SCOPE_SYSTEM,
            description="test grant",
        )
        db_session.add(perm)
        db_session.flush()
    if perm not in role.permissions:
        role.permissions = role.permissions + [perm]
    db_session.commit()


# ---------------------------------------------------------------------------
# Pure service
# ---------------------------------------------------------------------------


class TestCompressService:
    def test_compresses_image_heavy_pdf(self):
        original = _make_pdf_with_a_large_raster(page_count=2)
        compressed, stats = compress_pdf(
            original, preset=PRESETS["aggressive"]
        )
        # Output is a valid PDF
        assert compressed[:5] == b"%PDF-"
        # And it's meaningfully smaller — aggressive preset on a
        # 95-quality JPEG should comfortably drop ~30% or more.
        assert stats.original_size_bytes == len(original)
        assert stats.compressed_size_bytes == len(compressed)
        assert stats.compressed_size_bytes < stats.original_size_bytes
        assert stats.page_count == 2
        assert 0 < stats.reduction_ratio < 1

    @pytest.mark.parametrize(
        "preset_name", ["high", "balanced", "aggressive"]
    )
    def test_all_presets_produce_valid_output(self, preset_name):
        original = _make_pdf_with_a_large_raster(page_count=1)
        compressed, stats = compress_pdf(
            original, preset=PRESETS[preset_name]
        )
        assert compressed[:5] == b"%PDF-"
        assert stats.page_count == 1
        assert stats.preset_name == preset_name

    def test_aggressive_smaller_than_high(self):
        original = _make_pdf_with_a_large_raster(page_count=1)
        _, high = compress_pdf(original, preset=PRESETS["high"])
        _, aggressive = compress_pdf(original, preset=PRESETS["aggressive"])
        assert (
            aggressive.compressed_size_bytes
            <= high.compressed_size_bytes
        ), "aggressive preset must not produce a larger file than high"

    def test_empty_input_raises(self):
        with pytest.raises(PdfCompressionError):
            compress_pdf(b"")

    def test_garbage_input_raises(self):
        with pytest.raises(PdfCompressionError):
            compress_pdf(b"this is definitely not a PDF")


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestCompressEndpoint:
    def test_anon_is_401(self, client: TestClient):
        files = {"file": ("x.pdf", b"%PDF-1.4\n", "application/pdf")}
        assert client.post(ENDPOINT, files=files).status_code == 401

    def test_rejects_non_pdf(self, client: TestClient, seed_auth, db_session):
        _grant_marketing_perm(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])
        files = {"file": ("doc.txt", b"hello", "text/plain")}
        r = client.post(
            ENDPOINT, headers=headers, files=files, data={"preset": "balanced"}
        )
        assert r.status_code == 400

    def test_rejects_unknown_preset(
        self, client: TestClient, seed_auth, db_session
    ):
        _grant_marketing_perm(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])
        pdf = _make_pdf_with_a_large_raster(1)
        r = client.post(
            ENDPOINT,
            headers=headers,
            files={"file": ("x.pdf", pdf, "application/pdf")},
            data={"preset": "ultra-mega-tiny"},
        )
        assert r.status_code == 422

    def test_happy_path_returns_smaller_pdf_with_headers(
        self, client: TestClient, seed_auth, db_session
    ):
        _grant_marketing_perm(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])
        pdf = _make_pdf_with_a_large_raster(page_count=2)
        r = client.post(
            ENDPOINT,
            headers=headers,
            files={"file": ("flyer.pdf", pdf, "application/pdf")},
            data={"preset": "aggressive"},
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("application/pdf")
        # Compressed body is a valid PDF
        assert r.content[:5] == b"%PDF-"
        # Diagnostic headers
        assert int(r.headers["X-Original-Size"]) == len(pdf)
        assert int(r.headers["X-Compressed-Size"]) == len(r.content)
        assert int(r.headers["X-Compressed-Size"]) < len(pdf)
        assert int(r.headers["X-Page-Count"]) == 2
        assert r.headers["X-Preset"] == "aggressive"
        # Filename ends with _compressed.pdf
        assert (
            "flyer_compressed.pdf"
            in r.headers["content-disposition"].lower()
        )
