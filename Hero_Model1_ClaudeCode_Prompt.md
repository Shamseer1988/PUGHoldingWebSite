# Hero Model 1 — Claude Code Implementation Prompt

> Copy the section under **PROMPT TO PASTE INTO CLAUDE CODE** below into a fresh Claude Code session that has this repo open. Everything Claude Code needs to plan, implement, migrate, and ship the new hero is included.

---

## Context for the human

This prompt builds **Model 1** — a cinematic dark, full-bleed hero carousel where each slide can independently be a **video**, an **image**, or a **gradient**. It replaces the gradient-only `components/site/hero-slider.tsx` and extends the `HeroSlide` data model end-to-end (Pydantic schema → SQLAlchemy model → Alembic migration → admin CRUD → admin editor UI → public API client → frontend renderer).

Sample media uses **assets already present in `frontend/public/`** (`public/video/home/paris_group_banner.mp4` and `public/images/home/home_banner.jpg`). A Mux public test URL is provided as a fallback. The schema is identical for self-hosted media or future CDN-hosted media.

Style direction: cinematic dark, AA-contrast overlays, layered text card lower-left, dual CTA, slim progress bar, slide counter, source credit chip. Behaviour: respects `prefers-reduced-motion`, pauses on tab hidden, supports keyboard arrows and swipe, SSRs the first slide for LCP.

---

## PROMPT TO PASTE INTO CLAUDE CODE

````
You are working in the Paris United Group monorepo at the project root. Read CLAUDE.md / README.md / docs/ first if present, then complete the task below. Do not start coding until you have read every file you intend to modify.

# Goal

Replace the current gradient-only home hero with a cinematic dark, full-bleed carousel where each slide can independently be one of three media types: `video`, `image`, or `gradient`. Extend the data model, backend, admin UI, and public renderer end-to-end. Ship behind no flag — direct replacement.

# Visual + behavioural spec (Model 1)

- Full-bleed section, `min-h-[clamp(560px,80svh,840px)]` (use `svh`/`dvh`, not `vh`)
- Media layer (z -20): `<video>` autoplay muted loop playsinline, `<img>` with `object-cover` and per-slide focal point, or a Tailwind gradient — chosen by `media_type`
- Overlay layer (z -10): dark linear gradient `from-black/20 via-black/55 to-black/85` + radial spotlight top-left — tuned for WCAG AA contrast on white text
- Bottom fade to `bg-background` so the hero blends into the next section
- Content (lower-left, max-w-2xl): frosted eyebrow chip with status dot, H1 with `text-balance`, lede paragraph, dual CTA (solid white primary + ghost outline secondary)
- Controls: top-right frosted pill cluster with Pause/Play and Mute (mute only visible when slide is video); bottom-left expanding-dot indicators; bottom-right small media-credit chip + `01 / 04` slide counter; slim 3px progress bar fills with each slide's duration
- First slide must be SSR-rendered (no `motion.div` opacity-0 on initial paint) so it is the LCP element
- Respect `prefers-reduced-motion: reduce` → suppress framer transitions, pause the `<video>`, fall back to poster
- Pause auto-advance via Page Visibility API when the tab is hidden
- Keyboard: `←` previous, `→` next, `Space` toggle pause — only when the carousel is focused (use `tabIndex={0}` on the section)
- Touch: swipe left/right via `pointerdown` / `pointerup` delta (≥ 50 px)
- Screen readers: wrap the rotating text in `<div aria-live="polite" aria-atomic="true">`; indicators get `focus-visible:ring-2 ring-white/80 ring-offset-2 ring-offset-transparent`
- Per-slide auto-advance duration via `duration_ms` (fallback 6500 ms)

# Asset locations & conventions (READ THIS BEFORE TOUCHING CODE)

The repo uses **two distinct asset locations** — do not mix them up:

## A. Frontend static assets (committed to git, manually placed)

Path: `frontend/public/` — served by Next.js at the URL root (`/`). Use this for **default/baseline assets that ship with the codebase**.

