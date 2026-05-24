"use client";

import * as React from "react";
import {
  motion,
  useInView,
  type Variants,
} from "framer-motion";
import { ArrowUpRight } from "lucide-react";

import { STATS, type StatItem } from "@/lib/dummy-data/site-content";
import { cn } from "@/lib/utils";

/**
 * Homepage stats — bento layout.
 *
 * Layout:
 *   - lg+ : 3-column grid. The "hero" tile spans column 1 and rows 1-2.
 *           The four supporting tiles live in a nested 2-column grid
 *           that occupies the remaining 2 columns.
 *   - md  : 2-column grid. Hero spans the full row, then 2x2.
 *   - sm  : single column. Hero first, then the rest stacked.
 *
 * The hero is selected by `tile_variant === "hero"` — its position in
 * the source array doesn't matter. If no entry is flagged hero, every
 * tile falls back to the supporting grid (graceful degradation).
 */
export function StatsStrip() {
  const hero = STATS.find((s) => s.tile_variant === "hero");
  const rest = STATS.filter((s) => s !== hero);

  return (
    <ul
      role="list"
      className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3 lg:auto-rows-fr"
    >
      {hero && <HeroTile stat={hero} />}
      <li
        className={cn(
          "grid grid-cols-1 gap-3 sm:grid-cols-2",
          hero ? "lg:col-span-2" : "md:col-span-2 lg:col-span-3"
        )}
      >
        <ul role="list" className="contents">
          {rest.map((stat) => (
            <Tile key={stat.label} stat={stat} />
          ))}
        </ul>
      </li>
    </ul>
  );
}


// ---------------------------------------------------------------------------
// Tiles
// ---------------------------------------------------------------------------


