"""Tests for app.services.image_optimization."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.services.image_optimization import (
    VARIANT_WIDTHS,
    optimize_image,
)


def _write_test_image(tmp_path: Path, width: int = 2400, height: int = 1600) -> Path:
    """Build a real, multi-pixel JPEG so the resizer has something to chew on."""
    from PIL import Image

    src = tmp_path / "source.jpg"
    img = Image.new("RGB", (width, height), color=(60, 130, 90))
    img.save(src, format="JPEG", quality=90)
    return src


def test_optimize_image_generates_all_variants(tmp_path: Path):
    src = _write_test_image(tmp_path)
    result = optimize_image(
        src,
        public_base_url="/api/v1/uploads/cms",
        mime_type="image/jpeg",
    )
    assert result is not None
    for variant in VARIANT_WIDTHS:
        assert variant in result.webp
        assert variant in result.jpg
        # URLs point at the same cms subtree.
        assert result.webp[variant].startswith("/api/v1/uploads/cms/source-")
        assert result.webp[variant].endswith(".webp")
        assert result.jpg[variant].startswith("/api/v1/uploads/cms/source-")
        assert result.jpg[variant].endswith(".jpg")
        # Files actually written to disk.
        assert (src.parent / Path(result.webp[variant]).name).exists()
        assert (src.parent / Path(result.jpg[variant]).name).exists()


def test_webp_payload_is_smaller_than_source(tmp_path: Path):
    """The whole point: WebP medium must be smaller than the JPEG source."""
    src = _write_test_image(tmp_path, width=1600, height=1200)
    result = optimize_image(
        src,
        public_base_url="/api/v1/uploads/cms",
        mime_type="image/jpeg",
    )
    assert result is not None
    src_size = src.stat().st_size
    webp_medium = src.parent / Path(result.webp["medium"]).name
    assert webp_medium.stat().st_size < src_size


def test_does_not_upscale(tmp_path: Path):
    """Source smaller than 'large' variant width must not be upscaled."""
    from PIL import Image

    src = _write_test_image(tmp_path, width=400, height=300)  # smaller than 'thumb'
    result = optimize_image(
        src,
        public_base_url="/api/v1/uploads/cms",
        mime_type="image/jpeg",
    )
    assert result is not None
    for variant in ("thumb", "medium", "large"):
        out = src.parent / Path(result.webp[variant]).name
        with Image.open(out) as img:
            assert img.width <= 400, (variant, img.width)


def test_svg_is_skipped(tmp_path: Path):
    """Vectors don't need resizing — skip cleanly."""
    src = tmp_path / "logo.svg"
    src.write_text("<svg></svg>")
    assert (
        optimize_image(src, public_base_url="/x", mime_type="image/svg+xml")
        is None
    )


def test_corrupt_file_returns_none(tmp_path: Path):
    """A non-image file with an image mime returns None and doesn't crash."""
    bogus = tmp_path / "bogus.jpg"
    bogus.write_bytes(b"not actually a jpeg")
    assert optimize_image(bogus, public_base_url="/x", mime_type="image/jpeg") is None


def test_missing_source_returns_none(tmp_path: Path):
    assert (
        optimize_image(
            tmp_path / "nonexistent.jpg",
            public_base_url="/x",
            mime_type="image/jpeg",
        )
        is None
    )


def test_upload_persists_variants_on_media_asset(client, db_session, seed_auth):
    """End-to-end: an admin upload writes variants to the row."""
    from PIL import Image

    headers = {
        "Authorization": (
            "Bearer "
            + client.post(
                "/api/v1/admin/auth/login",
                json={
                    "email": "superadmin@pug.example.com",
                    "password": seed_auth["password"],
                },
            ).json()["access_token"]
        )
    }
    # Build a real >1×1 JPEG so the variants are meaningful.
    buf = io.BytesIO()
    Image.new("RGB", (1200, 800), color=(120, 60, 200)).save(
        buf, format="JPEG", quality=88
    )
    buf.seek(0)

    resp = client.post(
        "/api/v1/admin/cms/media/upload",
        headers=headers,
        files={"file": ("hero.jpg", buf, "image/jpeg")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    variants = body["asset"]["variants"]
    assert variants is not None, "upload didn't persist variants"
    assert set(variants["webp"]) == {"thumb", "medium", "large"}
    assert set(variants["jpg"]) == {"thumb", "medium", "large"}