Existing convention (already populated):
- `frontend/public/images/<section>/<subsection>/<file>` — e.g. `public/images/home/home_banner.jpg`, `public/images/home/about/`, `public/images/home/services/`
- `frontend/public/video/<section>/<file>` — e.g. `public/video/home/paris_group_banner.mp4`, `public/video/our-company/about_banner.mp4`

For the hero specifically, create and use these subfolders:
- `frontend/public/video/home/hero/` — hero video files (`.mp4`, optional `.webm`)
- `frontend/public/images/home/hero/` — hero still-image slides
- `frontend/public/images/home/hero/posters/` — video poster frames (~120 KB JPEG, first frame at 70 % quality)

In the database, store these as **absolute web paths starting with `/`** — e.g.:
```
video_url:  "/video/home/hero/paris_group_banner.mp4"
poster_url: "/images/home/hero/posters/paris_group_banner.jpg"
image_url:  "/images/home/hero/retail.jpg"
```

The frontend `<video>` / `<img>` tags consume these paths as-is — Next.js serves them statically. The `resolveAssetUrl()` helper in `lib/public-api.ts` already passes through any path that starts with `/` unchanged, so no client change is needed.

## B. Admin-uploaded assets (runtime, content-hashed)

Path: backend `<upload_dir>/cms/` — served via the existing `StaticFiles` mount at `/api/v1/uploads/cms/<filename>`. Used by `components/admin/image-upload.tsx` → `POST /api/v1/admin/cms/uploads/image` (see `app/api/endpoints/admin_cms.py` ~line 740). Files are deduped by SHA-256 hash, returned URLs look like `/api/v1/uploads/cms/abc123def.jpg`.

For the hero, the admin editor must support **both**:
1. **Pasting a path** to an asset that already lives in `frontend/public/` (e.g. `/video/home/hero/x.mp4`) — preferred for hero defaults that should ship with the build
2. **Uploading a new asset** via the existing image-upload component (stores in backend, returns `/api/v1/uploads/cms/...`) — preferred for marketing-team-managed slides

Both URL shapes work in the renderer — no special handling required.

## C. New backend upload endpoint for video

Extend `app/api/endpoints/admin_cms.py` with a sibling endpoint:

```
POST /api/v1/admin/cms/uploads/video
```

Mirror the existing `upload_image` handler but:
- `ALLOWED_VIDEO_MIME = {"video/mp4": "mp4", "video/webm": "webm"}`
- `MAX_VIDEO_BYTES = 25 * 1024 * 1024` (25 MB hard cap — corporate sites should never autoplay larger)
- Same content-hash dedupe, same `<upload_dir>/cms/` location, returns `/api/v1/uploads/cms/<hash>.<ext>`
- Same audit log entry (action `cms.upload.video`)

Extend `components/admin/image-upload.tsx` (or fork into `media-upload.tsx`) so it accepts an `accept` prop (`"image/*"` or `"video/mp4,video/webm"`) and calls the matching backend endpoint based on which one is in use.

## D. Path validation (frontend types)

In `lib/admin/types.ts`, the new media URL fields are typed as `string | null` — but add a runtime helper:

```ts
// lib/hero-assets.ts
export function isLocalAsset(url: string | null): boolean {
  return !!url && url.startsWith("/") && !url.startsWith("//");
}
export function isUploadedAsset(url: string | null): boolean {
  return !!url && url.startsWith("/api/v1/uploads/");
}
```

Use these in the admin editor to show a small badge ("Local · `/public/video/...`" vs "Uploaded · CMS") so admins know what they're looking at.

---

# Backend — schema changes

## 1. `backend/app/models/cms.py` → extend `HeroSlide`

Add the following columns (all nullable except `media_type` and `overlay_opacity` which have defaults):

