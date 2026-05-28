"use client";

import * as React from "react";
import Link from "next/link";
import { motion, useReducedMotion, type Variants } from "framer-motion";
import { Sparkles } from "lucide-react";

import { Section } from "@/components/site/section";
import {
  normaliseMediaUrl,
  type HomepageTrustedBrand,
  type HomepageTrustedBrandsSection,
} from "@/lib/public-api";
import { cn } from "@/lib/utils";

// Phase B-5 — framer-motion variants replacing the previous GSAP
// timeline. Header → accent → panel → tiles, with each tile staggered
// by 80ms. Matches the old "Luxury Brand Reveal" sequence at the same
// durations + offsets so the visual feel is unchanged.
const REVEAL_EASE = [0.16, 1, 0.3, 1] as const;
const SOFT_EASE = [0.33, 1, 0.68, 1] as const;

const HEADER_VARIANTS: Variants = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.7, ease: REVEAL_EASE } },
};

const ACCENT_VARIANTS: Variants = {
  hidden: { scaleX: 0 },
  visible: {
    scaleX: 1,
    transition: { duration: 0.9, ease: SOFT_EASE, delay: 0.1 },
  },
};

const PANEL_VARIANTS: Variants = {
  hidden: { opacity: 0, y: 40, scale: 0.98 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.8, ease: REVEAL_EASE, delay: 0.2 },
  },
};

const TILES_CONTAINER_VARIANTS: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.35 } },
};

const TILE_VARIANTS: Variants = {
  hidden: { opacity: 0, y: 24, scale: 0.94 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.6, ease: REVEAL_EASE },
  },
};


interface TrustedBrandsSectionProps {
  data: HomepageTrustedBrandsSection;
}

/**
 * Premium dark luxury "Trusted Brands We Work With" showcase.
 *
 * Replaces the old grayscale logo strip with a brand wall built on a
 * deep black-green / charcoal surface, gold accents, and an emerald
 * radial glow. Three layout modes from admin:
 *
 *   - `marquee` (default): two infinitely looping rows that pause on
 *     hover. Great for ten or more logos.
 *   - `grid`: balanced 2–5-column grid that staggers in on scroll.
 *     Best when the admin curates ≤ 12 brands and wants every tile
 *     visible at once.
 *   - `carousel`: center-focused row that horizontally scrolls on
 *     small screens and lays flat on desktop. Useful for ≤ 8 brands.
 *
 * Animation — "Luxury Brand Reveal":
 *   - Section header fades up first (y:30 → 0, opacity 0 → 1).
 *   - The decorative gold accent line under the title sweeps in
 *     (scaleX 0 → 1, transformOrigin left).
 *   - The main panel reveals with a soft scale-up (y:40 → 0,
 *     scale:0.98 → 1).
 *   - Each logo tile staggers up (y:24 → 0, opacity 0 → 1,
 *     scale:0.94 → 1, stagger:0.08).
 *   - The radial background glow drifts slowly with scroll (scrubbed
 *     xPercent / yPercent, never the main reveal).
 *
 * Respects `prefers-reduced-motion` and the admin `animation_enabled`
 * toggle. Hides itself entirely when the section is disabled or no
 * active brands exist.
 */
