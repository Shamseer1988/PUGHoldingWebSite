import * as React from "react";

import type { MediaVariants } from "@/lib/admin/types";
import { normaliseMediaUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";


interface ResponsiveImageProps {
  /** Original / full-resolution URL — used as the safe fallback. */
  src: string;
  /** Optimizer output from the backend (`MediaAsset.variants`). */
  variants?: MediaVariants | null;
  alt: string;
  className?: string;
  /**
   * Standard `sizes` attribute — drives the browser's variant
   * selection. Default assumes a full-width image; pass something
   * tighter (e.g. `(min-width: 1024px) 25vw, 50vw`) on grid tiles.
   */
  sizes?: string;
  /**
   * Set to `true` on above-the-fold imagery (hero, first card) so the
   * browser fetches it eagerly with high priority. Below-the-fold
   * images default to `loading="lazy" decoding="async"`.
   */
  priority?: boolean;
  /** Forces a specific aspect ratio via CSS — prevents layout shift. */
  aspectClassName?: string;
}


/**
 * `<picture>` wrapper that prefers WebP and falls back to JPEG / the
 * original URL. Always renders the JPEG fallback so non-WebP
 * browsers (basically none left in 2026, but the spec doesn't cost
 * us anything) get a working image.
 *
 * If the asset has no variants yet (uploaded before the optimizer
 * existed, or a video / SVG the optimizer skipped), we fall back to
 * the original URL with the same `loading` / `decoding` hints — slow
 * but never broken.
 *
 * Lookup `app/services/image_optimization.py` (backend) for the
 * source-of-truth variant widths.
 */
export function ResponsiveImage({
  src,
  variants,
  alt,
  className,
  sizes = "100vw",
  priority = false,
  aspectClassName,
}: ResponsiveImageProps) {
  const fallbackSrc = normaliseMediaUrl(src) ?? src;

  const loading = priority ? "eager" : "lazy";
  const decoding: React.ImgHTMLAttributes<HTMLImageElement>["decoding"] =
    "async";
  // fetchpriority is a valid HTML attr in React 18+ but the typings
  // haven't caught up everywhere — cast through unknown to keep TS
  // happy without reaching for `any`.
  const fetchAttrs = (
    priority ? { fetchpriority: "high" } : {}
  ) as unknown as React.ImgHTMLAttributes<HTMLImageElement>;

  if (!variants) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={fallbackSrc}
        alt={alt}
        loading={loading}
        decoding={decoding}
        className={cn(aspectClassName, className)}
        {...fetchAttrs}
      />
    );
  }

  // Phase A-7: rewrite each variant URL through ``normaliseMediaUrl``
  // so a relative ``/api/v1/uploads/cms/foo.webp`` becomes the absolute
  // CDN URL when ``NEXT_PUBLIC_MEDIA_BASE_URL`` is set, or the absolute
  // backend URL otherwise. Without this the browser would resolve the
  // relative path against the Next.js host and 404.
  const webpThumb = normaliseMediaUrl(variants.webp.thumb) ?? variants.webp.thumb;
  const webpMedium = normaliseMediaUrl(variants.webp.medium) ?? variants.webp.medium;
  const webpLarge = normaliseMediaUrl(variants.webp.large) ?? variants.webp.large;
  const jpgThumb = normaliseMediaUrl(variants.jpg.thumb) ?? variants.jpg.thumb;
  const jpgMedium = normaliseMediaUrl(variants.jpg.medium) ?? variants.jpg.medium;
  const jpgLarge = normaliseMediaUrl(variants.jpg.large) ?? variants.jpg.large;

  const webpSrcset = [
    `${webpThumb} 480w`,
    `${webpMedium} 960w`,
    `${webpLarge} 1920w`,
  ].join(", ");
  const jpgSrcset = [
    `${jpgThumb} 480w`,
    `${jpgMedium} 960w`,
    `${jpgLarge} 1920w`,
  ].join(", ");

  return (
    <picture className={cn(aspectClassName)}>
      <source type="image/webp" srcSet={webpSrcset} sizes={sizes} />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={jpgMedium}
        srcSet={jpgSrcset}
        sizes={sizes}
        alt={alt}
        loading={loading}
        decoding={decoding}
        className={className}
        {...fetchAttrs}
      />
    </picture>
  );
}