```python
media_type: Mapped[str] = mapped_column(
    String(16), nullable=False, default="gradient", server_default="gradient"
)  # "video" | "image" | "gradient"
video_url: Mapped[Optional[str]] = mapped_column(String(500))
video_webm_url: Mapped[Optional[str]] = mapped_column(String(500))
poster_url: Mapped[Optional[str]] = mapped_column(String(500))
image_url: Mapped[Optional[str]] = mapped_column(String(500))
focal_x: Mapped[Optional[int]] = mapped_column(Integer)   # 0–100
focal_y: Mapped[Optional[int]] = mapped_column(Integer)   # 0–100
overlay_opacity: Mapped[int] = mapped_column(
    Integer, nullable=False, default=60, server_default="60"
)  # 0–100
theme: Mapped[str] = mapped_column(
    String(8), nullable=False, default="dark", server_default="dark"
)  # "dark" | "light"
align: Mapped[str] = mapped_column(
    String(8), nullable=False, default="left", server_default="left"
)  # "left" | "center"
duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
video_credit: Mapped[Optional[str]] = mapped_column(String(120))
```

## 2. `backend/app/schemas/cms.py` → extend Pydantic schemas

Add a `Literal` for `media_type`, `theme`, `align`. Add the new fields to `HeroSlideBase`, `HeroSlideCreate` (inherits Base), `HeroSlideUpdate` (all Optional), `HeroSlideRead` (inherits Base). Validate `focal_x/focal_y` and `overlay_opacity` to range `0..100`. Validate `media_type='video'` requires `video_url`; `media_type='image'` requires `image_url`. Add a model validator on `HeroSlideBase` to enforce these constraints.

## 3. Alembic migration

Create `backend/migrations/versions/20260524_0003_hero_slide_media.py` that:
- adds all the columns above to `hero_slides` (server defaults for non-null ones so existing rows are valid)
- on `downgrade` drops them

Use `op.add_column` / `op.drop_column`. Reference the latest existing migration in `down_revision`.

## 4. Seed data

Update `backend/app/scripts/seed_cms.py` so the seeded hero slides include at least one of each `media_type`, **prioritizing assets that already exist in `frontend/public/`**:

- **Slide 1 (video, local asset that already ships in the repo):**
  - `media_type="video"`
  - `video_url="/video/home/paris_group_banner.mp4"`  *(already exists)*
  - `poster_url="/images/home/home_banner.jpg"`  *(already exists)*
  - `video_credit="Paris United Group"`
  - `duration_ms=8000`
- **Slide 2 (image, local asset):**
  - `media_type="image"`
  - `image_url="/images/home/home_banner.jpg"`  *(already exists — replace with a hero-specific JPG dropped into `/images/home/hero/` when one is provided)*
  - `focal_x=50`, `focal_y=40`
- **Slide 3 (gradient fallback):**
  - `media_type="gradient"`
  - Keep the existing PUG gradient string (`from-pug-green-700 via-pug-green-500 to-pug-gold-500`)
- **Optional Slide 4 (video, remote Mux sample — only seeded in non-production envs, gated by env var):**
  - `media_type="video"`
  - `video_url="https://stream.mux.com/VZtzUzGRv02OhRnZCxcjVPJHo7YuNwJSq/low.mp4"`
  - `poster_url="https://image.mux.com/VZtzUzGRv02OhRnZCxcjVPJHo7YuNwJSq/thumbnail.jpg?time=2"`
  - `video_credit="Mux sample"`

Before adding more hero subfolders or new assets, **check `frontend/public/video/home/` and `frontend/public/images/home/` first** — reuse what already ships.

Seed must be idempotent (upsert by `title` or clear-and-reseed depending on how the file already works).

# Backend — endpoints

`backend/app/api/endpoints/admin_cms.py` and `backend/app/api/endpoints/public.py` already expose `HeroSlide` CRUD via `HeroSlideRead`. No new CRUD endpoints required — the schema extension is enough.

**New endpoint required**: `POST /api/v1/admin/cms/uploads/video` (see "Asset locations & conventions" section above for full spec). Mirror the existing `upload_image` handler, accept `video/mp4` + `video/webm`, cap at 25 MB.

Add server-side validation: if `media_type='video'` and no `video_url`, return 422; same for `image`.

# Frontend — types

`frontend/lib/admin/types.ts` — mirror the new Pydantic schema:

