"""Branded QR-code generation for catalogue share links.

Builds a high-contrast PNG with the catalogue's public URL encoded in
a QR pattern, optionally overlaid with a small Paris United Group
logo in the centre so the code reads as a branded share asset rather
than a generic black-and-white square.

Used by the admin Catalogues page — a per-row button generates the
QR on demand and downloads it as a PNG, ready to drop into a printed
flyer, in-store signage, or social posts.
"""
from __future__ import annotations

from io import BytesIO
from typing import Optional

from PIL import Image
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer


# PUG brand colours (matches the email + viewer chrome).
BRAND_FG = "#17382f"   # dark green
BRAND_BG = "#f6f3eb"   # warm off-white
BRAND_ACCENT = "#b89c5c"  # gold


def build_catalogue_qr(
    public_url: str,
    *,
    logo_bytes: Optional[bytes] = None,
    size_px: int = 720,
    background: str = BRAND_BG,
    foreground: str = BRAND_FG,
) -> bytes:
    """Render the catalogue QR code to PNG bytes.

    ``ERROR_CORRECT_H`` (highest level) tolerates a ~30% obscured
    region so we can punch a logo into the centre without the code
    becoming unscannable. Rounded module drawer + brand foreground
    keep the share asset on-brand.

    ``logo_bytes`` is the raw image bytes for the centre badge. The
    caller is responsible for sourcing those bytes — typically from
    the storage backend via :func:`download_sync` so the QR works
    against R2 just as well as against the local-disk install. When
    no logo bytes are supplied (or decoding them fails) the badge
    falls back to a plain "PUG" monogram disc.
    """
    if not public_url:
        raise ValueError("public_url is required")

    qr = qrcode.QRCode(
        version=None,  # auto-select smallest fit
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(public_url)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=_hex_to_rgb(background),
            front_color=_hex_to_rgb(foreground),
        ),
    ).convert("RGBA")

    # Resize to the target box, preserving aspect (the QR is square).
    img = img.resize((size_px, size_px), Image.LANCZOS)

    # Centre-stamp a small brand badge so the share code is visibly
    # ours. Logo bytes are optional — if missing or undecodable we
    # fall back to a plain monogram disc.
    badge = _build_badge(size_px // 5, logo_bytes=logo_bytes)
    if badge is not None:
        bx = (img.width - badge.width) // 2
        by = (img.height - badge.height) // 2
        img.alpha_composite(badge, dest=(bx, by))

    out = BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _build_badge(side: int, *, logo_bytes: Optional[bytes]) -> Optional[Image.Image]:
    """Build a circular brand badge to stamp over the QR centre."""
    # Solid background disc in the brand off-white with a thin
    # gold border so the badge stands out against the dark QR
    # modules.
    badge = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    from PIL import ImageDraw

    draw = ImageDraw.Draw(badge)
    border = max(2, side // 20)
    draw.ellipse(
        (0, 0, side - 1, side - 1),
        fill=_hex_to_rgb(BRAND_BG) + (255,),
        outline=_hex_to_rgb(BRAND_ACCENT) + (255,),
        width=border,
    )

    inner_side = side - border * 4
    if logo_bytes:
        try:
            logo = Image.open(BytesIO(logo_bytes)).convert("RGBA")
            # Fit the logo into a square inside the badge while
            # preserving aspect.
            logo.thumbnail((inner_side, inner_side), Image.LANCZOS)
            ox = (badge.width - logo.width) // 2
            oy = (badge.height - logo.height) // 2
            badge.alpha_composite(logo, dest=(ox, oy))
            return badge
        except Exception:  # noqa: BLE001 — fall through to monogram
            pass

    # Monogram fallback — "PUG" centered in the brand foreground.
    try:
        from PIL import ImageFont

        # Try common system fonts; reportlab ships DejaVu which
        # we know is on the image.
        font = None
        for candidate in (
            "DejaVuSans-Bold.ttf",
            "Arial Bold.ttf",
            "Inter-Bold.ttf",
        ):
            try:
                font = ImageFont.truetype(candidate, size=inner_side // 2)
                break
            except (OSError, IOError):
                continue
        if font is None:
            font = ImageFont.load_default()
        text = "PUG"
        # textbbox is the modern API in Pillow ≥ 10.
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (badge.width - tw) // 2 - bbox[0]
        ty = (badge.height - th) // 2 - bbox[1]
        draw.text(
            (tx, ty),
            text,
            fill=_hex_to_rgb(BRAND_FG) + (255,),
            font=font,
        )
    except Exception:  # noqa: BLE001
        # Last-resort: leave the disc empty rather than crash.
        pass
    return badge


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    """``#17382f`` -> ``(23, 56, 47)``. Permissive about leading ``#``."""
    v = value.strip().lstrip("#")
    if len(v) != 6:
        raise ValueError(f"Expected a 6-char hex color, got {value!r}")
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


__all__ = ["build_catalogue_qr"]
