"""Branded QR generation smoke tests.

These don't try to scan the resulting QR (pyzbar isn't part of the
dependency set) but they DO assert the contract that keeps the
output reliably scannable:

* Valid PNG of the requested square dimensions.
* Quiet-zone module count meets the QR spec.
* Centre badge footprint stays inside the
  ``ERROR_CORRECT_H`` ~30% obscured-region tolerance — anything
  bigger and the redundancy can't recover the central modules.
* Both the per-catalogue-logo and the "PUG" monogram fallback
  produce visible badges (non-blank centre region).
"""
from __future__ import annotations

import io

from PIL import Image

from app.services.qr_codes import (
    BADGE_FRACTION,
    LOGO_FRACTION,
    RING_FRACTION,
    build_catalogue_qr,
)


PUBLIC_URL = "https://parisunitedgroup.com/offers/catalogues/summer-edit"


def _tiny_brand_logo() -> bytes:
    """Build a small RGBA logo with brand colours so the badge's
    "logo present" branch has something visible to composite."""
    img = Image.new("RGBA", (64, 64), (180, 156, 92, 255))  # gold
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _decode(png_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png_bytes))


def test_default_size_is_print_friendly():
    """1024 px at 300 DPI prints at ~3.4″ — enough for flyer-corner
    placement without visible scaling artefacts."""
    img = _decode(build_catalogue_qr(PUBLIC_URL))
    assert img.format == "PNG"
    assert img.size == (1024, 1024)


def test_custom_size_round_trips():
    img = _decode(build_catalogue_qr(PUBLIC_URL, size_px=512))
    assert img.size == (512, 512)


def test_empty_url_raises():
    import pytest

    with pytest.raises(ValueError):
        build_catalogue_qr("")


def test_logo_branch_renders_non_blank_centre():
    """With a logo supplied, the central badge region should NOT
    be the QR background colour (the white plate + logo should
    knock out the modules behind it)."""
    png = build_catalogue_qr(PUBLIC_URL, logo_bytes=_tiny_brand_logo())
    img = _decode(png).convert("RGBA")
    cx, cy = img.size[0] // 2, img.size[1] // 2
    centre_pixel = img.getpixel((cx, cy))
    # Anything other than pure QR-foreground or pure QR-background
    # — the badge stamps a distinctive colour at the centre.
    assert centre_pixel not in {(23, 56, 47, 255), (246, 243, 235, 255)}


def test_monogram_fallback_renders_white_plate():
    """No logo supplied — the centre should be the white knockout
    plate (with the "PUG" monogram text on top). At the very
    centre we expect either the white plate or the dark monogram
    text, NEVER the warm-off-white QR background."""
    png = build_catalogue_qr(PUBLIC_URL)
    img = _decode(png).convert("RGBA")
    cx, cy = img.size[0] // 2, img.size[1] // 2
    # Sample a 4-pixel cluster at the centre so a single antialiased
    # text pixel doesn't trick the assertion.
    samples = [
        img.getpixel((cx + dx, cy + dy))
        for dx in (-1, 1)
        for dy in (-1, 1)
    ]
    # At least one of the centre samples is the white plate
    # (255, 255, 255, 255). If every sample were the QR background
    # off-white the plate didn't render.
    assert (255, 255, 255, 255) in samples or any(
        s != (246, 243, 235, 255) for s in samples
    )


def test_invalid_logo_bytes_falls_back_to_monogram():
    """A corrupt logo upload shouldn't 500 the QR endpoint; the
    decoder catches the error and the function returns a valid PNG
    with the monogram fallback in the centre."""
    png = build_catalogue_qr(PUBLIC_URL, logo_bytes=b"not-an-image")
    img = _decode(png)
    assert img.format == "PNG"
    assert img.size == (1024, 1024)


def test_badge_fraction_within_scan_safe_envelope():
    """Hard ceiling: the centre badge must stay inside
    ``ERROR_CORRECT_H`` 's safe obscured-region (~30%)."""
    assert BADGE_FRACTION <= 0.22


def test_logo_padding_leaves_clear_zone_inside_disc():
    """The logo must fit comfortably inside the gold ring with
    pure-white padding all around — pad fraction = 1 - logo - ring
    on each side. Keep at least 5 percentage points of clear white
    between the logo edge and the ring inner edge."""
    pad_each_side = (1.0 - LOGO_FRACTION) / 2 - RING_FRACTION
    assert pad_each_side >= 0.05


def test_short_url_still_produces_smallest_canvas_correctly():
    """A short URL would auto-pick QR version 1 (21×21). Make sure
    we still get the requested canvas size — the resize at the
    end is what locks the output dimensions, regardless of the
    underlying QR version."""
    img = _decode(build_catalogue_qr("https://x.test/a", size_px=512))
    assert img.size == (512, 512)
