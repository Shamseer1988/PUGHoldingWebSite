import { normaliseMediaUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";

interface PageHeroProps {
  eyebrow?: string;
  title: string;
  description?: string;
  /** Tailwind gradient classes for the soft hero background. */
  accent?: string;
  /** Optional banner image (used as the main background when set). */
  imageUrl?: string | null;
  /** Optional mobile-tuned banner image (shown < sm). */
  mobileImageUrl?: string | null;
  /** Optional looping background video. Overrides the image when present. */
  videoUrl?: string | null;
  /** Optional content rendered below the description (CTAs etc.). */
  children?: React.ReactNode;
  /** Centre the heading + description. */
  centered?: boolean;
  /**
   * Vertical scale of the hero.
   *
   *   - ``default`` (current behaviour, used by ~13 pages): tall
   *     statement banner with ``py-16 sm:py-20 lg:py-24`` so the
   *     hero anchors the page's first scroll-fold.
   *   - ``compact``: roughly half the vertical padding
   *     (``py-8 sm:py-10 lg:py-12``). Used by the Offers landing
   *     where the hero is followed immediately by an interactive
   *     filter bar — the operator wants the campaigns above the
   *     fold, not the hero.
   *
   * Default keeps the exact pre-existing class string so the other
   * pages (companies / careers / news / media / about / contact /
   * terms / privacy …) stay pixel-identical.
   */
  size?: "default" | "compact";
  className?: string;
}


// Inner-padding presets per ``size``. Kept as constants so the
// vitest can assert the exact class strings haven't drifted.
const HERO_PADDING: Record<NonNullable<PageHeroProps["size"]>, string> = {
  default: "py-16 sm:py-20 lg:py-24",
  compact: "py-8 sm:py-10 lg:py-12",
};


/**
 * Standard banner used at the top of every secondary public page.
 */
export function PageHero({
  eyebrow,
  title,
  description,
  accent = "from-indigo-600 via-blue-500 to-cyan-400",
  imageUrl,
  mobileImageUrl,
  videoUrl,
  children,
  centered = false,
  size = "default",
  className,
}: PageHeroProps) {
  const resolvedVideo = normaliseMediaUrl(videoUrl ?? null);
  const resolvedImage = normaliseMediaUrl(imageUrl ?? null);
  const resolvedMobile = normaliseMediaUrl(mobileImageUrl ?? null);
  const hasMedia = Boolean(resolvedVideo || resolvedImage);

  return (
    <section
      className={cn(
        "relative isolate overflow-hidden border-b border-border/60 bg-background",
        hasMedia && "text-white",
        className
      )}
    >
      {/* Background media (video > image > gradient) */}
      {resolvedVideo ? (
        <video
          aria-hidden
          src={resolvedVideo}
          autoPlay
          loop
          muted
          playsInline
          preload="metadata"
          poster={resolvedImage ?? undefined}
          className="pointer-events-none absolute inset-0 -z-10 h-full w-full object-cover"
        />
      ) : resolvedImage ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            aria-hidden
            src={resolvedImage}
            alt=""
            // LCP optimisation: this is the hero — fetch it eagerly and
            // with high priority. The browser still respects the
            // ``hidden sm:block`` so only the visible variant takes
            // bandwidth on each breakpoint.
            loading="eager"
            decoding="async"
            // @ts-expect-error — fetchPriority is a valid HTML attr in
            // React 18+ but the typings haven't caught up everywhere.
            fetchpriority="high"
            className={cn(
              "pointer-events-none absolute inset-0 -z-10 h-full w-full object-cover",
              resolvedMobile && "hidden sm:block"
            )}
          />
          {resolvedMobile && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              aria-hidden
              src={resolvedMobile}
              alt=""
              loading="eager"
              decoding="async"
              // @ts-expect-error — see note above
              fetchpriority="high"
              className="pointer-events-none absolute inset-0 -z-10 h-full w-full object-cover sm:hidden"
            />
          )}
        </>
      ) : (
        <div
          aria-hidden
          className={cn(
            "pointer-events-none absolute inset-0 -z-10 opacity-30 dark:opacity-25",
            "bg-gradient-to-br",
            accent
          )}
        />
      )}

      {/* Overlays */}
      {hasMedia && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-br from-pug-green-900/75 via-pug-green-800/55 to-pug-gold-700/40"
        />
      )}
      {!hasMedia && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-64 bg-gradient-to-b from-background/0 via-background/40 to-background"
        />
      )}

      <div className={cn("container mx-auto px-4", HERO_PADDING[size])}>
        <div
          className={cn(
            "max-w-3xl space-y-4",
            centered && "mx-auto text-center"
          )}
        >
          {eyebrow && (
            <span
              className={cn(
                "inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] backdrop-blur",
                hasMedia
                  ? "border-white/30 bg-white/10 text-white"
                  : "border-border/60 bg-background/60 text-muted-foreground"
              )}
            >
              {eyebrow}
            </span>
          )}
          <h1
            className={cn(
              "text-balance text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl",
              hasMedia && "drop-shadow-sm"
            )}
          >
            {title}
          </h1>
          {description && (
            <p
              className={cn(
                "text-pretty text-base sm:text-lg",
                hasMedia ? "text-white/90" : "text-muted-foreground"
              )}
            >
              {description}
            </p>
          )}
          {children && <div className="pt-2">{children}</div>}
        </div>
      </div>
    </section>
  );
}
