"use client";

import * as React from "react";
import { motion, useInView } from "framer-motion";
import { ArrowUpRight } from "lucide-react";

import { STATS, type StatItem } from "@/lib/dummy-data/site-content";
import { cn } from "@/lib/utils";

/**
 * Homepage stats — uniform card row with GSAP scroll choreography.
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
 *   - GSAP ScrollTrigger drives the entry: cards fade-up + scale-in
 *     with 80ms stagger, then the hairline accents scaleX 0 → 1 in
 *     sequence.
 *   - The count-up uses the existing IntersectionObserver +
 *     requestAnimationFrame pattern (preserved verbatim from the
 *     prior implementation).
 *   - Both layers respect `prefers-reduced-motion: reduce` — cards
 *     and accents render at their final state on first paint, and
 *     the count-up snaps to the final value.
 *
 * The `tile_variant` / `sparkline_points` fields on StatItem stay
 * supported for back-compat but no longer affect the layout. The
 * optional `trend_percent` / `trend_label` still surface as a small
 * pill in the top-right of any card that has them.
 */
export function StatsStrip() {
  const sectionRef = React.useRef<HTMLUListElement | null>(null);
  const cardRefs = React.useRef<(HTMLLIElement | null)[]>([]);
  const accentRefs = React.useRef<(HTMLSpanElement | null)[]>([]);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (reduced) return;

    let cancelled = false;
    let cleanup: (() => void) | undefined;

    (async () => {
      const { gsap } = await import("gsap");
      const { ScrollTrigger } = await import("gsap/ScrollTrigger");
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);

      const section = sectionRef.current;
      const cards = cardRefs.current.filter(Boolean) as HTMLElement[];
      const accents = accentRefs.current.filter(Boolean) as HTMLElement[];
      if (!section || cards.length === 0) return;

      // Safety net for the timeline below — see footer.tsx for
      // rationale. If ScrollTrigger never fires, the stats cards
      // would stay invisible.
      let safetyTimer: number | undefined;

      const ctx = gsap.context(() => {
        // Hide everything until the timeline runs, so first paint
        // matches the animation starting position.
        gsap.set(cards, { y: 32, opacity: 0, scale: 0.97 });
        gsap.set(accents, { scaleX: 0, transformOrigin: "left center" });

        const tl = gsap.timeline({
          scrollTrigger: {
            trigger: section,
            start: "top 80%",
            once: true,
          },
          defaults: { ease: "power3.out" },
        });

        tl.to(cards, {
          y: 0,
          opacity: 1,
          scale: 1,
          duration: 0.7,
          stagger: 0.08,
        });
        if (accents.length) {
          tl.to(
            accents,
            {
              scaleX: 1,
              duration: 0.5,
              stagger: 0.08,
              ease: "power2.out",
            },
            "-=0.35"
          );
        }

        safetyTimer = window.setTimeout(() => {
          if (!tl.isActive() && tl.progress() === 0) {
            tl.progress(1);
          }
        }, 2500);
      }, section);

      cleanup = () => {
        if (safetyTimer !== undefined) window.clearTimeout(safetyTimer);
        ctx.revert();
      };
    })();

    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, []);

  return (
    <ul
      ref={sectionRef}
      role="list"
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 md:grid-cols-3 lg:grid-cols-5"
    >
      {STATS.map((stat, idx) => (
        <li
          key={stat.label}
          ref={(el) => {
            cardRefs.current[idx] = el;
          }}
          aria-label={ariaLabelFor(stat)}
          className={cn(
            "group relative flex h-full flex-col overflow-hidden rounded-2xl border border-pug-green-900/[0.08] bg-white/70 p-5 backdrop-blur-sm shadow-[0_1px_2px_rgba(15,42,28,0.04)] sm:p-6",
            "dark:border-white/10 dark:bg-white/[0.04]",
            // Hover lift gated by motion-safe so reduced-motion users
            // see no transform.
            "motion-safe:transition-shadow motion-safe:duration-200",
            "motion-safe:hover:shadow-[0_8px_24px_-12px_rgba(15,42,28,0.18)]",
            "dark:motion-safe:hover:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.6)]"
          )}
          style={{ willChange: "transform, opacity" }}
        >
          <header className="flex items-start justify-between gap-3">
            <span
              aria-hidden
              className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-pug-gold-500/25 bg-pug-gold-500/10 text-pug-gold-700 dark:text-pug-gold-300"
            >
              <stat.icon className="h-4 w-4" />
            </span>
            <TrendPill percent={stat.trend_percent} label={stat.trend_label} />
          </header>

          <strong className="mt-6 block text-[2.5rem] font-medium leading-none tracking-tight tabular-nums text-pug-green-900 dark:text-foreground sm:text-5xl">
            <Counter target={stat.value} suffix={stat.suffix} />
          </strong>

          <div className="mt-3 space-y-2">
            <p className="text-[10.5px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {stat.label}
            </p>
            <span
              aria-hidden
              ref={(el) => {
                accentRefs.current[idx] = el;
              }}
              className="block h-px w-12 bg-gradient-to-r from-pug-gold-500 to-pug-gold-500/0"
              style={{ willChange: "transform" }}
            />
          </div>
        </li>
      ))}
    </ul>
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
