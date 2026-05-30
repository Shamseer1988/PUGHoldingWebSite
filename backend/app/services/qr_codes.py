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
BRAND_FG = "#17382f"     # dark green — QR modules + monogram text
BRAND_BG = "#f6f3eb"     # warm off-white — QR background
BRAND_ACCENT = "#b89c5c" # gold — knockout plate ring
PLATE_BG = "#ffffff"     # pure white — solid backing under the logo


# Centre-badge footprint as a fraction of the rendered QR canvas.
# 0.20 stays comfortably inside ``ERROR_CORRECT_H``'s ~30% obscured-
# region tolerance so the code keeps scanning even after the badge
# overlays the centre modules. Bumping this past 0.22 starts pushing
# into "may fail on bargain phone cameras" territory.
BADGE_FRACTION = 0.20

# Inner ring thickness as a fraction of the badge diameter. Thicker
# than the previous 1/20 so the gold accent reads at print size.
RING_FRACTION = 0.08

# Logo footprint as a fraction of the badge diameter. The remainder
# is pure-white padding that knocks out the QR modules around the
# logo so the brand mark never sits on top of dark squares. A
# transparent-PNG logo with thin strokes used to "touch" the QR
# pattern at the corners; capping at 62% gives every logo shape
# room to breathe.
LOGO_FRACTION = 0.62


def build_catalogue_qr(
    public_url: str,
    *,
    logo_bytes: Optional[bytes] = None,
    size_px: int = 1024,
    background: str = BRAND_BG,
    foreground: str = BRAND_FG,
) -> bytes:
    """Render the catalogue QR code to PNG bytes.

    ``ERROR_CORRECT_H`` (highest level) tolerates a ~30% obscured
    region so we can punch a logo into the centre without the code
    becoming unscannable. Rounded module drawer + brand foreground
    keep the share asset on-brand. The output canvas defaults to
    1024 px — large enough to print at ~3.4″ / 300 DPI without
    visible scaling, while staying small for inline display.

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
        # Standard QR quiet zone is 4 modules — anything less leaves
        # scanners that auto-crop tight margins struggling to lock on.
        # The previous 2 was tolerable on a desktop preview but
        # marginal in printed flyers.
        border=4,
        box_size=10,
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

    # Centre-stamp a brand badge: pure-white knockout disc + gold
    # ring + logo (or PUG monogram fallback). Logo bytes optional.
    badge_side = max(1, round(size_px * BADGE_FRACTION))
    badge = _build_badge(badge_side, logo_bytes=logo_bytes)
    if badge is not None:
        bx = (img.width - badge.width) // 2
        by = (img.height - badge.height) // 2
        img.alpha_composite(badge, dest=(bx, by))

    out = BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _build_badge(side: int, *, logo_bytes: Optional[bytes]) -> Optional[Image.Image]:
    """Build a circular brand badge to stamp over the QR centre.

    Layout — outward to inward:

      1. Outer transparent canvas (side × side).
      2. Pure-white disc filling the whole side — this is the
         knockout plate that obscures the QR modules.
      3. Gold ring (``RING_FRACTION`` thick) drawn just inside the
         disc edge for brand definition.
      4. Logo / monogram centred on the white plate, capped at
         ``LOGO_FRACTION`` of the disc width so it never crowds
         either the ring or the QR modules around the badge.

    The plate stays pure white (not brand off-white) so the disc
    visually reads as a knockout against the warm QR background.
    Pure white also maximises contrast for scanners that key on
    brightness rather than colour.
    """
    badge = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    from PIL import ImageDraw

    draw = ImageDraw.Draw(badge)

    # Outer white plate. Drawn at the very edge of the badge canvas
    # so the gold ring (next) sits flush to the boundary.
    draw.ellipse(
        (0, 0, side - 1, side - 1),
        fill=_hex_to_rgb(PLATE_BG) + (255,),
    )

    # Gold ring, drawn as a thick outline. ``Pillow``'s outline
    # parameter draws the ring inside the bounding box, so the
    # plate stays the full ``side`` diameter and the ring eats
    # ``ring_w`` pixels off the inside.
    ring_w = max(2, round(side * RING_FRACTION))
    draw.ellipse(
        (0, 0, side - 1, side - 1),
        outline=_hex_to_rgb(BRAND_ACCENT) + (255,),
        width=ring_w,
    )

    # Logo / monogram footprint — square inscribed in the plate
    # inside the ring, with ``LOGO_FRACTION`` of the badge diameter
    # as the cap. Anything bigger starts brushing the ring's inner
    # edge or (in landscape logos) the white plate's curve.
    logo_max = max(1, round(side * LOGO_FRACTION))

    if logo_bytes:
        try:
            logo = Image.open(BytesIO(logo_bytes)).convert("RGBA")
            # ``thumbnail`` preserves aspect ratio and uses LANCZOS
            # for the highest-quality downsample; the logo always
            # fits inside ``logo_max`` × ``logo_max``.
            logo.thumbnail((logo_max, logo_max), Image.LANCZOS)
            ox = (badge.width - logo.width) // 2
            oy = (badge.height - logo.height) // 2
            badge.alpha_composite(logo, dest=(ox, oy))
            return badge
        except Exception:  # noqa: BLE001 — fall through to monogram
            pass

    # Monogram fallback — "PUG" centred in brand foreground.
    try:
        from PIL import ImageFont

        # Try common bundled fonts first; reportlab ships DejaVu and
        # the slim image normally has it too. Fall through to
        # Pillow's default bitmap if nothing fancier is around — at
        # least the badge stays legible.
        font = None
        for candidate in (
            "DejaVuSans-Bold.ttf",
            "Arial Bold.ttf",
            "Inter-Bold.ttf",
        ):
            try:
                font = ImageFont.truetype(candidate, size=logo_max // 2)
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
        # Last-resort: leave the white plate empty rather than crash.
        pass
    return badge


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    """``#17382f`` -> ``(23, 56, 47)``. Permissive about leading ``#``."""
    v = value.strip().lstrip("#")
    if len(v) != 6:
        raise ValueError(f"Expected a 6-char hex color, got {value!r}")
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


__all__ = ["build_catalogue_qr"]