```ts
export type HeroMediaType = "video" | "image" | "gradient";
export type HeroTheme = "dark" | "light";
export type HeroAlign = "left" | "center";

export interface HeroSlide {
  id: number;
  eyebrow: string | null;
  title: string;
  description: string | null;
  cta_label: string | null;
  cta_href: string | null;
  secondary_cta_label: string | null;
  secondary_cta_href: string | null;
  gradient: string;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // new
  media_type: HeroMediaType;
  video_url: string | null;
  video_webm_url: string | null;
  poster_url: string | null;
  image_url: string | null;
  focal_x: number | null;
  focal_y: number | null;
  overlay_opacity: number;     // 0–100
  theme: HeroTheme;
  align: HeroAlign;
  duration_ms: number | null;
  video_credit: string | null;
}
```

# Frontend — components

Split the existing `frontend/components/site/hero-slider.tsx` into three files:

1. `frontend/components/site/hero/hero.tsx` — **server component**
   - Takes `slides: HeroSlide[]`
   - Renders the section shell, the first slide's media + text statically (so H1 + poster are SSR'd → LCP)
   - Mounts `<HeroCarousel slides={slides} />` (client) as a child for the interactive layer

2. `frontend/components/site/hero/hero-carousel.tsx` — `"use client"`
   - Owns: current index, paused state, focus state
   - Handles: auto-advance (per-slide `duration_ms`), Page Visibility pause, `prefers-reduced-motion`, keyboard ←/→/Space, swipe gestures
   - Renders: text content (with `aria-live="polite"`), indicators, pause/play, slide counter, progress bar
   - Crossfades media via Framer Motion `AnimatePresence`, but the initial frame for slide 0 matches SSR exactly to avoid hydration flicker

3. `frontend/components/site/hero/hero-media.tsx` — `"use client"`
   - Props: a single `HeroSlide`
   - Renders one of `<video>` / `<img>` / gradient `<div>` based on `slide.media_type`
   - `<video autoPlay muted loop playsInline preload="metadata" poster={poster_url}>` with `<source src={video_webm_url} type="video/webm">` first (if set), then `<source src={video_url} type="video/mp4">`
   - Pauses the video when `prefers-reduced-motion` is set or the carousel is paused; resumes on play
   - `object-cover` with `objectPosition: \`${focal_x ?? 50}% ${focal_y ?? 50}%\``
   - `pointer-events-none` so the H1/CTAs receive clicks
   - Inline `<img>` fallback inside `<video>` for browsers that block autoplay

Add `frontend/components/site/hero/index.ts` that re-exports `Hero` so `app/(public)/page.tsx` can `import { Hero } from "@/components/site/hero"`.

Delete `frontend/components/site/hero-slider.tsx` after the new `Hero` is wired in; update the import in `app/(public)/page.tsx`.

# Frontend — public API client

`frontend/lib/public-api.ts` — `getHeroSlides()` returns `HeroSlide[]`. Already does. No code change required — the API now returns the new fields automatically.

# Frontend — admin editor

`frontend/app/admin/hero-slides/page.tsx` — extend the form:
- Add a `<select>` for `media_type` (Video / Image / Gradient). On change, show/hide the relevant fields:
  - `video` → file/url inputs for `video_url`, `video_webm_url`, `poster_url`, `video_credit`
  - `image` → file/url input for `image_url`, plus `focal_x`/`focal_y` number inputs (0–100)
  - `gradient` → existing `gradient` text input
- Add `overlay_opacity` (range slider 0–100, default 60)
- Add `theme` toggle (Dark / Light)
- Add `align` toggle (Left / Center)
- Add `duration_ms` number input (placeholder "6500", optional)
- For `poster_url` and `image_url`: reuse `components/admin/image-upload.tsx` (uploads to `/api/v1/admin/cms/uploads/image` → returned URL stored as-is)
- For `video_url` and `video_webm_url`: use the **new** media-upload component (or extended `image-upload` with `accept` prop) that calls `/api/v1/admin/cms/uploads/video`. Also accept manual URL entry so admins can paste:
  - a local `frontend/public/` path (e.g. `/video/home/hero/x.mp4`)
  - a CDN URL (Mux / Cloudflare Stream / Vimeo Pro direct MP4)
