"use client";

import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
  /**
   * When true (default) the full logo (mandala + wordmark) is shown.
   * When false only the mandala mark is shown — used in tight spaces
   * (favicons, narrow mobile chrome).
   */
  showWordmark?: boolean;
  /** Where the logo should link to. */
  href?: string;
  /**
   * - `auto` (default): light variant on dark mode, dark variant on light mode.
   * - `dark`           : use the dark-on-light variant (for light surfaces).
   * - `light`          : use the light-on-dark variant (for dark surfaces such
   *                       as a coloured hero).
   */
  variant?: "auto" | "dark" | "light";
  /** Approximate height of the rendered logo. */
  size?: "sm" | "md" | "lg";
}

const HEIGHT: Record<NonNullable<LogoProps["size"]>, number> = {
  sm: 32,
  md: 40,
  lg: 56,
};

// The supplied logo (mandala + wordmark) is wider than tall. 2.4x is
// the approximate aspect ratio of the images you attached.
const ASPECT_FULL = 2.4;
const ASPECT_MARK = 1;

/**
 * Paris United Group Holding logo.
 *
 * Reads PNGs from /public so the website admin can swap the files
 * without touching code. Expected files:
 *
 *   /public/logo.png            full logo for LIGHT surfaces
 *                               (green wordmark + gold mandala + gold HOLDING)
 *   /public/logo-light.png      full logo for DARK surfaces
 *                               (gold/cream wordmark + gold mandala + gold HOLDING)
 *   /public/logo-mark.png       mandala only (square)
 *
 * The favicon is wired through Next.js `app/icon.png` instead of the
 * old /favicon.ico convention.
 */
export function Logo({
  className,
  showWordmark = true,
  href = "/",
  variant = "auto",
  size = "md",
}: LogoProps) {
  const height = HEIGHT[size];
  const aspect = showWordmark ? ASPECT_FULL : ASPECT_MARK;
  const width = Math.round(height * aspect);

  const darkSrc = showWordmark ? "/logo.png" : "/logo-mark.png";
  const lightSrc = showWordmark ? "/logo-light.png" : "/logo-mark.png";

  const commonImg = {
    alt: "Paris United Group Holding",
    width,
    height,
    priority: true,
    // `unoptimized` keeps the image pipeline simple while the user is
    // iterating on the asset (no need to redeploy or wait for ISR).
    unoptimized: true,
  } as const;

  return (
    <Link
      href={href}
      aria-label="Paris United Group Holding home"
      className={cn("inline-flex items-center", className)}
    >
      {variant === "auto" ? (
        <>
          <Image
            src={darkSrc}
            {...commonImg}
            className="block h-auto w-auto max-h-full dark:hidden"
          />
          <Image
            src={lightSrc}
            {...commonImg}
            className="hidden h-auto w-auto max-h-full dark:block"
          />
        </>
      ) : (
        <Image
          src={variant === "light" ? lightSrc : darkSrc}
          {...commonImg}
          className="h-auto w-auto max-h-full"
        />
      )}
    </Link>
  );
}

/**
 * Standalone mandala mark (square) — kept as a named export for
 * components that previously imported it.
 */
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
      className={cn("h-9 w-9", className)}
    />
  );
}
