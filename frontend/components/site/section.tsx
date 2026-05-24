import * as React from "react";

import { cn } from "@/lib/utils";

interface SectionProps extends React.HTMLAttributes<HTMLElement> {
  /** Visually centered tag rendered above the heading. */
  eyebrow?: string;
  title?: string;
  description?: string;
  /** When true the title/description are centred. */
  centered?: boolean;
  containerClassName?: string;
}

/**
 * Page section wrapper used across the public site. Handles consistent
 * vertical spacing, the optional eyebrow / title / description block,
 * and the safe horizontal padding so children never overflow on
 * narrow viewports.
 */
export function Section({
  eyebrow,
  title,
  description,
  centered = false,
  className,
  containerClassName,
  children,
  ...props
}: SectionProps) {
  const hasHeader = eyebrow || title || description;
  return (
    <section className={cn("py-16 sm:py-20 lg:py-24", className)} {...props}>
      <div className={cn("container mx-auto px-4", containerClassName)}>
        {hasHeader && (
          <header
            className={cn(
              "mb-10 max-w-2xl space-y-3",
              centered && "mx-auto text-center"
            )}
          >
            {eyebrow && (
              <span className="inline-flex items-center rounded-full border border-border/60 bg-background/60 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                {eyebrow}
              </span>
            )}
            {title && (
              <h2 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl lg:text-4xl">
                {title}
              </h2>
            )}
            {description && (
              <p className="text-pretty text-base text-muted-foreground sm:text-lg">
                {description}
              </p>
            )}
          </header>
        )}
        {children}
      </div>
    </section>
  );
}
