"use client";

import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
  /**
   * When true (default) the full logo (mandala + wordmark) is shown.
   * When false only the mandala mark is shown.
   */
  showWordmark?: boolean;
  /** Where the logo should link to. */
  href?: string;
  /**
   * - `auto` (default): light variant on dark mode, dark variant on light mode.
   * - `dark`           : use the dark-on-light variant (for light surfaces).
   * - `light`          : use the light-on-dark variant (for dark surfaces).
   */
  variant?: "auto" | "dark" | "light";
  /** Rendered height of the logo. */
  size?: "sm" | "md" | "lg" | "xl";
}

/**
 * Rendered heights. We use Tailwind classes (not inline styles) so the
 * caller can still override via className if needed.
 *
 *   sm  →  h-7   (28 px) — admin sidebar
 *   md  →  h-10  (40 px) — standard navbar
 *   lg  →  h-12  (48 px) — footer, login pages
 *   xl  →  h-16  (64 px) — hero / marketing surfaces
 */
const HEIGHT_CLASS: Record<NonNullable<LogoProps["size"]>, string> = {
  sm: "h-7",
  md: "h-10",
  lg: "h-12",
  xl: "h-16",
};

/**
 * Approximate intrinsic aspect ratio of the supplied PUG logo PNG
 * (mandala + 3-line wordmark). Fed to next/image's width/height props
 * so SSR layout reservation matches reality; the actual rendered size
 * is governed by the CSS height class.
 */
const ASPECT_FULL = 2.1;
const ASPECT_MARK = 1;

// Pixel sizes used for width/height props on <Image>. Real render
// dimensions come from the CSS class.
const SIZE_PX: Record<NonNullable<LogoProps["size"]>, number> = {
  sm: 28,
  md: 40,
  lg: 48,
  xl: 64,
};

export function Logo({
  className,
  showWordmark = true,
  href = "/",
  variant = "auto",
  size = "md",
}: LogoProps) {
  const heightClass = HEIGHT_CLASS[size];
  const pxHeight = SIZE_PX[size];
  const aspect = showWordmark ? ASPECT_FULL : ASPECT_MARK;
  const pxWidth = Math.round(pxHeight * aspect);

  const darkSrc = showWordmark ? "/logo.png" : "/logo-mark.png";
  const lightSrc = showWordmark ? "/logo-light.png" : "/logo-mark.png";

  const imgClass = cn(heightClass, "w-auto object-contain");

  return (
    <Link
      href={href}
      aria-label="Paris United Group Holding home"
      className={cn("inline-flex shrink-0 items-center", className)}
    >
      {variant === "auto" ? (
        <>
          <Image
            src={darkSrc}
            alt="Paris United Group Holding"
            width={pxWidth}
            height={pxHeight}
            priority
            unoptimized
            className={cn(imgClass, "block dark:hidden")}
          />
          <Image
            src={lightSrc}
            alt="Paris United Group Holding"
            width={pxWidth}
            height={pxHeight}
            priority
            unoptimized
            className={cn(imgClass, "hidden dark:block")}
          />
        </>
      ) : (
        <Image
          src={variant === "light" ? lightSrc : darkSrc}
          alt="Paris United Group Holding"
          width={pxWidth}
          height={pxHeight}
          priority
          unoptimized
          className={imgClass}
        />
      )}
    </Link>
  );
}

/** Standalone mandala mark (square). */
export function MandalaMark({
  className,
  size = 36,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <Image
      src="/logo-mark.png"
      alt=""
      width={size}
      height={size}
      unoptimized
      className={cn("object-contain", className)}
    />
  );
}
