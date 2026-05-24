import { resolveAssetUrl } from "@/lib/public-api";
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
  className?: string;
}

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
  className,
}: PageHeroProps) {
  const resolvedVideo = resolveAssetUrl(videoUrl ?? null);
  const resolvedImage = resolveAssetUrl(imageUrl ?? null);
  const resolvedMobile = resolveAssetUrl(mobileImageUrl ?? null);
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

      <div className="container mx-auto px-4 py-16 sm:py-20 lg:py-24">
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
