import { cn } from "@/lib/utils";

interface PageHeroProps {
  eyebrow?: string;
  title: string;
  description?: string;
  /** Tailwind gradient classes for the soft hero background. */
  accent?: string;
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
  children,
  centered = false,
  className,
}: PageHeroProps) {
  return (
    <section
      className={cn(
        "relative isolate overflow-hidden border-b border-border/60 bg-background",
        className
      )}
    >
      <div
        aria-hidden
        className={cn(
          "pointer-events-none absolute inset-0 -z-10 opacity-30 dark:opacity-25",
          "bg-gradient-to-br",
          accent
        )}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-64 bg-gradient-to-b from-background/0 via-background/40 to-background"
      />

      <div className="container mx-auto px-4 py-16 sm:py-20 lg:py-24">
        <div
          className={cn(
            "max-w-3xl space-y-4",
            centered && "mx-auto text-center"
          )}
        >
          {eyebrow && (
            <span className="inline-flex items-center rounded-full border border-border/60 bg-background/60 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground backdrop-blur">
              {eyebrow}
            </span>
          )}
          <h1 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">
            {title}
          </h1>
          {description && (
            <p className="text-pretty text-base text-muted-foreground sm:text-lg">
              {description}
            </p>
          )}
          {children && <div className="pt-2">{children}</div>}
        </div>
      </div>
    </section>
  );
}
