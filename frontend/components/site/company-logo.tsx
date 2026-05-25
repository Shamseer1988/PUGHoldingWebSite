import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";

/** Size presets shared by every place a company logo is rendered.
 *  Each preset picks both the wrapper size and the rounded-corner
 *  radius, so the gradient-initials fallback and the uploaded
 *  image visually match wherever they appear. */
const SIZE_PRESETS = {
  xs: {
    box: "h-9 w-9 rounded-lg",
    text: "text-xs",
    pad: "p-1",
  },
  sm: {
    box: "h-10 w-10 rounded-lg",
    text: "text-sm",
    pad: "p-1",
  },
  md: {
    box: "h-14 w-14 rounded-xl",
    text: "text-base",
    pad: "p-1.5",
  },
  lg: {
    box: "h-16 w-16 rounded-2xl",
    text: "text-lg",
    pad: "p-2",
  },
} as const;

export type CompanyLogoSize = keyof typeof SIZE_PRESETS;

interface CompanyLogoProps {
  /** Optional uploaded brand-logo URL. When present, the logo
   *  renders instead of the gradient initials tile. */
  logoUrl?: string | null;
  /** Initials fallback (1–8 chars) shown when no logo is set. */
  initials: string;
  /** Tailwind gradient classes for the initials fallback
   *  (e.g. "from-pug-green-500 to-pug-gold-500"). */
  accent: string;
  /** Company name — used as the logo image alt text. */
  name: string;
  size?: CompanyLogoSize;
  className?: string;
}

export function CompanyLogo({
  logoUrl,
  initials,
  accent,
  name,
  size = "md",
  className,
}: CompanyLogoProps) {
  const preset = SIZE_PRESETS[size];
  const resolved = resolveAssetUrl(logoUrl ?? null);

  if (resolved) {
    return (
      <span
        className={cn(
          "inline-flex shrink-0 items-center justify-center overflow-hidden border border-border/40 bg-white shadow-sm dark:bg-white",
          preset.box,
          preset.pad,
          className
        )}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={resolved}
          alt={`${name} logo`}
          loading="lazy"
          className="h-full w-full object-contain"
        />
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center bg-gradient-to-br font-bold tracking-wide text-white shadow-md",
        preset.box,
        preset.text,
        accent,
        className
      )}
      aria-hidden
    >
      {initials}
    </span>
  );
}
