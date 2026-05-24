"use client";

import * as React from "react";
import Image from "next/image";
import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";

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
 * Desktop (>= 1024px, motion allowed):
 *   - The whole section pins for ~100vh per company while the
 *     stacked preview cards on the right scrub from one to the next.
 *   - The left column updates the small "01 / 04" pager + a
 *     subtle progress bar.
 *
 * Mobile / reduced-motion:
 *   - Cards stack vertically below the heading. No pinning, no
 *     scroll-bound animation. Each card fades+lifts in once.
 */
export function FeaturedCompaniesShowcase({
  section,
  companies,
}: FeaturedCompaniesShowcaseProps) {
  const rootRef = React.useRef<HTMLDivElement | null>(null);
  const cardRefs = React.useRef<(HTMLDivElement | null)[]>([]);
  const progressRef = React.useRef<HTMLDivElement | null>(null);
  const counterRef = React.useRef<HTMLSpanElement | null>(null);

  const [activeIndex, setActiveIndex] = React.useState(0);

  const total = companies.length;

  // ---------------------------------------------------------------------
  // GSAP ScrollTrigger — desktop only, respects prefers-reduced-motion,
  // and only runs when the admin enabled the animation toggle.
  // ---------------------------------------------------------------------
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    if (!section.animation_enabled) return;
    if (companies.length === 0) return;

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

      const root = rootRef.current;
      const cards = cardRefs.current.filter(
        (c): c is HTMLDivElement => Boolean(c)
      );
      const progress = progressRef.current;
      const counter = counterRef.current;
      if (!root || cards.length === 0) return;

      const ctx = gsap.context(() => {
        // Start with only the first card visible.
        gsap.set(cards, {
          opacity: 0,
          y: 60,
          scale: 0.97,
          pointerEvents: "none",
        });
        gsap.set(cards[0], {
          opacity: 1,
          y: 0,
          scale: 1,
          pointerEvents: "auto",
        });

        // ~100vh of scroll per card after the first.
        const distance = 100 * (cards.length - 1);

        const tl = gsap.timeline({
          scrollTrigger: {
            trigger: root,
            start: "top top",
            end: () => `+=${distance * window.innerHeight / 100}`,
            pin: true,
            scrub: 0.6,
            anticipatePin: 1,
            onUpdate: (self) => {
              const idx = Math.min(
                cards.length - 1,
                Math.round(self.progress * (cards.length - 1))
              );
              setActiveIndex(idx);
              if (counter) {
                counter.textContent = String(idx + 1).padStart(2, "0");
              }
              if (progress) {
                progress.style.transform = `scaleX(${self.progress})`;
              }
            },
          },
        });

        for (let i = 1; i < cards.length; i++) {
          const prev = cards[i - 1];
          const next = cards[i];
          tl
            .to(
              prev,
              {
                opacity: 0,
                y: -60,
                scale: 0.96,
                pointerEvents: "none",
                duration: 1,
                ease: "power2.inOut",
              },
              i - 1
            )
            .fromTo(
              next,
              { opacity: 0, y: 80, scale: 0.97, pointerEvents: "none" },
              {
                opacity: 1,
                y: 0,
                scale: 1,
                pointerEvents: "auto",
                duration: 1,
                ease: "power2.out",
              },
              i - 1 + 0.1
            );
        }
      }, root);

      // Recompute pin distances once images settle.
      const refresh = () => ScrollTrigger.refresh();
      window.addEventListener("load", refresh);

      cleanup = () => {
        window.removeEventListener("load", refresh);
        ctx.revert();
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
      ref={rootRef}
      aria-label="Featured group companies"
      className={cn(
        "relative isolate overflow-hidden",
        // Dark luxury background that picks up the brand greens with a
        // warm gold radial glow.
        "bg-gradient-to-b from-pug-green-900 via-pug-green-800 to-[hsl(145_60%_6%)]",
        "text-white"
      )}
    >
      <BackgroundDecor />

      {/* The pinned viewport: 100vh tall when ScrollTrigger pins it. */}
      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-16 sm:px-6 lg:flex-row lg:items-center lg:gap-12 lg:px-8 lg:py-0">
        {/* Left column — sticky text + pager */}
        <div className="relative lg:w-[44%] lg:py-24">
          <span className="inline-flex items-center rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-white/80 backdrop-blur">
            {section.eyebrow ?? "Group companies"}
          </span>
          <h2 className="mt-5 text-balance text-3xl font-semibold leading-[1.1] tracking-tight sm:text-4xl lg:text-5xl">
            {section.title ?? "A diversified portfolio."}
          </h2>
          {section.subtitle && (
            <p className="mt-4 max-w-xl text-pretty text-base text-white/80 sm:text-lg">
              {section.subtitle}
            </p>
          )}

          {section.cta_url && (
            <Link
              href={section.cta_url}
              className={cn(
                "mt-7 inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold",
                "bg-white text-pug-green-900 transition-transform hover:scale-[1.02]",
                "shadow-[0_0_0_1px_rgba(255,255,255,0.2)]"
              )}
            >
              {section.cta_label ?? "View all companies"}
              <ArrowRight className="h-4 w-4" />
            </Link>
          )}

          {/* Pager + progress bar (visible on desktop). */}
          <div className="mt-10 hidden items-center gap-4 lg:flex">
            <span className="font-mono text-sm tabular-nums text-white/90">
              <span ref={counterRef}>01</span>
              <span className="mx-1.5 text-white/40">/</span>
              <span>{String(total).padStart(2, "0")}</span>
            </span>
            <div className="h-px flex-1 max-w-[180px] overflow-hidden bg-white/15">
              <div
                ref={progressRef}
                className="h-full origin-left bg-gradient-to-r from-pug-gold-400 to-pug-gold-200"
                style={{ transform: "scaleX(0)" }}
                aria-hidden
              />
            </div>
          </div>

          {/* Compact pager dots (visible on mobile too). */}
          <ul className="mt-8 flex flex-wrap gap-1.5 lg:hidden">
            {companies.map((_, i) => (
              <li
                key={i}
                className={cn(
                  "h-1.5 rounded-full transition-all",
                  i === activeIndex
                    ? "w-8 bg-pug-gold-400"
                    : "w-1.5 bg-white/30"
                )}
              />
            ))}
          </ul>
        </div>

        {/* Right column — preview frame with the stacked cards */}
        <div className="relative mt-10 flex-1 lg:mt-0">
          <PreviewFrame>
            {/* Desktop / motion-on: cards stacked, GSAP animates them. */}
            <div className="relative hidden h-full lg:block">
              {companies.map((company, i) => (
                <div
                  key={company.id}
                  ref={(el) => {
                    cardRefs.current[i] = el;
                  }}
                  className="absolute inset-0"
                  aria-hidden={i !== activeIndex}
                >
                  <CompanyCard company={company} />
                </div>
              ))}
            </div>

            {/* Mobile / reduced motion: simple stack, no overlay positioning. */}
            <div className="space-y-4 lg:hidden">
              {companies.map((company) => (
                <CompanyCard key={company.id} company={company} compact />
              ))}
            </div>
          </PreviewFrame>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function BackgroundDecor() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div
        className="absolute -left-32 top-1/4 h-96 w-96 rounded-full opacity-30 blur-3xl"
        style={{ background: "hsl(36 60% 50% / 0.45)" }}
      />
      <div
        className="absolute right-[-10%] bottom-[-10%] h-[28rem] w-[28rem] rounded-full opacity-25 blur-3xl"
        style={{ background: "hsl(145 70% 30% / 0.5)" }}
      />
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.6) 1px, transparent 0)",
          backgroundSize: "32px 32px",
        }}
      />
    </div>
  );
}

function PreviewFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.04] p-3 backdrop-blur-xl",
        "shadow-[0_30px_80px_-30px_rgba(0,0,0,0.6)]",
        // Frame height matches the pinned viewport on desktop, with
        // an aspect ratio fallback on mobile.
        "min-h-[420px] sm:min-h-[480px] lg:h-[72vh] lg:min-h-[520px]"
      )}
    >
      {/* fake browser chrome dots */}
      <div className="flex items-center gap-1.5 px-2 py-1.5">
        <span className="h-2 w-2 rounded-full bg-white/30" />
        <span className="h-2 w-2 rounded-full bg-white/20" />
        <span className="h-2 w-2 rounded-full bg-white/15" />
      </div>
      <div className="relative h-[calc(100%-1.75rem)] overflow-hidden rounded-2xl bg-pug-green-900/40">
        {children}
      </div>
    </div>
  );
}

function CompanyCard({
  company,
  compact = false,
}: {
  company: Company;
  compact?: boolean;
}) {
  const featuredImage = resolveAssetUrl(company.featured_image_url);
  const ctaHref =
    company.cta_url ?? company.website ?? `/companies/${company.slug}`;
  const ctaLabel = company.cta_label ?? "Explore the brand";

  return (
    <article
      className={cn(
        "group relative h-full overflow-hidden rounded-2xl",
        compact && "min-h-[280px]"
      )}
    >
      {/* Backdrop: real image if uploaded, else the brand accent gradient */}
      {featuredImage ? (
        <Image
          src={featuredImage}
          alt=""
          fill
          sizes="(max-width: 1024px) 100vw, 700px"
          className="object-cover"
          unoptimized
          priority={false}
        />
      ) : (
        <div
          aria-hidden
          className={cn(
            "absolute inset-0 bg-gradient-to-br",
            company.accent || "from-pug-green-700 to-pug-gold-500"
          )}
        />
      )}

      {/* Gradient overlay for legibility */}
      <div
        aria-hidden
        className="absolute inset-0 bg-gradient-to-t from-pug-green-900/95 via-pug-green-900/60 to-pug-green-900/10"
      />

      {/* Content */}
      <div className="relative flex h-full flex-col justify-end p-6 sm:p-8">
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "inline-flex h-10 w-10 items-center justify-center rounded-lg text-sm font-bold text-white shadow-md",
              "bg-gradient-to-br",
              company.accent || "from-pug-green-700 to-pug-gold-500"
            )}
            aria-hidden
          >
            {company.initials}
          </span>
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-white/70">
            {company.category}
          </span>
        </div>

        <h3 className="mt-4 text-balance text-2xl font-semibold leading-tight tracking-tight text-white sm:text-3xl">
          {company.name}
        </h3>

        {company.short_description && (
          <p className="mt-2 max-w-xl text-pretty text-sm text-white/80 sm:text-base">
            {company.short_description}
          </p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Link
            href={ctaHref}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold",
              "bg-white text-pug-green-900 transition-transform hover:scale-[1.02]"
            )}
            {...(company.cta_url?.startsWith("http")
              ? { target: "_blank", rel: "noopener noreferrer" }
              : {})}
          >
            {ctaLabel}
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
          {company.branches && (
            <span className="text-xs text-white/70">{company.branches}</span>
          )}
        </div>
      </div>
    </article>
  );
}
