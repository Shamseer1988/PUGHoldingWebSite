# Header Navbar — Variant A (Refined Classic) — Claude Code Implementation Prompt

> Copy the section under **PROMPT TO PASTE INTO CLAUDE CODE** into a fresh Claude Code session. Self-contained — covers the logo entrance animation, the nav-link underline interaction, the new icon-button + CTA-pill primitives, the optional scroll-pill behaviour, accessibility, mobile parity, tests, and acceptance criteria.

---

## Context for the human

The current header lives at `frontend/components/site/navbar.tsx`. It already has a lot of the bones in place: fixed positioning with a scroll-triggered backdrop blur, a `<Logo />` component, a centred `<DesktopNav>` with hover dropdowns (a `CompaniesMegaMenu` for "Group Companies", a generic `DropdownWrapper` for items with `children`), gold-and-green active underline, theme toggle, search panel, mobile menu trigger. The dropdown patterns and accessibility scaffolding (`aria-haspopup`, `aria-expanded`, focus + blur handling, hover bridges) are solid — keep them.

What Variant A adds, without rewriting the bones:

1. A **logo entrance animation** on first page load — mandala scales from `2.2× rotate(-12deg)` to `1×` with a custom spring overshoot, wordmark rises up 8 px afterwards. Plays once per session (sessionStorage-gated so it doesn't repeat on every soft-nav).
2. A subtle **3-second petal shimmer** loop on the mandala mark (opacity + brightness pulse) so the brand mark feels alive without distracting.
3. An animated **gold underline reveal** on nav-link hover (`scaleX` from 0 → 0.8, easing 220 ms) — alongside the existing active-state indicator.
4. New **outlined circular icon buttons** for search and theme toggle (36 × 36, 0.5 px border, hover bg `pug-gold-500/15`).
5. A new permanent **gold CTA pill** ("Join Us →" or admin-configurable text/href) on the right, between the icons and the mobile menu button.
6. The existing scroll-triggered backdrop blur stays — extend it with an *optional* "floating pill" behaviour after the user scrolls past 80 px (header detaches from the edges with 16 px inset, becomes a rounded pill). Behind a feature flag so it can ship dark.

The `Logo` component (`components/site/logo.tsx`) currently renders a Next.js `<Image>` PNG with no animation hooks. To support the entrance animation we'll wrap the existing image rendering in a `<motion.span>` and split mandala + wordmark into two animated children. The PNG remains the source of truth — no SVG rewrite needed.

---

## PROMPT TO PASTE INTO CLAUDE CODE

````
You are working in the Paris United Group monorepo. Read CLAUDE.md, the docs/ folder, and the files I list below before touching code. Print a numbered file-by-file plan and wait for confirmation before editing.

# Goal

Upgrade the public-site header (`components/site/navbar.tsx` + `components/site/logo.tsx`) to "Variant A — Refined Classic": logo entrance animation on first load (big-to-small mandala + wordmark rise), petal shimmer loop, gold-underline-reveal on nav-link hover, new outlined circular icon buttons, and a permanent gold CTA pill on the right. Keep all existing accessibility, dropdown, and mega-menu patterns intact. Add an optional scroll-pill behaviour behind a feature flag.

# Files to read first

- `frontend/components/site/navbar.tsx` — current navbar with scroll blur, dropdowns, mobile trigger
- `frontend/components/site/logo.tsx` — current Logo (next/image, no animation)
- `frontend/components/site/companies-mega-menu.tsx` — keep, do not change
- `frontend/components/site/mobile-menu.tsx` — extend to add the same CTA pill at the bottom
- `frontend/components/site/theme-toggle.tsx` — wrap with the new icon-button style
- `frontend/components/ui/button.tsx` — keep, this PR introduces a new IconButton primitive alongside it
- `frontend/lib/site-config.ts` — `NAV_ITEMS` (no IA change required)
- `frontend/lib/public-api.ts` — `getSiteSettings()` (we'll read the CTA label/href from here)
- `frontend/tailwind.config.ts` — confirm the pug-green and pug-gold tokens exist
- `frontend/app/(public)/layout.tsx` — confirms `<Navbar />` placement; passes `companies` prop

# Files this PR creates

- `frontend/components/site/icon-button.tsx` — new circular icon button primitive (36×36)
- `frontend/components/site/nav-cta.tsx` — the gold CTA pill (reads label + href from site settings, falls back to "Join Us" → /careers)
- `frontend/hooks/use-once-per-session.ts` — small hook to gate the logo entrance animation
- `frontend/hooks/use-prefers-reduced-motion.ts` — IF NOT already present in the repo; reuse if it is

# Logo entrance animation spec

In `components/site/logo.tsx`, refactor so:

1. The component wraps both `<Image>` tags in a `<motion.span>` (Framer Motion is already a dep — confirm in `package.json`)
2. On mount, run the entrance animation ONCE per browser session (gated by `useOncePerSession("pug-logo-intro")`)
3. Animation timing:
   - Mandala: `initial={{ scale: 2.2, rotate: -12, opacity: 0 }}` → `animate={{ scale: 1, rotate: 0, opacity: 1 }}` with `transition={{ type: "spring", stiffness: 120, damping: 14, mass: 0.9 }}` (~1.4 s total with a small overshoot)
   - Wordmark: rises 8 px from below + fades in, `duration: 0.7s, ease: "easeOut", delay: 0.6s`
   - Petal shimmer: continuous, after entrance — opacity 0.95 → 1.0 + filter brightness 1 → 1.15 pulse over 3 s, infinite alternate. Apply as a CSS class added once entrance finishes
4. Honour `prefers-reduced-motion`: skip the entrance, render at final state immediately, no shimmer
5. The component should expose a `disableAnimation` prop (boolean) so admin-shell and footer instances of the logo can opt out

The current PNG-with-wordmark approach stays — we are animating the *container*, not the SVG paths. The mandala-only and full-logo+wordmark variants both get the animation. For finer-grained mandala-vs-wordmark splitting (so they can animate on different timings as specified), update the Logo so that when `showWordmark=true` it renders two stacked images side-by-side instead of one combined image:

- Left: the mandala mark (`/logo-mark.png`) — gets the scale/rotate entrance
- Right: the wordmark text rendered as text (if a brand font is available) OR a separate wordmark PNG if we have one

If a separate wordmark asset doesn't exist yet, surface that in the plan. Two options:
(a) Use the existing combined `logo.png` and animate it as one element (acceptable but the wordmark and mandala can't animate on different timings).
(b) I provide a wordmark-only asset later — for this PR, animate the combined image as one element and leave a TODO comment for the future split.

Default to option (a) for v1 — the combined animation still looks great and ships today.

# Petal shimmer

Implement as a CSS keyframe defined in `styles/globals.css`:

```css
@keyframes pug-petal-shimmer {
  0%, 100% { opacity: 0.95; filter: brightness(1); }
  50% { opacity: 1; filter: brightness(1.10); }
}
.pug-petal-shimmer {
  animation: pug-petal-shimmer 3s ease-in-out infinite;
}
```

Add the class to the logo container *after* the entrance animation completes (use `onAnimationComplete` from Framer Motion to flip a state, then conditionally apply the class).

# Nav-link underline reveal (hover)

Modify `NavLink` in `navbar.tsx`:

- Keep the existing active-state gradient underline (it works)
- Add a hover-state underline: same gold colour, full-width, `scaleX` 0 → 0.8 from centre, transition 220 ms ease
- When active, hover and active underlines both render — the active underline is fatter / shorter (current behaviour), hover one is full-width thinner
- Use `peer` + `peer-hover` or a pseudo-element via Tailwind's `after:` utilities; do not introduce CSS modules

Example pseudo-element approach:

```tsx
<span className="relative">
  {children}
  <span aria-hidden className="absolute -bottom-1 left-0 right-0 h-[2px] origin-center scale-x-0 rounded-full bg-pug-gold-500/80 transition-transform duration-200 group-hover/nav:scale-x-[0.8]" />
  {active && <span aria-hidden className="absolute -bottom-1 left-1/2 h-[2px] w-6 -translate-x-1/2 rounded-full bg-gradient-to-r from-pug-gold-500 to-pug-green-500" />}
</span>
```

The trigger needs a `group/nav` class on the `<Link>` element. Verify the underline doesn't double-render on the active item — if it does, swap the hover one for `group-hover/nav:scale-x-[0.6]` so they layer differently.

# IconButton primitive

New file `frontend/components/site/icon-button.tsx`:

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  "aria-label": string;
  size?: "sm" | "md";
  variant?: "outlined" | "ghost";
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  function IconButton(
    { className, size = "md", variant = "outlined", ...props },
    ref
  ) {
    return (
      <button
        ref={ref}
        type="button"
        className={cn(
          "inline-flex items-center justify-center rounded-full transition-all",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pug-gold-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
          size === "md" && "h-9 w-9",
          size === "sm" && "h-8 w-8",
          variant === "outlined" &&
            "border border-foreground/15 bg-transparent text-foreground/70 hover:bg-pug-gold-500/15 hover:text-pug-gold-600 hover:border-pug-gold-500/30",
          variant === "ghost" &&
            "bg-transparent text-foreground/70 hover:bg-pug-gold-500/15 hover:text-pug-gold-600",
          className
        )}
        {...props}
      />
    );
  }
);
```

Replace the existing `<Button variant="ghost" size="icon">` instances for search and theme toggle in navbar.tsx with `<IconButton aria-label="...">`. Mobile menu trigger keeps `<Button variant="ghost" size="icon">` since it lives next to other non-icon controls in some layouts — discretion.

# Theme toggle wrap

`components/site/theme-toggle.tsx` currently renders its own button. Refactor so it accepts an optional `as` slot OR simpler: render the sun/moon icon inside an `<IconButton>` instead of its current `<Button>`. Preserve all aria behaviour.

# Nav CTA pill

New file `frontend/components/site/nav-cta.tsx`:

```tsx
"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface NavCtaProps {
  label?: string | null;
  href?: string | null;
  className?: string;
}

const FALLBACK = { label: "Join Us", href: "/careers" };

export function NavCta({ label, href, className }: NavCtaProps) {
  const text = (label ?? "").trim() || FALLBACK.label;
  const url = (href ?? "").trim() || FALLBACK.href;
  return (
    <Link
      href={url}
      className={cn(
        "group/cta inline-flex items-center gap-1.5 rounded-full bg-pug-gold-500 px-4 py-2 text-xs font-medium tracking-wide text-white shadow-sm transition-all",
        "hover:-translate-y-0.5 hover:shadow-[0_6px_16px_rgba(196,153,99,0.32)] hover:bg-pug-gold-500",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pug-gold-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className
      )}
    >
      {text}
      <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover/cta:translate-x-0.5" />
    </Link>
  );
}
```

Wire it into navbar.tsx:

- Hide on small screens (`hidden md:inline-flex`) — mobile gets the CTA inside the `MobileMenu` instead
- Read label + href from `getSiteSettings()` — add two new optional fields to `SiteSetting`: `nav_cta_label` and `nav_cta_href`. If null/empty, falls back to "Join Us" → "/careers"

# Site settings extension (backend)

In `backend/app/models/cms.py` extend `SiteSetting`:

```python
nav_cta_label: Mapped[Optional[str]] = mapped_column(String(60))
nav_cta_href: Mapped[Optional[str]] = mapped_column(String(255))
```

In `backend/app/schemas/cms.py` extend `SiteSettingsRead` and `SiteSettingsUpdate`:

```python
nav_cta_label: Optional[str] = Field(default=None, max_length=60)
nav_cta_href: Optional[str] = Field(default=None, max_length=255)
```

New Alembic migration `backend/migrations/versions/20260524_0008_navbar_cta.py`:

- `revision = "20260524_0008"`, `down_revision = "20260524_0007"` (or whatever the latest revision is — read `alembic_version` in the DB or the latest migration file)
- `upgrade`: `op.batch_alter_table("site_settings")` adds both columns
- `downgrade`: drop both columns

Admin: extend `frontend/app/admin/settings/page.tsx` form with two new text inputs in a "Header CTA" group.

# Scroll-pill behaviour (optional, behind feature flag)

Add `NEXT_PUBLIC_NAVBAR_SCROLL_PILL` env var. When `"1"`, after the user scrolls past 80 px:

- Outer `<header>` gains `inset-x-4 top-4` (was `inset-x-0 top-0`)
- The inner container gets `rounded-full border-pug-gold-500/25 bg-background/85 shadow-[0_10px_30px_rgba(0,0,0,0.10)]`
- All four corners round to `999px`
- Transition 350 ms cubic-bezier(0.4, 0, 0.2, 1)

The current `scrolled` state already exists — extend it with a `scrolledFar` second threshold. When the flag is off, behaviour is identical to today's (just blur + border at >8 px scroll).

Default the env var to off. Ship dark. The PR description should mention how to enable it locally for QA.

# Mobile menu parity

In `components/site/mobile-menu.tsx`, append the same `<NavCta />` at the bottom of the menu items list, full-width:

```tsx
<NavCta className="mt-auto w-full justify-center text-sm py-3" />
```

This way the CTA isn't only desktop-visible.

# Accessibility requirements

- Logo entrance animation must respect `prefers-reduced-motion: reduce` → no scale/rotate, no shimmer
- All new IconButtons have visible focus rings (gold ring, 2 px, offset 2 px)
- CTA pill has the same focus ring treatment
- Hover-underline is decorative — keep `aria-hidden`, never replace the active-state indicator
- Tab order: Logo → 7 nav items → Search → Theme → CTA → (Mobile menu on small screens). Verify with keyboard test
- Screen reader announcement of the active nav item is unchanged (the active indicator is `aria-hidden`; active state is conveyed via `aria-current="page"` — add this to `<NavLink>` when `active` is true if it isn't already)
- The CTA pill text must NOT rely on the gold colour alone to convey importance — it has text, an icon, and shape distinct from nav links, which satisfies WCAG

# Tests

Frontend (RTL):
- `Logo` renders without entrance animation when `prefers-reduced-motion` is set (mock matchMedia)
- `Logo` animation runs once per session (mount, unmount, remount within same session → second mount doesn't re-animate)
- `IconButton` forwards refs and renders aria-label
- `NavCta` falls back to "Join Us" → "/careers" when settings are empty
- `NavCta` renders custom label and href when settings provide them
- `Navbar` shows CTA on md+ screens, hides on smaller

Backend:
- `test_site_settings_nav_cta_round_trip`: PATCH `nav_cta_label` + `nav_cta_href`, GET returns the new values
- `test_alembic_upgrade_downgrade`: clean rollback

# Acceptance criteria

- Home page first load: mandala scales in from 2.2× with rotate overshoot, wordmark rises after, petals shimmer continuously thereafter
- Second navigation within the same session: logo renders at final state, no re-animation
- Hover any nav link: gold underline grows from centre in ~220 ms
- Search and theme toggle render as outlined circular icon buttons; hover lights them in pug-gold
- Gold "Join Us →" pill visible on the right at md+; clicking goes to `/careers` by default
- Admin → Site settings has new "Header CTA — label" and "Header CTA — link" inputs; saving them updates the public navbar within the revalidate window
- `prefers-reduced-motion` set: no entrance animation, no shimmer, no hover lift on CTA
- Lighthouse accessibility = 100 on home, about, careers
- No console warnings, no hydration mismatch, no CLS shift caused by the logo container
- `npm run build` clean

# Out of scope for this PR

- Mega menu visual redesign (companies grid stays as-is)
- Full nav IA changes (item order, new items)
- RTL / Arabic language toggle
- Secondary utility row above the main nav (the "Variant C" tracked-caps strip) — separate PR if you want it
- Replacing the wordmark PNG with a brand font — leave a TODO
- New mega-menu types (e.g. for "About Us") — current chevron dropdown stays
- Adapting the admin shell navbar — it uses a different layout

# Working agreement

- Plan first, wait for confirmation
- Atomic commits: (1) backend schema + migration + admin form, (2) IconButton primitive, (3) NavCta component, (4) Logo entrance + shimmer, (5) Navbar wire-up + hover underline, (6) Mobile menu parity, (7) Optional scroll-pill behind flag, (8) Tests
- Run `pytest`, `npm test`, `npm run build` before declaring done. Paste output of each
- Manual QA pass: first load, second load (no re-animation), keyboard tab order, prefers-reduced-motion in DevTools, mobile viewport
- If the wordmark-only asset doesn't exist, surface and default to option (a) per the Logo spec above
````

---

## Notes on using this prompt

Paste the entire fenced block above (everything between the triple backticks under `## PROMPT TO PASTE INTO CLAUDE CODE`) into a fresh Claude Code session. Claude Code will read the relevant files, print a plan, and wait for your confirmation before editing.

The implementation is deliberately conservative about the existing IA: no menu item is added or removed, no dropdown component is replaced, the mega menu for Group Companies stays intact. The only behavioural changes are the logo entrance (gated to once-per-session so it doesn't annoy repeat visitors), the underline reveal, the icon button restyle, and the CTA pill. Everything else is the same Navbar architecture you have today, just better materials.

The CTA pill is wired through `SiteSetting` so marketing can change it anytime ("Join Us" today, "View Careers" during a hiring push, "Investors →" during an earnings cycle) without a code deploy. The two new columns are nullable and fall back to the "Join Us" → "/careers" defaults if either is empty.

The scroll-pill behaviour is behind a feature flag (`NEXT_PUBLIC_NAVBAR_SCROLL_PILL=1`) because some teams prefer the full-width header always; locking it in unconditionally is a stronger statement than a default should make. Ship dark, test with one or two stakeholders, then flip the flag on if you like the feel.

After this PR you'll have one more reusable primitive in your design system (`IconButton`) that other surfaces can adopt — the admin shell topbar is the obvious next consumer, but that's a follow-up PR.

---

*Generated as a planning document for the Paris United Group navbar upgrade. No source code in the project was modified.*