- Next to each URL field, render a small badge using the `isLocalAsset` / `isUploadedAsset` helpers from `lib/hero-assets.ts`:
  - `/video/...` or `/images/...` → blue badge "Local · /public asset"
  - `/api/v1/uploads/cms/...` → green badge "Uploaded via CMS"
  - `http(s)://...` → gray badge "External"
- Add a help line under the video URL field: *"Drop new videos in `frontend/public/video/home/hero/` and reference them as `/video/home/hero/filename.mp4`, or upload via the button above."*
- Validate client-side: video type requires `video_url`; image type requires `image_url`. Disable Save until valid.

# Performance + a11y acceptance criteria

- Lighthouse mobile: Performance ≥ 90, Accessibility = 100, Best Practices ≥ 95 on the home route
- LCP element on first paint is the hero poster `<img>` (or the H1 if no media). Add `fetchPriority="high"` on the poster of slide 0 only
- `preload="metadata"` on every `<video>` — never `"auto"`
- Honor `prefers-reduced-motion: reduce` (manual test in DevTools)
- All interactive elements reachable via keyboard with a visible focus ring
- Screen reader (VoiceOver / NVDA) announces eyebrow + title when slide rotates (verified by `aria-live` region)
- No hydration warnings in console
- Bundle size impact: hero JS gzipped ≤ 10 KB above current (measure with `next build`)

# Tests

Backend (pytest, alongside existing tests in `backend/tests`):
- `test_hero_slide_media_validation`: posting `media_type='video'` without `video_url` returns 422
- `test_hero_slide_media_round_trip`: create + read + update + read returns all new fields correctly
- `test_alembic_upgrade_downgrade`: upgrade then downgrade leaves no residual columns

Frontend:
- Snapshot/RTL test for `Hero` rendering each `media_type`
- Smoke test that pressing `→` advances the slide index

# Out of scope for this PR

- Hero on non-home pages (those use `PageHero`, untouched)
- Server-side video transcoding / poster generation (admin must upload an already-encoded `.mp4` and a separate poster `.jpg`)
- Mux/Cloudflare Stream account wiring (we paste raw URLs or use the local upload endpoint)
- Per-slide focal point cropping for video (only images get focal point in v1)
- Theme=light variant styling (schema field accepted, renderer only ships `dark` in v1 — log a TODO)
- Migrating existing miscellaneous assets in `public/images/` and `public/video/` into the new `home/hero/` subfolders — only place *new* hero assets there; leave the rest of the tree as it is

# Working agreement

- Plan first. Print a numbered file-by-file plan and wait for me to confirm before editing.
- Make atomic commits per logical change (model, schema, migration, seed, types, hero component, admin editor, tests). Conventional commit prefixes.
- Run `pytest` and `pnpm/npm test` and `pnpm/npm run build` before declaring done. Paste the final output of each.
- If anything in this spec conflicts with code you find in the repo, surface it before changing — don't guess.
````

---

## Notes on using this prompt

Paste the entire fenced block above (everything between the triple backticks under `## PROMPT TO PASTE INTO CLAUDE CODE`) into a fresh Claude Code session. Claude Code will read the relevant files itself, print a plan, and wait for confirmation before editing.

The repo already ships with `frontend/public/video/home/paris_group_banner.mp4` and `frontend/public/images/home/home_banner.jpg` — the seed data uses these as the default Slide 1 so the hero works out of the box with zero extra asset prep. Drop additional hero footage into `frontend/public/video/home/hero/` and posters into `frontend/public/images/home/hero/posters/` as you produce them.

The sample Mux URL (`stream.mux.com/VZtzUzGRv02OhRnZCxcjVPJHo7YuNwJSq`) is a public test asset and is safe to use during development. Swap to your own Mux/Vimeo Pro asset or another self-hosted MP4 when going live.

The schema is forward-compatible: adding more media providers later (HLS, DASH, Cloudflare Stream) only requires a new `media_type` literal and a renderer branch in `hero-media.tsx` — no migration.
