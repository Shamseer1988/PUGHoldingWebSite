"""Server-side image optimization for uploaded media.

Every image uploaded through the admin Media Gallery is resized into
three WebP variants (thumb / medium / large) on the server right
after the original is written to disk. The public site uses a
``<picture>`` element preferring WebP, with a JPEG fallback set
generated alongside.

Why this matters:

* The biggest single perf win on the public site. Admins upload
  full-resolution photos (often 4–10 MB). Without optimization, a
  phone visitor downloads the same 4 MB asset that a desktop
  visitor does — slow and expensive.
* WebP is ~30% smaller than JPEG at the same perceived quality,
  ~70% smaller than PNG.
* Multiple widths let the browser pick the smallest variant that
  matches its viewport via ``srcset`` + ``sizes``.

Design notes:

* Fail-soft. If Pillow can't decode the file (SVG, broken upload,
  HEIC with no plugin), we keep the original on disk and return
  ``None`` so the row stores no variants. The frontend's
  ``ResponsiveImage`` component falls back to the original URL.
* The original file always stays untouched — it's the source of
  truth for the lightbox and downloads.
* SVG isn't resized (vector — already small) but we still skip
  Pillow on it.
* Animated GIFs get a static first-frame WebP; rendering the
  animated variant would defeat the size-saving goal.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Target widths for the responsive variants.
# 480: phone tile / thumbnail
# 960: standard card / 2-up grid
# 1920: hero / lightbox
VARIANT_WIDTHS: dict[str, int] = {
    "thumb": 480,
    "medium": 960,
    "large": 1920,
}

# WebP quality. 78 is the visual sweet spot for photographs — most
# users can't tell it from 90+ but the byte savings are large.
WEBP_QUALITY = 78
JPEG_QUALITY = 82

# MIME types we won't try to optimize.
_SKIP_MIME_TYPES = frozenset(
    {
        "image/svg+xml",
        "image/x-icon",
    }
)


@dataclass(frozen=True)
class VariantSet:
    """Result of optimizing one source image.

    Each value is a public URL (e.g. ``/api/v1/uploads/cms/<hash>-thumb.webp``)
    that the frontend can drop straight into ``<picture>``.
    """

    webp: dict[str, str]
    jpg: dict[str, str]

    def as_dict(self) -> dict[str, dict[str, str]]:
        return {"webp": dict(self.webp), "jpg": dict(self.jpg)}


def optimize_image(
    source_path: Path,
    *,
    public_base_url: str,
    mime_type: Optional[str] = None,
) -> Optional[VariantSet]:
    """Generate WebP + JPEG variants alongside ``source_path``.

    ``public_base_url`` is the URL prefix that the frontend uses to
    fetch from the same directory (e.g.
    ``/api/v1/uploads/cms`` — the variant filenames are appended).

    Returns ``None`` when Pillow can't handle the image — the caller
    should then leave ``MediaAsset.variants`` as ``NULL``. The
    original file stays on disk in every case.
    """
    if mime_type and mime_type in _SKIP_MIME_TYPES:
        return None
    if not source_path.exists():
        logger.warning("optimize_image: source missing %s", source_path)
        return None

    try:
        from PIL import Image, ImageOps  # imported lazily to keep startup fast
    except Exception as exc:  # pragma: no cover - import guard
        logger.warning("optimize_image: Pillow unavailable (%s)", exc)
        return None

    stem = source_path.stem
    out_dir = source_path.parent
    base_url = public_base_url.rstrip("/")

    webp_urls: dict[str, str] = {}
    jpg_urls: dict[str, str] = {}

    try:
        with Image.open(source_path) as raw:
            # EXIF orientation handling — a photo shot in portrait
            # on a phone often arrives sideways without this.
            img = ImageOps.exif_transpose(raw)
            # Drop alpha for the JPEG fallback. Keep RGBA for WebP
            # (it supports transparency).
            rgb_img = img.convert("RGB") if img.mode != "RGB" else img
            rgba_img = img.convert("RGBA") if img.mode not in {"RGB", "RGBA"} else img

            for variant, target_width in VARIANT_WIDTHS.items():
                # Don't upscale — if the original is narrower than
                # the target, use the original's dimensions so we
                # don't waste bytes on blurry pixels.
                target_w = min(target_width, img.width)
                ratio = target_w / img.width if img.width else 1.0
                target_h = max(1, int(round(img.height * ratio)))

                # --- WebP variant ---
                webp_name = f"{stem}-{variant}.webp"
                webp_path = out_dir / webp_name
                webp_img = rgba_img.resize(
                    (target_w, target_h), Image.Resampling.LANCZOS
                )
                webp_img.save(
                    webp_path,
                    format="WEBP",
                    quality=WEBP_QUALITY,
                    method=6,
                )
                webp_urls[variant] = f"{base_url}/{webp_name}"

                # --- JPEG fallback ---
                jpg_name = f"{stem}-{variant}.jpg"
                jpg_path = out_dir / jpg_name
                jpg_img = rgb_img.resize(
                    (target_w, target_h), Image.Resampling.LANCZOS
                )
                jpg_img.save(
                    jpg_path,
                    format="JPEG",
                    quality=JPEG_QUALITY,
                    optimize=True,
                    progressive=True,
                )
                jpg_urls[variant] = f"{base_url}/{jpg_name}"

    except Exception as exc:
        # Pillow raises various OSError / UnidentifiedImageError
        # subclasses for unsupported / corrupt files. Don't fail the
        # upload because the optimisation step couldn't decode.
        logger.warning(
            "optimize_image: skipping %s (%s: %s)",
            source_path,
            type(exc).__name__,
            exc,
        )
        return None

    return VariantSet(webp=webp_urls, jpg=jpg_urls)