export function TrustedBrandsSection({ data }: TrustedBrandsSectionProps) {
  const prefersReducedMotion = useReducedMotion();

  const brands = React.useMemo(
    () => data.brands.filter((b) => b.is_active),
    [data.brands]
  );

  const layoutMode: HomepageTrustedBrandsSection["layout_mode"] =
    data.layout_mode === "grid" || data.layout_mode === "carousel"
      ? data.layout_mode
      : "marquee";

  // Reduced motion + admin off → render at the final state on first
  // paint. Otherwise the section orchestrates a top-down reveal via
  // its variant tree (see HEADER_VARIANTS etc. above).
  const animationsOff = !data.animation_enabled || prefersReducedMotion;
  const initial = animationsOff ? "visible" : "hidden";

  if (!data.enabled || brands.length === 0) return null;

  return (
    <Section
      className={cn(
        "trusted-brands-section relative overflow-hidden py-16 sm:py-24",
        // The section itself has NO background — it sits transparently
        // on top of the page's global background like every other
        // homepage section. Only the inner panel + tiles carry color.
        // Light-theme tokens for the panel + tiles + gold accents.
        "[--tb-panel-bg:rgba(255,255,255,0.78)]",
        "[--tb-panel-bg-strong:rgba(255,255,255,0.92)]",
        "[--tb-gold:#a3812d]",
        "[--tb-gold-soft:rgba(163,129,45,0.18)]",
        "[--tb-border:rgba(163,129,45,0.22)]",
        "[--tb-tile-border:rgba(24,51,43,0.10)]",
        // Dark-theme tokens — original luxury wall colors for the
        // panel + tiles. The page bg in dark mode is already deep
        // green so we don't need a section bg of our own.
        "dark:[--tb-panel-bg:rgba(255,255,255,0.04)]",
        "dark:[--tb-panel-bg-strong:rgba(255,255,255,0.06)]",
        "dark:[--tb-gold:#cfa646]",
        "dark:[--tb-gold-soft:rgba(207,166,70,0.24)]",
        "dark:[--tb-border:rgba(207,166,70,0.16)]",
        "dark:[--tb-tile-border:rgba(255,255,255,0.08)]"
      )}
    >
      <motion.div
        initial={initial}
        whileInView="visible"
        viewport={{ once: true, amount: 0.15 }}
        className="relative isolate"
      >
        {/* Header */}
        <motion.div
          variants={HEADER_VARIANTS}
          className="mx-auto mb-10 max-w-2xl text-center sm:mb-14"
        >
          {data.eyebrow && (
            <span
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em]"
              style={{
                color: "var(--tb-gold)",
                borderColor: "var(--tb-border)",
                background: "var(--tb-gold-soft)",
              }}
            >
              <Sparkles className="h-3 w-3" />
              {data.eyebrow}
            </span>
          )}
          {data.title && (
            <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              {data.title}
            </h2>
          )}
          {data.subtitle && (
            <p className="mt-4 text-pretty text-base text-muted-foreground">
              {data.subtitle}
            </p>
          )}
          <motion.span
            variants={ACCENT_VARIANTS}
            aria-hidden
            className="mt-6 inline-block h-[2px] w-24 origin-left rounded-full"
            style={{
              background:
                "linear-gradient(90deg, transparent, var(--tb-gold), transparent)",
            }}
          />
        </motion.div>

        {/* Brand panel */}
        <motion.div
          variants={PANEL_VARIANTS}
          className={cn(
            "relative mx-auto overflow-hidden rounded-[2rem] border p-5 backdrop-blur-2xl sm:p-8",
            // Two shadow stops: outer drop shadow (theme-aware) + inner edge highlight.
            "shadow-[0_18px_55px_-22px_rgba(24,51,43,0.18),inset_0_1px_0_0_rgba(255,255,255,0.6)]",
            "dark:shadow-[0_30px_80px_-28px_rgba(0,0,0,0.65),inset_0_1px_0_0_rgba(255,255,255,0.08)]"
          )}
          style={{
            background: "var(--tb-panel-bg)",
            borderColor: "var(--tb-border)",
            willChange: "transform, opacity",
          }}
        >
          {/* Soft corner glints inside the panel */}
          <span
            aria-hidden
            className="pointer-events-none absolute -left-12 -top-10 h-40 w-40 rounded-full blur-2xl opacity-70"
            style={{ background: "var(--tb-gold-soft)" }}
          />
          <span
            aria-hidden
            className="pointer-events-none absolute -right-16 -bottom-12 h-44 w-44 rounded-full blur-2xl opacity-50"
            style={{ background: "var(--tb-green-glow)" }}
          />

          <motion.div variants={TILES_CONTAINER_VARIANTS}>
            {layoutMode === "marquee" && <BrandMarquee brands={brands} />}
            {layoutMode === "grid" && <BrandGrid brands={brands} />}
            {layoutMode === "carousel" && <BrandCarousel brands={brands} />}
          </motion.div>
        </motion.div>
      </motion.div>
    </Section>
  );
}


