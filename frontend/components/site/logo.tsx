import Link from "next/link";

import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
  /** Show the full word-mark beside the icon. */
  showWordmark?: boolean;
  /** Where the logo should link to. */
  href?: string;
  /** Variant: 'auto' (theme-aware), 'dark' (for light surfaces),
   * 'light' (for dark surfaces). */
  variant?: "auto" | "dark" | "light";
  /** Approximate height of the mark in rem (defaults to 2.25rem). */
  size?: "sm" | "md" | "lg";
}

const SIZE_TO_CLASS: Record<NonNullable<LogoProps["size"]>, string> = {
  sm: "h-7 w-7",
  md: "h-9 w-9",
  lg: "h-12 w-12",
};

const WORDMARK_SIZE: Record<NonNullable<LogoProps["size"]>, string> = {
  sm: "text-[11px]",
  md: "text-sm",
  lg: "text-base",
};

const WORDMARK_TAGLINE_SIZE: Record<NonNullable<LogoProps["size"]>, string> = {
  sm: "text-[9px]",
  md: "text-[10px]",
  lg: "text-[11px]",
};

/**
 * Paris United Group Holding wordmark + mandala mark.
 *
 * The mandala SVG approximates the lotus-style symbol from the brand
 * logo. When `variant="auto"` (default) the colour tracks the active
 * theme — both mark and wordmark stay legible in light and dark.
 */
export function Logo({
  className,
  showWordmark = true,
  href = "/",
  variant = "auto",
  size = "md",
}: LogoProps) {
  return (
    <Link
      href={href}
      aria-label="Paris United Group Holding home"
      className={cn(
        "group inline-flex items-center gap-2.5 font-semibold tracking-tight",
        className
      )}
    >
      <MandalaMark
        className={cn(SIZE_TO_CLASS[size], "shrink-0")}
        variant={variant}
      />
      {showWordmark && (
        <span className="hidden flex-col leading-tight sm:flex">
          <span
            className={cn(
              "font-semibold tracking-[0.06em]",
              WORDMARK_SIZE[size],
              variant === "light"
                ? "text-white"
                : variant === "dark"
                ? "text-pug-green-700 dark:text-foreground"
                : "text-pug-green-700 dark:text-foreground"
            )}
          >
            PARIS UNITED GROUP
          </span>
          <span
            className={cn(
              "font-medium uppercase tracking-[0.32em]",
              WORDMARK_TAGLINE_SIZE[size],
              "text-pug-gold-600 dark:text-pug-gold-400"
            )}
          >
            Holding
          </span>
        </span>
      )}
    </Link>
  );
}

/** 8-petal lotus mandala matching the PUG brand mark. */
export function MandalaMark({
  className,
  variant = "auto",
}: {
  className?: string;
  variant?: LogoProps["variant"];
}) {
  // Resolve to a real CSS color via the gold class so dark/light both look
  // tasteful without needing prop drilling.
  const tone =
    variant === "light"
      ? "text-pug-gold-300"
      : variant === "dark"
      ? "text-pug-gold-600"
      : "text-pug-gold-600 dark:text-pug-gold-400";

  return (
    <svg
      viewBox="0 0 64 64"
      role="img"
      aria-hidden
      className={cn(tone, className)}
      fill="currentColor"
    >
      {/* 8 petals rotated around the centre */}
      <g transform="translate(32 32)">
        {Array.from({ length: 8 }).map((_, i) => (
          <g key={i} transform={`rotate(${i * 45})`}>
            {/* Outer petal */}
            <path
              d="M0 -28 C 5 -18 5 -8 0 -2 C -5 -8 -5 -18 0 -28 Z"
              opacity="0.95"
            />
          </g>
        ))}
        {/* 8 inner petals offset by 22.5deg */}
        {Array.from({ length: 8 }).map((_, i) => (
          <g key={`b-${i}`} transform={`rotate(${i * 45 + 22.5})`}>
            <path
              d="M0 -18 C 3 -12 3 -6 0 -2 C -3 -6 -3 -12 0 -18 Z"
              opacity="0.85"
            />
          </g>
        ))}
        {/* 4 small diamond accents on the diagonals */}
        {Array.from({ length: 4 }).map((_, i) => (
          <g key={`d-${i}`} transform={`rotate(${i * 90 + 45})`}>
            <path d="M0 -24 l 2 2 l -2 2 l -2 -2 z" opacity="0.95" />
          </g>
        ))}
        {/* Centre dot */}
        <circle r="2" />
      </g>
    </svg>
  );
}
