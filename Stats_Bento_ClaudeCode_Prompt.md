# Business Overview — Bento Grid Stats — Claude Code Implementation Prompt

> Copy the section under **PROMPT TO PASTE INTO CLAUDE CODE** into a fresh Claude Code session. Self-contained — covers the component rewrite, optional CMS-managed extension, types, animation, accessibility, tests, and acceptance criteria.

---

## Context for the human

The homepage currently renders a five-equal-cards stats strip via `components/site/stats-strip.tsx` (a client component that uses Framer Motion's `useInView` + a count-up `<Counter>`). Data lives statically in `lib/dummy-data/site-content.ts` as `STATS`.

This prompt replaces that with a **bento-grid layout** — one hero stat (customers served daily) gets a large dark-green card on the left with a sparkline and trend badge, and the four supporting stats sit in a 2×2 grid on the right with one accent gold card for visual rhythm. Modern, asymmetric, screenshot-friendly. Keeps the existing count-up animation, IntersectionObserver trigger, accessibility scaffolding, and theme tokens — only the layout, the per-card chrome, and a few new optional data fields change.

The data model is extended with optional fields (`trend_percent`, `trend_label`, `sparkline_points`, `tile_variant`) so each stat can render with appropriate chrome. Existing `StatItem` rows keep working without those fields (graceful fallback).

A follow-up Phase 5 CMS migration to back this with a real `cms_stats` table is sketched at the bottom as an out-of-scope appendix — keep this PR focused on the layout rewrite.

---

## PROMPT TO PASTE INTO CLAUDE CODE

````
You are working in the Paris United Group monorepo. Read CLAUDE.md, the docs/ folder, and the files I list below before touching code. Print a numbered file-by-file plan and wait for confirmation before editing.

# Goal

Replace the existing five-equal-cards stats strip on the homepage with a bento-grid layout: one hero card on the left for "Customers served daily" with a sparkline and trend badge, and four supporting stats in a 2x2 grid on the right with one accent-gold card. Keep the count-up animation and IntersectionObserver trigger that already exist. Modernise without breaking the data contract.

# Files to read first

- `frontend/components/site/stats-strip.tsx` (the component being rewritten — current implementation uses Framer Motion + GlassCard)
- `frontend/components/site/glass-card.tsx` (visual primitive used today; bento cards will use their own treatment)
- `frontend/components/site/section.tsx` (wrapper used by the homepage — keep)
- `frontend/lib/dummy-data/site-content.ts` (defines STATS array — extend this)
- `frontend/app/(public)/page.tsx` (homepage — currently calls <StatsStrip /> inside a <Section eyebrow="Business overview" ...>)
- `frontend/tailwind.config.ts` (confirm the pug-green and pug-gold colour tokens — they should already exist)
- `frontend/styles/globals.css` (theme tokens)

# Visual specification

Bento layout, responsive:

- Desktop (lg+): 3-column grid. Hero card spans column 1 and rows 1-2 (2x1 in row count). Cards 2-5 fill the remaining 2x2 grid on the right
- Tablet (md): 2-column grid. Hero card spans full width on top, supporting 2x2 below
- Mobile: single column. Hero first, then four cards stacked

Card chrome per role:

1. HERO card (Customers served daily):
   - Dark green background: gradient `from-pug-green-700 to-pug-green-800` (use the existing tokens — fall back to `from-emerald-900 to-emerald-800` if no PUG token exists)
   - Subtle dot-grid pattern overlay at 6% opacity (CSS radial-gradient)
   - Icon in a frosted gold pill: 36x36, `bg-pug-gold-500/20 border-pug-gold-500/40`, gold icon
   - Trend badge top-right: pill with arrow-up-right icon and "+12% YoY" text in gold on a translucent gold background
   - Number: 56px font weight 500, white, `tracking-tighter`, `font-variant-numeric: tabular-nums`
   - Label: 11px uppercase tracking-[0.18em] in white/70
   - Sparkline (SVG, bottom-right corner): an upward-trending curve in gold at 50% opacity, fading area fill underneath
   - Padding: 24px
   - Min height matches the 2x1 column on the right (~220px)

2. SUPPORTING cards (Group companies, Retail branches, Business sectors):
   - White background, 0.5px border `border-pug-green-900/10`, rounded-2xl
   - Icon badge 28x28, `bg-pug-gold-500/12`, gold icon
   - Tiny eyebrow label 9.5px uppercase tracking-[0.18em] muted
   - Number: 30px, weight 500, dark green, tabular-nums
   - Padding: 18px

3. ACCENT card (Employees) — the gold one for visual rhythm:
   - Background: gradient `from-pug-gold-500 to-pug-gold-400`
   - Icon badge: `bg-white/25`, white icon
   - Eyebrow label: white at 90% opacity
   - Number: 30px, weight 500, white, tabular-nums
   - Padding: 18px

4. SECTORS card (Business sectors) gets a small extra detail under the number: a 3-segment progress bar (each segment one of the sector colours) since "3" has no trend direction. Heights 4px, gap 4px. Segments: dark green, gold, mid green.

# Data model — extend StatItem

Edit `frontend/lib/dummy-data/site-content.ts`:

```ts
export type StatTileVariant = "default" | "hero" | "accent" | "sectors";

export interface StatItem {
  label: string;
  value: number;
  suffix?: string;
  icon: LucideIcon;
  /** Optional layout role for the bento grid. Defaults to "default". */
  tile_variant?: StatTileVariant;
  /** Optional trend percentage (e.g. 12 → "+12% YoY"). */
  trend_percent?: number;
  /** Optional override for trend label (e.g. "+4 in Q2"). */
  trend_label?: string;
  /** Optional sparkline data — 6 to 12 normalised values 0..1. */
  sparkline_points?: number[];
}

export const STATS: StatItem[] = [
  {
    label: "Group companies",
    value: 14,
    icon: Building2,
    tile_variant: "default",
  },
  {
    label: "Retail branches",
    value: 56,
    suffix: "+",
    icon: ShoppingBag,
    tile_variant: "default",
    trend_label: "+4 in Q2",
  },
  {
    label: "Employees",
    value: 2500,
    suffix: "+",
    icon: Users,
    tile_variant: "accent",
  },
  {
    label: "Business sectors",
    value: 3,
    icon: Briefcase,
    tile_variant: "sectors",
  },
  {
    label: "Customers served daily",
    value: 100000,
    suffix: "+",
    icon: HandHeart,
    tile_variant: "hero",
    trend_percent: 12,
    sparkline_points: [0.2, 0.25, 0.35, 0.4, 0.55, 0.65, 0.78, 0.9, 1.0],
  },
];
```

The hero card MUST be the one with `tile_variant: "hero"` regardless of array order. The grid renderer picks it out and places it in the left column.

# Component rewrite

Replace `frontend/components/site/stats-strip.tsx` with a bento renderer. Keep the file path and the exported `StatsStrip` symbol so the homepage import doesn't change.

Structure:

```tsx
"use client";

import * as React from "react";
import { motion, useInView } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import { STATS, type StatItem } from "@/lib/dummy-data/site-content";
import { cn } from "@/lib/utils";

export function StatsStrip() {
  const hero = STATS.find((s) => s.tile_variant === "hero");
  const rest = STATS.filter((s) => s.tile_variant !== "hero");
  // ...
}
```

Render:

```tsx
<div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3 lg:auto-rows-fr">
  {hero && (
    <HeroTile stat={hero} className="lg:col-span-1 lg:row-span-2" />
  )}
  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:col-span-2">
    {rest.map((stat) => (
      <Tile key={stat.label} stat={stat} />
    ))}
  </div>
</div>
```

Tiles:

- `HeroTile` — dark green + sparkline + trend pill (see Visual spec card 1)
- `Tile` — branches by `stat.tile_variant`:
  - `"accent"` → gold gradient card
  - `"sectors"` → white card with 3-segment progress bar under the number
  - default → plain white card with optional `trend_label` chip top-right

Use a single `<Counter>` component (you can keep the existing implementation from the old file — copy it verbatim — it already uses `useInView` + `requestAnimationFrame` correctly). The hero number gets a larger font; everything else uses the standard size.

Sparkline component:

```tsx
function Sparkline({ points, className }: { points: number[]; className?: string }) {
  const w = 200, h = 50;
  const stepX = w / Math.max(1, points.length - 1);
  const path = points
    .map((p, i) => {
      const x = i * stepX;
      const y = h - p * h * 0.85 - 4;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const fillPath = `${path} L${w},${h} L0,${h} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={className} aria-hidden>
      <path d={fillPath} fill="rgba(196,153,99,0.12)" />
      <path d={path} fill="none" stroke="#D4A574" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
```

Position the sparkline absolute bottom-right, width ~140px, height ~36px, opacity 50%.

# Trend pill

```tsx
function TrendPill({ percent, label }: { percent?: number; label?: string }) {
  const text = label ?? (percent != null ? `+${percent}% YoY` : null);
  if (!text) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-pug-gold-500/20 px-2 py-0.5 text-[10px] font-medium tracking-wide text-pug-gold-300">
      <ArrowUpRight className="h-3 w-3" />
      {text}
    </span>
  );
}
```

For supporting tiles, the pill goes top-right at 9px font in muted colour.

# Dot-grid background utility

Add to `frontend/styles/globals.css` (or as inline CSS in the hero tile — pick one):

```css
.pug-dotgrid {
  background-image: radial-gradient(circle at 1px 1px, rgba(255,255,255,0.08) 1px, transparent 0);
  background-size: 16px 16px;
}
```

Apply to the hero tile container.

# Animation requirements

- Count-up triggers only when the section enters the viewport (use the existing `useInView({ once: true, amount: 0.5 })` from the current file)
- Sparkline draws on enter — animate `stroke-dasharray` from 0 → path length using `<motion.path>`, duration 1.2s, easeOut, starting at 0.2s delay (after count-up begins)
- Hover: each tile lifts 2px with a soft shadow `shadow-md` — keep subtle, this is a corporate page not a marketing landing
- Honor `prefers-reduced-motion: reduce` — when set, render numbers at their final value immediately and skip sparkline animation; tiles do not lift on hover

# Accessibility

- Wrap the whole component in `<ul role="list">` so screen readers announce it as a list of stats (preserve the existing semantics — current component already uses `<ul>`)
- Each tile is an `<li>` with the number in `<strong>` and the label in `<span>` for proper hierarchy
- Numbers must have `aria-live="off"` while animating, then `aria-live="polite"` once final — or simpler, give each `<li>` an `aria-label="14 group companies"` so SR users hear the final number regardless of animation state
- Decorative SVG sparkline gets `aria-hidden="true"`
- Icons get `aria-hidden="true"` — labels carry the meaning
- All text must clear WCAG AA contrast against its background (white on `pug-green-700` is fine; verify pug-gold-500 background still gives 4.5:1 against white text — if it doesn't, swap to dark green text on the gold card)

# Theme & tokens

Use only existing Tailwind tokens. The PUG palette should already include:
- `pug-green-500`, `pug-green-700`, `pug-green-900`
- `pug-gold-300`, `pug-gold-400`, `pug-gold-500`

If those tokens are missing, surface that in the plan and propose adding them to `tailwind.config.ts` — do NOT use hardcoded hex values in the component file.

Dark mode: the hero tile's dark green works in both modes. White supporting tiles need a dark-mode variant: `dark:bg-card dark:border-border/40` and `dark:text-foreground` for numbers. Test by toggling the theme.

# Tests

Frontend (RTL or smoke tests):
- `StatsStrip` renders all 5 stats from the STATS array
- The hero tile picks the stat with `tile_variant: "hero"`, regardless of array order
- A stat with `tile_variant` omitted renders as a default tile (no crash)
- A stat without `sparkline_points` doesn't render a sparkline
- A stat without `trend_percent` and without `trend_label` doesn't render a trend pill
- `prefers-reduced-motion` set → final numbers visible immediately, no animation classes applied

# Acceptance criteria

- Homepage section "A snapshot of Paris United Group" now renders the bento grid (not the old 5-equal-cards strip)
- All 5 numbers count up smoothly when the section scrolls into view
- Hero tile (customers) has the dark-green background, dot-grid pattern, trend pill, sparkline
- Employees tile is gold; Sectors tile shows the 3-segment progress bar
- Mobile (375px wide) stacks cleanly: hero on top, four cards below — no horizontal scroll, no overlap
- Tablet (768px) shows hero full-width on top, 2x2 grid below
- Desktop (1280px+) shows hero on left, 2x2 on right
- Lighthouse accessibility score remains 100 on the home route
- No console warnings, no hydration mismatch
- `npm run build` completes with no new warnings
- All existing pages that import `StatsStrip` still work — homepage is the only consumer today

# Out of scope for this PR

- Moving STATS into the CMS as a real database-backed `cms_stats` table — that's a Phase 5 follow-up. Sketch:
  - Table `cms_stats` with columns `id, label, value, suffix, icon_name, tile_variant, trend_percent, trend_label, sparkline_points (JSON), display_order, is_active, created_at, updated_at`
  - Admin module mirrors hero-slides pattern with drag-and-drop reorder
  - Public endpoint `GET /stats` returns active rows ordered by `display_order`
  - StatsStrip becomes a server component that fetches via `getStats()`
- Variant switching at runtime (user picks bento vs other layouts) — single layout in v1
- Real-time stat updates via webhook — static numbers for now
- Translating labels — single locale (English) only
- Other stats sections on other pages (e.g. an investor relations sub-page) — homepage only

# Working agreement

- Plan first. Print a numbered file-by-file plan and wait for me to confirm before editing
- One commit per logical change: (1) data-model extension to StatItem, (2) StatsStrip rewrite, (3) styles addition (dot-grid utility), (4) tests
- Take a screenshot of the section before and after at desktop, tablet, and mobile widths — paste in the PR description
- Run `npm run build` and `npm test` before declaring done. Paste output of each
- If the PUG colour tokens don't exist in `tailwind.config.ts`, do NOT hardcode hex values — surface the missing tokens in the plan and propose adding them as a separate first commit
````

---

## Notes on using this prompt

Paste the entire fenced block above (everything between the triple backticks under `## PROMPT TO PASTE INTO CLAUDE CODE`) into a fresh Claude Code session. Claude Code will read the relevant files, print a plan, and wait for your confirmation before editing.

The implementation deliberately keeps the existing `<Counter>` component, the `useInView` trigger, and the file path (`components/site/stats-strip.tsx`) — only the layout changes. This means the homepage import (`<StatsStrip />` in `app/(public)/page.tsx`) doesn't need to change at all, and the count-up behaviour stays identical. The risk of regression is tiny.

The optional `trend_percent`, `trend_label`, `sparkline_points`, and `tile_variant` fields are all nullable extensions to `StatItem` — anyone adding a new stat row without them gets the default white tile with no extra chrome, which means the data file stays forgiving for marketing edits.

The "out of scope" appendix sketches the CMS migration so when you're ready to move STATS into a real database table (the same way `HeroSlide` and `MediaAsset` already work), there's a starting point. That's the right second step but not part of this PR — keep the visual rewrite isolated so it's easy to review.

---

*Generated as a planning document for the Paris United Group business overview rebuild. No source code in the project was modified.*
