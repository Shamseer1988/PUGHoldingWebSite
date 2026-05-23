import Link from "next/link";

import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
  /** Show the full word-mark beside the icon. */
  showWordmark?: boolean;
  /** Where the logo should link to. */
  href?: string;
}

/**
 * Placeholder PUG mark.
 *
 * Phase 5/6 will let the website admin upload a real logo and we will
 * swap the inline SVG for an <Image /> served from the backend.
 */
export function Logo({
  className,
  showWordmark = true,
  href = "/",
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
      <span className="relative inline-flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl bg-gradient-to-br from-primary via-fuchsia-500 to-emerald-400 text-primary-foreground shadow-sm transition-transform group-hover:scale-105">
        <span className="text-sm font-bold">PUG</span>
        <span
          aria-hidden
          className="absolute inset-0 bg-gradient-to-tr from-white/0 via-white/30 to-white/0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        />
      </span>
      {showWordmark && (
        <span className="hidden flex-col leading-tight sm:flex">
          <span className="text-sm font-semibold">Paris United Group</span>
          <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Holding
          </span>
        </span>
      )}
    </Link>
  );
}