function HeroTile({ stat }: { stat: StatItem }) {
  const Icon = stat.icon;
  return (
    <li
      aria-label={ariaLabelFor(stat)}
      className="motion-safe:transition-all motion-safe:duration-200 motion-safe:hover:-translate-y-0.5 motion-safe:hover:shadow-md md:col-span-2 lg:col-span-1 lg:row-span-2"
    >
      <div
        className={cn(
          "pug-dotgrid relative isolate flex h-full min-h-[220px] flex-col overflow-hidden rounded-2xl bg-gradient-to-br from-pug-green-700 to-pug-green-800 p-6 text-white shadow-[0_8px_30px_-12px_rgba(15,42,28,0.45)]"
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <span
            aria-hidden
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-pug-gold-500/40 bg-pug-gold-500/20 text-pug-gold-300"
          >
            <Icon className="h-5 w-5" />
          </span>
          <TrendPill
            percent={stat.trend_percent}
            label={stat.trend_label}
            tone="dark"
          />
        </div>

        <strong className="mt-6 block text-[56px] font-medium leading-none tracking-tighter tabular-nums">
          <Counter target={stat.value} suffix={stat.suffix} />
        </strong>
        <span className="mt-2 inline-block text-[11px] font-medium uppercase tracking-[0.18em] text-white/70">
          {stat.label}
        </span>

        {stat.sparkline_points && stat.sparkline_points.length > 1 && (
          <Sparkline
            points={stat.sparkline_points}
            className="pointer-events-none absolute bottom-3 right-3 h-9 w-[140px] opacity-50"
          />
        )}
      </div>
    </li>
  );
}


function Tile({ stat }: { stat: StatItem }) {
  if (stat.tile_variant === "accent") {
    return <AccentTile stat={stat} />;
  }
  if (stat.tile_variant === "sectors") {
    return <SectorsTile stat={stat} />;
  }
  return <DefaultTile stat={stat} />;
}


function DefaultTile({ stat }: { stat: StatItem }) {
  const Icon = stat.icon;
  return (
    <li
      aria-label={ariaLabelFor(stat)}
      className="motion-safe:transition-all motion-safe:duration-200 motion-safe:hover:-translate-y-0.5 motion-safe:hover:shadow-md"
    >
      <div
        className={cn(
          "relative flex h-full flex-col rounded-2xl border border-pug-green-900/10 bg-white p-[18px] shadow-[0_1px_2px_rgba(15,42,28,0.04)]",
          "dark:border-border/40 dark:bg-card"
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <span
            aria-hidden
            className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-pug-gold-500/12 text-pug-gold-700 dark:text-pug-gold-300"
          >
            <Icon className="h-4 w-4" />
          </span>
          <TrendPill
            percent={stat.trend_percent}
            label={stat.trend_label}
            tone="muted"
          />
        </div>

        <span className="mt-4 inline-block text-[9.5px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
          {stat.label}
        </span>
        <strong className="mt-1 block text-[30px] font-medium leading-tight tabular-nums text-pug-green-900 dark:text-foreground">
          <Counter target={stat.value} suffix={stat.suffix} />
        </strong>
      </div>
    </li>
  );
}


function AccentTile({ stat }: { stat: StatItem }) {
  const Icon = stat.icon;
  // Decision A: dark forest-green text on the gold background clears
  // WCAG AA. White-on-gold-500 lands at ~3.4:1 which is below the 4.5
  // floor for body text.
  return (
    <li
      aria-label={ariaLabelFor(stat)}
      className="motion-safe:transition-all motion-safe:duration-200 motion-safe:hover:-translate-y-0.5 motion-safe:hover:shadow-md"
    >
      <div className="relative flex h-full flex-col rounded-2xl bg-gradient-to-br from-pug-gold-500 to-pug-gold-400 p-[18px] text-pug-green-900 shadow-[0_1px_2px_rgba(80,55,15,0.10)]">
        <div className="flex items-start justify-between gap-3">
          <span
            aria-hidden
            className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-pug-green-900/15 text-pug-green-900"
          >
            <Icon className="h-4 w-4" />
          </span>
          <TrendPill
            percent={stat.trend_percent}
            label={stat.trend_label}
            tone="on-gold"
          />
        </div>
        <span className="mt-4 inline-block text-[9.5px] font-medium uppercase tracking-[0.18em] text-pug-green-900/80">
          {stat.label}
        </span>
        <strong className="mt-1 block text-[30px] font-medium leading-tight tabular-nums">
          <Counter target={stat.value} suffix={stat.suffix} />
        </strong>
      </div>
    </li>
  );
}


function SectorsTile({ stat }: { stat: StatItem }) {
  const Icon = stat.icon;
  return (
    <li
      aria-label={ariaLabelFor(stat)}
      className="motion-safe:transition-all motion-safe:duration-200 motion-safe:hover:-translate-y-0.5 motion-safe:hover:shadow-md"
    >
      <div
        className={cn(
          "relative flex h-full flex-col rounded-2xl border border-pug-green-900/10 bg-white p-[18px] shadow-[0_1px_2px_rgba(15,42,28,0.04)]",
          "dark:border-border/40 dark:bg-card"
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <span
            aria-hidden
            className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-pug-gold-500/12 text-pug-gold-700 dark:text-pug-gold-300"
          >
            <Icon className="h-4 w-4" />
          </span>
          <TrendPill
            percent={stat.trend_percent}
            label={stat.trend_label}
            tone="muted"
          />
        </div>
        <span className="mt-4 inline-block text-[9.5px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
          {stat.label}
        </span>
        <strong className="mt-1 block text-[30px] font-medium leading-tight tabular-nums text-pug-green-900 dark:text-foreground">
          <Counter target={stat.value} suffix={stat.suffix} />
        </strong>
        <div aria-hidden className="mt-3 flex h-1 gap-1">
          <span className="flex-1 rounded-full bg-pug-green-700" />
          <span className="flex-1 rounded-full bg-pug-gold-500" />
          <span className="flex-1 rounded-full bg-pug-green-500" />
        </div>
      </div>
    </li>
  );
}


// ---------------------------------------------------------------------------
// Trend pill
// ---------------------------------------------------------------------------


function TrendPill({
  percent,
  label,
  tone = "dark",
}: {
  percent?: number;
  label?: string;
  tone?: "dark" | "muted" | "on-gold";
}) {
  const text = label ?? (percent != null ? `+${percent}% YoY` : null);
  if (!text) return null;

  const classes = {
    dark: "bg-pug-gold-500/20 text-pug-gold-300 text-[10px]",
    muted:
      "border border-border/60 bg-background/60 text-muted-foreground text-[9px]",
    "on-gold": "bg-pug-green-900/15 text-pug-green-900 text-[10px]",
  } as const;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium tracking-wide",
        classes[tone]
      )}
    >
      <ArrowUpRight className="h-3 w-3" aria-hidden />
      {text}
    </span>
  );
}


// ---------------------------------------------------------------------------
// Sparkline
// ---------------------------------------------------------------------------


function Sparkline({
  points,
  className,
}: {
  points: number[];
  className?: string;
}) {
  const reduced = usePrefersReducedMotion();
  const w = 200;
  const h = 50;
  const stepX = w / Math.max(1, points.length - 1);
  const path = points
    .map((p, i) => {
      const x = i * stepX;
      const y = h - p * h * 0.85 - 4;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const fillPath = `${path} L${w},${h} L0,${h} Z`;

  // `pathLength` normalises stroke length so we can animate 0 → 1 without
  // needing `getTotalLength()` from JS.
  const lineVariants: Variants = reduced
    ? {
        hidden: { pathLength: 1, opacity: 1 },
        visible: { pathLength: 1, opacity: 1 },
      }
    : {
        hidden: { pathLength: 0, opacity: 0 },
        visible: {
          pathLength: 1,
          opacity: 1,
          transition: { duration: 1.2, ease: "easeOut", delay: 0.2 },
        },
      };
  const fillVariants: Variants = reduced
    ? { hidden: { opacity: 1 }, visible: { opacity: 1 } }
    : {
        hidden: { opacity: 0 },
        visible: {
          opacity: 1,
          transition: { duration: 0.8, ease: "easeOut", delay: 0.6 },
        },
      };

  return (
    <motion.svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className={className}
      aria-hidden
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.5 }}
    >
      <motion.path
        d={fillPath}
        fill="rgba(196,153,99,0.12)"
        variants={fillVariants}
      />
      <motion.path
        d={path}
        fill="none"
        stroke="#D4A574"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        variants={lineVariants}
      />
    </motion.svg>
  );
}


// ---------------------------------------------------------------------------
// Counter — copied verbatim from the previous implementation, with a
// `prefers-reduced-motion` short-circuit so reduced-motion users see
// the final value on first paint.
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
 * We deliberately avoid framer-motion's `useReducedMotion` here because
 * it caches `matchMedia` into a module-scoped singleton on first call,
 * which makes the test mock unreliable (the singleton would freeze the
 * value from whichever test ran first). This local version reads
 * `matchMedia` synchronously at every fresh render of the component
 * tree, and subscribes to changes via the standard `change` event.
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
    // Older Safari only supports the legacy `addListener` API.
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", handler);
      return () => mql.removeEventListener("change", handler);
    }
    mql.addListener(handler);
    return () => mql.removeListener(handler);
  }, []);
  return reduced;
}
