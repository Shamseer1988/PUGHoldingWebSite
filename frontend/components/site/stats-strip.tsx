"use client";

import * as React from "react";
import { motion, useInView, type Variants } from "framer-motion";
import { ArrowUpRight } from "lucide-react";

import { STATS, type StatItem } from "@/lib/dummy-data/site-content";
import { cn } from "@/lib/utils";

/**
 * Homepage stats — uniform card row with framer-motion scroll
 * choreography (Phase B-5; previously driven by GSAP ScrollTrigger).
 *
 * Replaces the prior bento (whose dark-green hero slab clashed with
 * the warm cream brand surface) with five equal glass-style cards.
 * The visual interest comes from typography + a per-card hairline
 * gold accent that draws in after the card settles, not from a heavy
 * coloured tile.
 *
 * Layout:
 *   - lg+ : five-up row
 *   - md  : 3 + 2 (two rows)
 *   - sm  : single column stack
 *
 * Each card sits on the same `bg-card`-style glass with a subtle
 * brand border, so light + dark look like reflections of one another
 * — no jarring colour swap.
 *
 * Animation:
 *   - Cards fade-up + scale-in with 80ms stagger via
 *     ``staggerChildren`` on the list container.
 *   - Each card's accent line scaleX 0 → 1 follows the card by a
 *     250ms delay, the same offset GSAP's "-=0.35" produced.
 *   - The count-up uses the existing IntersectionObserver +
 *     requestAnimationFrame pattern (preserved verbatim).
 *   - All three layers respect ``prefers-reduced-motion: reduce``
 *     via the local hook below — cards land at their final state
 *     on first paint, and the count-up snaps.
 *
 * The `tile_variant` / `sparkline_points` fields on StatItem stay
 * supported for back-compat but no longer affect the layout. The
 * optional `trend_percent` / `trend_label` still surface as a small
 * pill in the top-right of any card that has them.
 */
const REVEAL_EASE = [0.16, 1, 0.3, 1] as const;

const LIST_VARIANTS: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};

const CARD_VARIANTS: Variants = {
  hidden: { opacity: 0, y: 32, scale: 0.97 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.7, ease: REVEAL_EASE },
  },
};

const ACCENT_VARIANTS: Variants = {
  hidden: { scaleX: 0 },
  visible: {
    scaleX: 1,
    transition: { duration: 0.5, ease: REVEAL_EASE, delay: 0.25 },
  },
};

export function StatsStrip() {
  const reduced = usePrefersReducedMotion();
  const initial = reduced ? "visible" : "hidden";

  return (
    <motion.ul
      role="list"
      variants={LIST_VARIANTS}
      initial={initial}
      whileInView="visible"
      viewport={{ once: true, amount: 0.2 }}
      className="grid grid-cols-2 gap-2.5 sm:grid-cols-2 sm:gap-4 md:grid-cols-3 lg:grid-cols-5"
    >
      {STATS.map((stat) => (
        <motion.li
          key={stat.label}
          variants={CARD_VARIANTS}
          aria-label={ariaLabelFor(stat)}
          className={cn(
            "group relative flex h-full flex-col overflow-hidden rounded-2xl border border-pug-green-900/[0.08] bg-white/70 p-3.5 backdrop-blur-sm shadow-[0_1px_2px_rgba(15,42,28,0.04)] sm:p-6",
            "dark:border-white/10 dark:bg-white/[0.04]",
            // Hover lift gated by motion-safe so reduced-motion users
            // see no transform.
            "motion-safe:transition-shadow motion-safe:duration-200",
            "motion-safe:hover:shadow-[0_8px_24px_-12px_rgba(15,42,28,0.18)]",
            "dark:motion-safe:hover:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.6)]"
          )}
          style={{ willChange: "transform, opacity" }}
        >
          <header className="flex items-start justify-between gap-2">
            <span
              aria-hidden
              className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-pug-gold-500/25 bg-pug-gold-500/10 text-pug-gold-700 dark:text-pug-gold-300 sm:h-9 sm:w-9 sm:rounded-xl"
            >
              <stat.icon className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            </span>
            <TrendPill percent={stat.trend_percent} label={stat.trend_label} />
          </header>

          <strong className="mt-3 block text-2xl font-medium leading-none tracking-tight tabular-nums text-pug-green-900 dark:text-foreground sm:mt-6 sm:text-5xl">
            <Counter target={stat.value} suffix={stat.suffix} />
          </strong>

          <div className="mt-1.5 space-y-1.5 sm:mt-3 sm:space-y-2">
            <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-muted-foreground sm:text-[10.5px] sm:tracking-[0.18em]">
              {stat.label}
            </p>
            <motion.span
              aria-hidden
              variants={ACCENT_VARIANTS}
              className="block h-px w-8 origin-left bg-gradient-to-r from-pug-gold-500 to-pug-gold-500/0 sm:w-12"
              style={{ willChange: "transform" }}
            />
          </div>
        </motion.li>
      ))}
    </motion.ul>
  );
}


// ---------------------------------------------------------------------------
// Trend pill — used in any card that defines trend_percent or trend_label
// ---------------------------------------------------------------------------


function TrendPill({
  percent,
  label,
}: {
  percent?: number;
  label?: string;
}) {
  const text = label ?? (percent != null ? `+${percent}% YoY` : null);
  if (!text) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-pug-gold-500/25 bg-pug-gold-500/10 px-2 py-0.5 text-[10px] font-medium tracking-wide text-pug-gold-700 dark:text-pug-gold-300">
      <ArrowUpRight className="h-3 w-3" aria-hidden />
      {text}
    </span>
  );
}


// ---------------------------------------------------------------------------
// Counter — animated number with IntersectionObserver trigger.
// Preserves the prior implementation and adds the local reduced-motion
// short-circuit so the test mock works reliably.
// ---------------------------------------------------------------------------


function Counter({
  target,
  suffix = "",
}: {
  target: number;
  suffix?: string;
}) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const reduced = usePrefersReducedMotion();
  const [value, setValue] = React.useState(() => (reduced ? target : 0));

  React.useEffect(() => {
    if (reduced) {
      setValue(target);
      return;
    }
    if (!inView) return;
    const startTs = performance.now();
    const durationMs = Math.min(1400, 400 + Math.log10(target + 1) * 350);
    let raf = 0;

    function step(now: number) {
      const elapsed = now - startTs;
      const t = Math.min(1, elapsed / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(target * eased));
      if (t < 1) raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [inView, target, reduced]);

  return (
    <motion.span
      ref={ref}
      initial={{ opacity: reduced ? 1 : 0 }}
      animate={{ opacity: inView || reduced ? 1 : 0 }}
      transition={{ duration: reduced ? 0 : 0.4 }}
    >
      {value.toLocaleString()}
      {suffix}
    </motion.span>
  );
}


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------


function ariaLabelFor(stat: StatItem): string {
  return `${stat.value.toLocaleString()}${stat.suffix ?? ""} ${stat.label.toLowerCase()}`;
}


/**
 * Local `prefers-reduced-motion: reduce` hook.
 *
 * We deliberately avoid framer-motion's `useReducedMotion` because it
 * caches `matchMedia` into a module-scoped singleton, which makes
 * the test mock unreliable. This local version reads the live
 * media-query on first render and subscribes to changes.
 */
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = React.useState<boolean>(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return false;
    }
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  });
  React.useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handler = () => setReduced(mql.matches);
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", handler);
      return () => mql.removeEventListener("change", handler);
    }
    mql.addListener(handler);
    return () => mql.removeListener(handler);
  }, []);
  return reduced;
}
