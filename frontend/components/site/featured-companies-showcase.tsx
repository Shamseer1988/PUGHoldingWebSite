"use client";

import * as React from "react";
import Image from "next/image";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, Building2, Sparkles } from "lucide-react";

import type { Company } from "@/lib/admin/types";
import type { FeaturedSectionPayload } from "@/lib/public-api";
import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";

interface FeaturedCompaniesShowcaseProps {
  section: FeaturedSectionPayload;
  companies: Company[];
}

/**
 * Premium scroll-driven "Featured Companies" section.
 *
 * Desktop (≥ 1024px, motion allowed, admin toggle on):
 *   - Left column: one tall panel per company; user scrolls through.
 *   - Right column: a single preview frame that is `position: sticky`
 *     so it stays pinned next to whichever panel is currently centered.
 *   - GSAP ScrollTrigger detects which panel is "active" (center of
 *     viewport) and React swaps the visible image via opacity+scale.
 *
 * Mobile / reduced-motion / animation disabled:
 *   - Single-column stack. Each panel shows its own inline image
 *     below the text. No pinning, no sticky, no GSAP.
 *
 * Colours are theme-aware — base surface uses CSS variables so it
 * looks right in both light and dark mode.
 */
export function FeaturedCompaniesShowcase({
  section,
  companies,
}: FeaturedCompaniesShowcaseProps) {
  const panelRefs = React.useRef<(HTMLElement | null)[]>([]);
  const [activeIndex, setActiveIndex] = React.useState(0);

  // ---------------------------------------------------------------------
  // GSAP ScrollTrigger — per-panel active-state detection.
  // ---------------------------------------------------------------------
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    if (!section.animation_enabled) return;
    if (companies.length <= 1) return;

    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    const isDesktop = window.matchMedia("(min-width: 1024px)").matches;
    if (reducedMotion || !isDesktop) return;

    let cleanup: (() => void) | undefined;
    let cancelled = false;

    (async () => {
      const { gsap } = await import("gsap");
      const { ScrollTrigger } = await import("gsap/ScrollTrigger");
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);

      const triggers: InstanceType<typeof ScrollTrigger>[] = [];
      panelRefs.current.forEach((panel, i) => {
        if (!panel) return;
        triggers.push(
          ScrollTrigger.create({
            trigger: panel,
            start: "top center",
            end: "bottom center",
            // No markers / no scrub — just a callback flipping React state.
            onToggle: ({ isActive }) => {
              if (isActive) setActiveIndex(i);
            },
          })
        );

        // Highlight reveal: separate per-panel timeline that targets
        // the new "Company Highlight" card. Runs once when the panel
        // enters the viewport (start: "top 70%"). Stays independent
        // from the active-state trigger above so the two never fight.
        const eyebrow = panel.querySelector<HTMLElement>("[data-highlight-eyebrow]");
        const text = panel.querySelector<HTMLElement>("[data-highlight-text]");
        const chips = panel.querySelectorAll<HTMLElement>("[data-highlight-chip]");
        const accent = panel.querySelector<HTMLElement>("[data-highlight-accent]");
        const targets = [eyebrow, text, accent, ...Array.from(chips)].filter(
          (el): el is HTMLElement => Boolean(el)
        );
        if (targets.length === 0) return;

        gsap.set(targets, { opacity: 0, y: 18 });
        if (accent) gsap.set(accent, { scaleX: 0, transformOrigin: "left center" });

        const tl = gsap.timeline({
          scrollTrigger: {
            trigger: panel,
            start: "top 70%",
            end: "bottom 40%",
            once: true,
          },
          defaults: { ease: "power3.out" },
        });
        if (eyebrow) tl.to(eyebrow, { opacity: 1, y: 0, duration: 0.5 }, 0);
        if (text) tl.to(text, { opacity: 1, y: 0, duration: 0.55 }, 0.08);
        if (chips.length) {
          tl.to(
            chips,
            { opacity: 1, y: 0, duration: 0.45, stagger: 0.08 },
            0.18
          );
        }
        if (accent) {
          tl.to(
            accent,
            { opacity: 1, scaleX: 1, duration: 0.55, ease: "power2.out" },
            "-=0.25"
          );
        }
        // Hook the timeline's ScrollTrigger into the same cleanup
        // pool so unmount kills it alongside the active-panel
        // triggers above. Killing the trigger also stops the tween.
        if (tl.scrollTrigger) triggers.push(tl.scrollTrigger);
      });

      // Force initial evaluation so the active panel is correct
      // when the user lands mid-page (link to anchor, reload, etc.).
      const syncInitial = () => {
        for (let i = 0; i < triggers.length; i++) {
          if (triggers[i].isActive) {
            setActiveIndex(i);
            return;
          }
        }
      };
      syncInitial();

      // Recompute trigger positions after the layout settles. We do this
      // twice: once on the next frame (fonts + base CSS), and again on
      // window 'load' (images + late assets). A ResizeObserver also
      // refreshes whenever the section size changes (responsive flips).
      const refresh = () => {
        ScrollTrigger.refresh();
        syncInitial();
      };

      const raf1 = requestAnimationFrame(() => {
        const raf2 = requestAnimationFrame(refresh);
        (refresh as { _raf2?: number })._raf2 = raf2;
      });
      window.addEventListener("load", refresh);

      const ro = new ResizeObserver(refresh);
      panelRefs.current.forEach((panel) => panel && ro.observe(panel));

      cleanup = () => {
        cancelAnimationFrame(raf1);
        const raf2 = (refresh as { _raf2?: number })._raf2;
        if (raf2) cancelAnimationFrame(raf2);
        window.removeEventListener("load", refresh);
        ro.disconnect();
        triggers.forEach((t) => t.kill());
      };
    })();

    return () => {
      cancelled = true;
      if (cleanup) cleanup();
    };
  }, [companies.length, section.animation_enabled]);

  if (!section.enabled || companies.length === 0) return null;

  return (
    <section
      aria-label="Featured group companies"
      // NOTE: do NOT add overflow-hidden here — it would create a scroll
      // container that breaks `position: sticky` on the preview frame.
      // The decoration handles its own clipping locally.
      className={cn("relative isolate bg-background py-16 sm:py-20 lg:py-24")}
    >
      <BackgroundDecor />

      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <header className="mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center rounded-full border border-border/60 bg-background/60 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground backdrop-blur">
            {section.eyebrow ?? "Group companies"}
          </span>
          <h2 className="mt-5 text-balance text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">
            {section.title ?? "A diversified portfolio, one trusted group."}
          </h2>
          {section.subtitle && (
            <p className="mt-4 text-pretty text-base text-muted-foreground sm:text-lg">
              {section.subtitle}
            </p>
          )}
        </header>

        {/* Desktop split — left panels scroll, right preview sticks */}
        <div className="mt-12 hidden lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-14 xl:gap-20">
          {/* Left: scrolling panels */}
          <div>
            {companies.map((company, i) => (
              <CompanyPanel
                key={company.id}
                ref={(el) => {
                  panelRefs.current[i] = el;
                }}
                company={company}
                index={i}
                total={companies.length}
                isActive={i === activeIndex}
              />
            ))}
          </div>

          {/* Right: sticky preview */}
          <div className="relative">
            <div className="sticky top-24 h-[calc(100vh-8rem)] min-h-[520px]">
              <PreviewFrame>
                {companies.map((company, i) => (
                  <PreviewImage
                    key={company.id}
                    company={company}
                    isActive={i === activeIndex}
                  />
                ))}
              </PreviewFrame>
            </div>
          </div>
        </div>

        {/* Mobile / reduced-motion: simple stacked cards */}
        <div className="mt-10 space-y-6 lg:hidden">
          {companies.map((company, i) => (
            <MobileCompanyCard
              key={company.id}
              company={company}
              index={i}
              total={companies.length}
            />
          ))}
        </div>

        {section.cta_url && (
          <div className="mt-12 flex justify-center lg:mt-16">
            <Link
              href={section.cta_url}
              className={cn(
                "inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-transform hover:scale-[1.02]",
                "bg-primary text-primary-foreground shadow-sm"
              )}
            >
              {section.cta_label ?? "View all companies"}
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Left-panel: one full-height block per company
// ---------------------------------------------------------------------------

const CompanyPanel = React.forwardRef<
  HTMLElement,
  {
    company: Company;
    index: number;
    total: number;
    isActive: boolean;
  }
>(function CompanyPanel({ company, index, total, isActive }, ref) {
  const ctaHref =
    company.cta_url ?? company.website ?? `/companies/${company.slug}`;
  const ctaLabel = company.cta_label ?? "Explore the brand";
  const external = company.cta_url?.startsWith("http") ?? false;

  return (
    <article
      ref={ref}
      className={cn(
        "flex min-h-[78vh] flex-col justify-center border-t border-border/40 py-12 first:border-t-0 lg:min-h-screen lg:py-16",
        "transition-opacity duration-500",
        isActive ? "opacity-100" : "opacity-55"
      )}
      aria-current={isActive ? "true" : undefined}
    >
      <div className="flex items-center gap-3 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
        <span className="font-mono text-foreground/80">
          {String(index + 1).padStart(2, "0")}
          <span className="mx-1.5 text-muted-foreground/60">/</span>
          {String(total).padStart(2, "0")}
        </span>
        <span aria-hidden className="h-px flex-1 bg-border" />
        <span className="capitalize">{company.category}</span>
      </div>

      <div className="mt-6 flex items-center gap-3">
        <span
          className={cn(
            "inline-flex h-10 w-10 items-center justify-center rounded-lg text-sm font-bold text-white shadow-md",
            "bg-gradient-to-br",
            company.accent || "from-pug-green-600 to-pug-gold-500"
          )}
          aria-hidden
        >
          {company.initials}
        </span>
        {company.branches && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Building2 className="h-3.5 w-3.5" />
            {company.branches}
          </span>
        )}
      </div>

      <h3 className="mt-4 text-balance text-3xl font-semibold leading-tight tracking-tight sm:text-4xl lg:text-5xl">
        <span
          className={cn(
            "bg-gradient-to-r bg-clip-text",
            isActive
              ? "text-transparent from-pug-green-700 to-pug-gold-600 dark:from-pug-gold-200 dark:to-pug-green-300"
              : "text-foreground"
          )}
        >
          {company.name}
        </span>
      </h3>

      {company.short_description && (
        <p className="mt-4 max-w-xl text-pretty text-base text-muted-foreground sm:text-lg">
          {company.short_description}
        </p>
      )}

      {company.services.length > 0 && (
        <ul className="mt-5 flex flex-wrap gap-1.5">
          {company.services.slice(0, 4).map((service) => (
            <li
              key={service.id}
              className="rounded-full border border-border/60 bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur"
            >
              {service.name}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-7">
        <Link
          href={ctaHref}
          {...(external
            ? { target: "_blank", rel: "noopener noreferrer" }
            : {})}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold transition-colors",
            isActive
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "border border-border/60 bg-background/60 text-foreground hover:bg-muted"
          )}
        >
          {ctaLabel}
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      <CompanyHighlight company={company} className="mt-8" />
      <CompanyStatLine company={company} />
    </article>
  );
});


// ---------------------------------------------------------------------------
// Company highlight card
// Fills the previously-empty space below the CTA inside every panel.
// Backend-controlled: prefers `homepage_highlight_description`, falls
// back to a trimmed `long_description`, then `short_description`.
// Chips prefer `homepage_highlight_points` (newline list), fall back
// to the company's services. Returns null when there's nothing to
// show so the panel still renders cleanly.
// ---------------------------------------------------------------------------

const HIGHLIGHT_MAX_CHARS = 280;

function trimLongDescription(value: string): string {
  if (value.length <= HIGHLIGHT_MAX_CHARS) return value;
  const slice = value.slice(0, HIGHLIGHT_MAX_CHARS);
  // Cut on the last sentence boundary if possible, else on the last
  // word boundary, else hard-cut. Append an ellipsis only when we
  // actually shortened.
  const lastSentence = Math.max(
    slice.lastIndexOf(". "),
    slice.lastIndexOf("! "),
    slice.lastIndexOf("? ")
  );
  if (lastSentence > HIGHLIGHT_MAX_CHARS * 0.6) {
    return `${slice.slice(0, lastSentence + 1).trimEnd()}`;
  }
  const lastSpace = slice.lastIndexOf(" ");
  if (lastSpace > 0) return `${slice.slice(0, lastSpace).trimEnd()}…`;
  return `${slice.trimEnd()}…`;
}

function resolveHighlightDescription(company: Company): string | null {
  // Phase 18 follow-up — prefer the new admin field, then fall back to
  // the existing homepage_highlight_description, then trim long, then
  // short. Keeps existing rows working without any data migration.
  const groupHighlight = company.homepage_group_highlight?.trim();
  if (groupHighlight) return groupHighlight;
  const explicit = company.homepage_highlight_description?.trim();
  if (explicit) return explicit;
  const long = company.long_description?.trim();
  if (long) return trimLongDescription(long);
  const short = company.short_description?.trim();
  if (short) return short;
  return null;
}

function resolveHighlightPoints(company: Company): string[] {
  const explicit = company.homepage_highlight_points?.trim();
  if (explicit) {
    return explicit
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(0, 3);
  }
  return company.services.slice(0, 3).map((s) => s.name);
}

/** Pulls the names used for the marquee. Prefers explicit highlight
 *  points (so admins can drive the strip), falls back to the company's
 *  services so the strip never sits empty when the admin hasn't curated
 *  a list yet. Returns at most 8 items — the marquee duplicates the
 *  list inline so 8 unique entries already produce a long, smooth
 *  loop without becoming visually noisy. */
function resolveBrandStripItems(company: Company): string[] {
  const explicit = company.homepage_highlight_points?.trim();
  const fromExplicit = explicit
    ? explicit
        .split(/\r?\n/)
        .map((s) => s.trim())
        .filter(Boolean)
    : [];
  const fromServices = company.services.map((s) => s.name);
  // Dedupe + cap. Order: explicit first, then services so admin
  // overrides take precedence visually.
  const seen = new Set<string>();
  const merged: string[] = [];
  for (const item of [...fromExplicit, ...fromServices]) {
    const key = item.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
    if (merged.length >= 8) break;
  }
  return merged;
}

/** Eyebrow label switches based on what's actually rendered inside.
 *  The spec wants three modes:
 *    - "COMPANY HIGHLIGHT" — pure description card (default)
 *    - "GROUP BRANDS"       — description + sub-brand / service marquee
 *    - "TRUSTED PARTNERS"   — partner-only mode (no description)
 *  We pick the label deterministically from the rendered content so a
 *  single backend field can drive all three without an extra toggle. */
function resolveHighlightEyebrow(opts: {
  description: string | null;
  marquee: string[];
}): string {
  if (!opts.description && opts.marquee.length > 0) return "Trusted Partners";
  if (opts.marquee.length > 0) return "Group Brands";
  return "Company Highlight";
}

function CompanyHighlight({
  company,
  className,
}: {
  company: Company;
  className?: string;
}) {
  const description = resolveHighlightDescription(company);
  const points = resolveHighlightPoints(company);
  // Marquee draws from services / explicit points. Only render the
  // strip when we have enough items to make scrolling meaningful (>=2);
  // a single item would just sit static.
  const marqueeItems = resolveBrandStripItems(company);
  const showMarquee = marqueeItems.length >= 2;
  const eyebrow = resolveHighlightEyebrow({
    description,
    marquee: showMarquee ? marqueeItems : [],
  });
  if (!description && points.length === 0 && !showMarquee) return null;

  return (
    <aside
      aria-label="Company highlight"
      className={cn(
        // Glassmorphism card — same surface language as the rest of
        // the public site. Light/dark via existing tokens.
        "relative overflow-hidden rounded-3xl border border-pug-gold-500/15 bg-white/70 p-5 shadow-[0_4px_30px_-18px_rgba(15,42,28,0.18)] backdrop-blur-sm sm:p-6",
        "dark:border-white/10 dark:bg-white/[0.04] dark:shadow-[0_4px_30px_-18px_rgba(0,0,0,0.6)]",
        className
      )}
    >
      <p
        data-highlight-eyebrow
        className="inline-flex items-center gap-1.5 rounded-full border border-pug-gold-500/25 bg-pug-gold-500/10 px-2.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.18em] text-pug-gold-700 dark:text-pug-gold-300"
      >
        <Sparkles className="h-3 w-3" aria-hidden />
        {eyebrow}
      </p>

      {description && (
        <p
          data-highlight-text
          className="mt-4 text-pretty text-sm leading-relaxed text-foreground/80 sm:text-base"
        >
          {description}
        </p>
      )}

      {points.length > 0 && (
        <ul className="mt-4 flex flex-wrap gap-1.5">
          {points.map((point) => (
            <li
              key={point}
              data-highlight-chip
              className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-pug-green-900/[0.08] bg-background/60 px-3 py-1 text-xs font-medium text-foreground/80 dark:border-white/10"
            >
              <span
                aria-hidden
                className="inline-block h-1 w-1 shrink-0 rounded-full bg-pug-gold-500"
              />
              <span className="truncate">{point}</span>
            </li>
          ))}
        </ul>
      )}

      {showMarquee && <BrandLogoMarquee items={marqueeItems} />}

      <span
        aria-hidden
        data-highlight-accent
        className="mt-5 block h-px w-20 bg-gradient-to-r from-pug-gold-500 to-pug-gold-500/0"
      />
    </aside>
  );
}


/** Pure-CSS marquee of text "logos". The list is duplicated inline so
 *  the keyframe can translate `-50%` for a seamless loop. The track is
 *  paused on hover; `prefers-reduced-motion` cancels the animation in
 *  globals.css so users who opt out see a static row instead. */
function BrandLogoMarquee({ items }: { items: string[] }) {
  // Render the list twice so translating the track by -50% lands the
  // second copy in the exact position of the first — a seamless loop.
  return (
    <div className="brand-marquee mt-5">
      <div className="brand-marquee__track" aria-hidden>
        {[...items, ...items].map((label, i) => (
          <span
            key={`${label}-${i}`}
            className="brand-marquee__chip"
          >
            {label}
          </span>
        ))}
      </div>
      {/* SR-friendly list mirroring the visible marquee */}
      <ul className="sr-only">
        {items.map((label) => (
          <li key={label}>{label}</li>
        ))}
      </ul>
    </div>
  );
}


/** Single-line stat strip rendered below the card. Driven purely by
 *  `homepage_group_stat_line` so the admin can decide whether to show
 *  it at all. Returns null when the field is empty. */
function CompanyStatLine({ company }: { company: Company }) {
  const line = company.homepage_group_stat_line?.trim();
  if (!line) return null;
  return (
    <p
      className="mt-4 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground"
      data-highlight-statline
    >
      {line}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Sticky preview frame on the right
// ---------------------------------------------------------------------------

function PreviewFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "relative h-full overflow-hidden rounded-3xl border border-border/60 bg-card p-3",
        "shadow-[0_30px_80px_-30px_rgba(0,0,0,0.25)] dark:shadow-[0_30px_80px_-30px_rgba(0,0,0,0.6)]"
      )}
    >
      {/* Browser chrome dots */}
      <div className="flex items-center gap-1.5 px-2 py-1.5">
        <span className="h-2 w-2 rounded-full bg-foreground/15" />
        <span className="h-2 w-2 rounded-full bg-foreground/10" />
        <span className="h-2 w-2 rounded-full bg-foreground/[0.07]" />
      </div>
      <div className="relative h-[calc(100%-1.75rem)] overflow-hidden rounded-2xl bg-muted/40">
        {children}
      </div>
    </div>
  );
}

function PreviewImage({
  company,
  isActive,
}: {
  company: Company;
  isActive: boolean;
}) {
  const featured = resolveAssetUrl(company.featured_image_url);

  return (
    <div
      className={cn(
        "absolute inset-0 transition-all duration-500 ease-out",
        isActive
          ? "opacity-100 scale-100 pointer-events-auto"
          : "opacity-0 scale-[0.97] pointer-events-none"
      )}
      aria-hidden={!isActive}
    >
      {featured ? (
        <Image
          src={featured}
          alt=""
          fill
          sizes="(max-width: 1024px) 100vw, 720px"
          className="object-cover"
          unoptimized
          priority={isActive}
        />
      ) : (
        <div
          aria-hidden
          className={cn(
            "absolute inset-0 bg-gradient-to-br",
            company.accent || "from-pug-green-600 to-pug-gold-500"
          )}
        />
      )}

      {/* Bottom gradient overlay for legibility */}
      <div
        aria-hidden
        className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/70 via-black/30 to-transparent"
      />

      {/* Caption bar */}
      <div className="absolute inset-x-0 bottom-0 p-5 text-white sm:p-6">
        <span className="inline-flex items-center rounded-full border border-white/25 bg-white/10 px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.18em] backdrop-blur">
          {company.category}
        </span>
        <h4 className="mt-2 text-xl font-semibold leading-tight tracking-tight sm:text-2xl">
          {company.name}
        </h4>
        {company.short_description && (
          <p className="mt-1 line-clamp-2 max-w-xl text-sm text-white/85">
            {company.short_description}
          </p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mobile card (one per company, image inline)
// ---------------------------------------------------------------------------

function MobileCompanyCard({
  company,
  index,
  total,
}: {
  company: Company;
  index: number;
  total: number;
}) {
  const featured = resolveAssetUrl(company.featured_image_url);
  const ctaHref =
    company.cta_url ?? company.website ?? `/companies/${company.slug}`;
  const ctaLabel = company.cta_label ?? "Explore";
  const external = company.cta_url?.startsWith("http") ?? false;

  return (
    <article className="overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm">
      <div className="relative aspect-[5/3] w-full overflow-hidden">
        {featured ? (
          <Image
            src={featured}
            alt=""
            fill
            sizes="100vw"
            className="object-cover"
            unoptimized
          />
        ) : (
          <div
            aria-hidden
            className={cn(
              "absolute inset-0 bg-gradient-to-br",
              company.accent || "from-pug-green-600 to-pug-gold-500"
            )}
          />
        )}
        <div
          aria-hidden
          className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent"
        />
        <div className="absolute inset-x-0 bottom-0 p-4 text-white">
          <span className="font-mono text-xs text-white/80">
            {String(index + 1).padStart(2, "0")}
            <span className="mx-1.5 text-white/40">/</span>
            {String(total).padStart(2, "0")}
          </span>
          <h3 className="mt-1 text-lg font-semibold leading-tight">
            {company.name}
          </h3>
        </div>
      </div>

      <div className="p-5">
        {company.short_description && (
          <p className="text-sm text-muted-foreground">
            {company.short_description}
          </p>
        )}
        {company.services.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {company.services.slice(0, 3).map((service) => (
              <li
                key={service.id}
                className="rounded-full border border-border/60 bg-background/60 px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
              >
                {service.name}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-4">
          <Link
            href={ctaHref}
            {...(external
              ? { target: "_blank", rel: "noopener noreferrer" }
              : {})}
            className="inline-flex items-center gap-1.5 rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
          >
            {ctaLabel}
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {/* Mobile: render the highlight card too. No GSAP reveal here
            — the section uses CSS-only fade-in to keep scroll perf
            cheap on phones; targets behind data-highlight-* still
            get the GSAP setup on desktop but on mobile the effect
            short-circuits because reducedMotion / !isDesktop returns
            early up top. */}
        <CompanyHighlight company={company} className="mt-5" />
        <CompanyStatLine company={company} />
      </div>
    </article>
  );
}

// ---------------------------------------------------------------------------
// Decorative background (theme-aware)
// ---------------------------------------------------------------------------

function BackgroundDecor() {
  // `overflow: clip` (with hidden fallback) locally clips the decoration
  // without creating a scroll container, so the sticky preview frame
  // higher up the tree still anchors to the viewport.
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 -z-10"
      style={{ overflow: "clip" }}
    >
      <div
        className="absolute -left-40 top-20 h-[28rem] w-[28rem] rounded-full opacity-30 blur-3xl dark:opacity-25"
        style={{ background: "hsl(36 60% 55% / 0.35)" }}
      />
      <div
        className="absolute right-[-12rem] bottom-10 h-[32rem] w-[32rem] rounded-full opacity-25 blur-3xl dark:opacity-20"
        style={{ background: "hsl(145 60% 35% / 0.45)" }}
      />
      <div
        className="absolute inset-0 opacity-[0.025] dark:opacity-[0.04]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)",
          backgroundSize: "32px 32px",
          color: "var(--tw-prose-body, currentColor)",
        }}
      />
    </div>
  );
}