// ---------------------------------------------------------------------------
// Layout: marquee — two rows that scroll in opposite directions and pause
// on hover. Pure CSS animation so it works even when GSAP isn't loaded
// (e.g. reduced motion or admin animation-disabled).
// ---------------------------------------------------------------------------

function BrandMarquee({ brands }: { brands: HomepageTrustedBrand[] }) {
  // Split into two rows for visual richness when there are enough
  // logos; fall back to a single row otherwise.
  const useTwoRows = brands.length >= 6;
  const half = Math.ceil(brands.length / 2);
  const row1 = useTwoRows ? brands.slice(0, half) : brands;
  const row2 = useTwoRows ? brands.slice(half) : [];

  return (
    <div className="space-y-5">
      <MarqueeRow brands={row1} reverse={false} />
      {row2.length > 0 && <MarqueeRow brands={row2} reverse />}
    </div>
  );
}

function MarqueeRow({
  brands,
  reverse,
}: {
  brands: HomepageTrustedBrand[];
  reverse: boolean;
}) {
  // Duplicate the row twice so the translateX(-50%) keyframe loops
  // seamlessly regardless of the count.
  const items = [...brands, ...brands];
  return (
    <div
      className="group/marquee relative overflow-hidden"
      style={{
        maskImage:
          "linear-gradient(90deg, transparent, black 8%, black 92%, transparent)",
        WebkitMaskImage:
          "linear-gradient(90deg, transparent, black 8%, black 92%, transparent)",
      }}
    >
      <div
        className={cn(
          "flex w-max items-stretch gap-4 sm:gap-5",
          // CSS marquee keyframes defined inline below.
          reverse
            ? "animate-[tb-marquee-r_38s_linear_infinite]"
            : "animate-[tb-marquee-l_38s_linear_infinite]",
          "group-hover/marquee:[animation-play-state:paused]"
        )}
      >
        {items.map((brand, idx) => (
          <BrandTile
            key={`${brand.id}-${idx}`}
            brand={brand}
            // Only tiles in the first half (the originals, not the
            // duplicates) are animation targets — duplicates inherit.
            asAnimationTarget={idx < brands.length}
          />
        ))}
      </div>

      {/* Marquee keyframes — kept inline so the section is self-contained. */}
      <style jsx>{`
        @keyframes tb-marquee-l {
          0% {
            transform: translateX(0);
          }
          100% {
            transform: translateX(-50%);
          }
        }
        @keyframes tb-marquee-r {
          0% {
            transform: translateX(-50%);
          }
          100% {
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Layout: grid — balanced responsive tile wall.
// ---------------------------------------------------------------------------

function BrandGrid({ brands }: { brands: HomepageTrustedBrand[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 md:grid-cols-4 lg:grid-cols-5">
      {brands.map((brand) => (
        <BrandTile key={brand.id} brand={brand} asAnimationTarget />
      ))}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Layout: carousel — horizontally scrollable row, snaps on touch.
// ---------------------------------------------------------------------------

function BrandCarousel({ brands }: { brands: HomepageTrustedBrand[] }) {
  return (
    <div
      className="-mx-2 flex snap-x snap-mandatory items-stretch gap-4 overflow-x-auto px-2 pb-2 sm:gap-5"
      style={{ scrollbarWidth: "none" }}
    >
      {brands.map((brand) => (
        <div
          key={brand.id}
          className="snap-center shrink-0"
          style={{ width: "min(220px, 50vw)" }}
        >
          <BrandTile brand={brand} asAnimationTarget />
        </div>
      ))}
    </div>
  );
}


// ---------------------------------------------------------------------------
// BrandTile — premium glass logo card with gold accent + halo on hover.
// ---------------------------------------------------------------------------

function BrandTile({
  brand,
  asAnimationTarget,
}: {
  brand: HomepageTrustedBrand;
  asAnimationTarget: boolean;
}) {
  const logo = normaliseMediaUrl(brand.logo_url_alt ?? brand.logo_url);
  const labelId = `brand-${brand.id}`;
  // Only the originals (asAnimationTarget=true) participate in the
  // stagger reveal. The marquee duplicates inherit the visible state
  // implicitly because they are rendered with no variants attached —
  // framer-motion treats a plain ``div`` as "no animation, render as-is".
  const inner = (
    <motion.div
      variants={asAnimationTarget ? TILE_VARIANTS : undefined}
      className={cn(
        "group/tile relative flex h-28 w-44 shrink-0 items-center justify-center overflow-hidden rounded-2xl border backdrop-blur-md transition-all duration-300 sm:h-32 sm:w-52",
        "hover:-translate-y-0.5",
        // Theme-aware tile shadow: lighter, gold-tinted drop in light mode;
        // deeper near-black drop in dark mode.
        "shadow-[inset_0_1px_0_0_rgba(255,255,255,0.6),0_8px_24px_-12px_rgba(24,51,43,0.18)]",
        "dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_8px_24px_-12px_rgba(0,0,0,0.55)]",
        brand.is_highlight && "ring-1"
      )}
      style={{
        background: "var(--tb-panel-bg-strong)",
        borderColor: brand.is_highlight
          ? "var(--tb-gold)"
          : "var(--tb-tile-border)",
      }}
    >
      {/* Subtle inner gold ring */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover/tile:opacity-100"
        style={{
          boxShadow: "inset 0 0 0 1px var(--tb-gold-soft)",
        }}
      />

      {/* Hover halo behind the logo */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover/tile:opacity-100"
        style={{
          background:
            "radial-gradient(60% 80% at 50% 50%, var(--tb-gold-soft), transparent 70%)",
        }}
      />

      {/* Diagonal shine sweep on hover */}
      <span
        aria-hidden
        className="pointer-events-none absolute -inset-1 -translate-x-full skew-x-[-20deg] bg-gradient-to-r from-transparent via-amber-500/15 to-transparent transition-transform duration-700 group-hover/tile:translate-x-full dark:via-white/15"
      />

      {logo ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logo}
          alt={brand.brand_name}
          loading="lazy"
          aria-labelledby={labelId}
          className="relative z-10 max-h-16 w-auto max-w-[85%] object-contain opacity-90 transition-all duration-300 group-hover/tile:opacity-100 sm:max-h-20"
        />
      ) : (
        <span
          id={labelId}
          className="relative z-10 px-3 text-center text-xs font-semibold uppercase tracking-[0.18em]"
          style={{ color: "var(--tb-text)" }}
        >
          {brand.brand_name}
        </span>
      )}

      {/* Visually-hidden brand name when logo image is used, for a11y */}
      {logo && (
        <span id={labelId} className="sr-only">
          {brand.brand_name}
        </span>
      )}

      {/* Highlight badge */}
      {brand.is_highlight && (
        <span
          aria-hidden
          className="absolute right-2 top-2 rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.18em]"
          style={{
            color: "var(--tb-gold)",
            background: "var(--tb-gold-soft)",
          }}
        >
          Featured
        </span>
      )}
    </motion.div>
  );

  if (brand.link_url) {
    return (
      <Link
        href={brand.link_url}
        target={
          brand.link_url.startsWith("http") ? "_blank" : undefined
        }
        rel={
          brand.link_url.startsWith("http") ? "noopener noreferrer" : undefined
        }
        aria-label={brand.brand_name}
        className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--tb-gold)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--tb-bg)]"
      >
        {inner}
      </Link>
    );
  }

  return inner;
}
