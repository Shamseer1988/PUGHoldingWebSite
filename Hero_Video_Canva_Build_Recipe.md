# Paris United Group Holding — Canva Hero Video Build Recipe

A step-by-step Canva recipe for building an 8-second seamless-loop hero background video in two formats: **desktop 1920×1080 (16:9)** and **mobile 1080×1920 (9:16)**. No Magic Design or paid plan required — works on any Canva account. Brand direction has been corrected to match the *actual* PUG business: warm, bright, family-focused Qatar retail and distribution, with the gold mandala as the premium signature.

---

## Quick reference

| Field | Value |
|---|---|
| Brand kit ID in Canva | `kAGqCNUFqeU` (already on your account) |
| Brand gold | `#C49963` primary, `#D4A574` light, `#8B6F3F` deep |
| Background base | `#0A0E1A` deep charcoal (for vignette/text panel) |
| Text on dark | `#FFFFFF` headline, `rgba(255,255,255,0.78)` lede |
| Primary serif (headlines + wordmark) | Cinzel, Cormorant Garamond, or Playfair Display |
| Secondary sans (small UI) | Inter, Montserrat, or Poppins (medium 500) |
| Duration | 8.0 seconds exactly |
| Frame rate | 30 fps (Canva default) |
| Aspect: desktop | 1920 × 1080, 16:9 |
| Aspect: mobile | 1080 × 1920, 9:16 |
| Output | MP4 H.264, target ≤ 4 MB after compression |

---

## Storyboard — 8-second loop

Scene-by-scene timing. Both formats follow the same beats, only the framing differs.

| Time | Background image | Foreground action |
|---|---|---|
| 0.0 – 2.5 s | Warm-lit fresh-produce aisle, family choosing tomatoes (Scene A) | Gold mandala fades in (top centre / left), brand wordmark slides up beneath it |
| 2.5 – 5.0 s | Crossfade to mother + daughter at the shelves, golden bokeh (Scene B) | Headline "A heritage of trust." fades in word by word, then "A family of brands." in gold italic |
| 5.0 – 7.5 s | Crossfade to woman with full cart of fresh groceries (Scene C) | Two CTA pills appear: solid gold "Discover the group →" and ghost "Visit our stores" |
| 7.5 – 8.0 s | Crossfade back into Scene A's first frame | Headline + CTAs hold briefly, then crossfade with the start |

The crossfade from Scene C back to Scene A is what makes the loop seamless — both endpoints share the same image, so the playhead snap is invisible.

---

## Step 1 — Create the desktop canvas

1. Open Canva → **Create a design** → **Custom size** → enter **1920 × 1080 px**, click **Create new design**
2. Rename top-left: `PUG Hero — Desktop 16x9`
3. **Apply brand kit**: click `…` menu → **Brand** → select your kit (`kAGqCNUFqeU`)
4. Change page background colour to **`#0A0E1A`** (Page → Background colour → custom hex)

## Step 2 — Add the three scene images

In Canva, click **Elements → Photos** and search the following terms — pick photos that match the description in parentheses. All should be **warm-toned, brightly lit, real families, NOT cold supermarket stock**:

| Slot | Search term in Canva | Pick a photo that shows… |
|---|---|---|
| Scene A (0–2.5s) | `family supermarket produce` | Parents + child near tomatoes/peppers, smiling, warm lighting |
| Scene B (2.5–5.0s) | `mother daughter grocery shopping` | Mom and child at shelves, joyful, golden-bokeh background |
| Scene C (5.0–7.5s) | `woman shopping cart vegetables` | Woman pushing a full cart of fresh produce, warm aisle lighting |

For each photo:
- Drag onto the canvas, **stretch to fill the full 1920 × 1080 frame**
- Crop so the *visual subject is on the right two-thirds* of the frame — left third must stay relatively quiet so the text reads cleanly
- Apply Canva's **Photo Edit → Adjust → Warmth +15, Tint +5, Saturation -10** so all three shots share one grade
- Apply **Filter → "Epic" or "Cali"** at ~40 % strength to lock the warm cinematic look

## Step 3 — Add the dark gradient overlay

On top of every scene image, add a left-to-right dark gradient so the text panel stays readable:

1. **Elements → Shapes → Rectangle**, stretch to full frame
2. Fill: **Gradient → Linear → Left to right**
3. Left stop: **#0A0E1A** at **85 % opacity**
4. Right stop: **#0A0E1A** at **0 % opacity**
5. Gradient angle: 90° (horizontal)

Duplicate this overlay and place one over **every** scene image (or use **Position → Send to back of layer group** to apply to all).

## Step 4 — Add the brand lockup (left column, vertically centred)

The lockup stays on screen the entire 8 seconds. Build it once and pin it.

1. **Uploads → Upload from device** → upload `logo-mark.png` from `frontend/public/logo-mark.png`
2. Drag the mandala onto the canvas. Resize to **120 × 120 px**
3. Position: **x = 96, y = 240** (left margin 96 px, vertically about a third down)
4. **Animate** → **Rise** at 1.2 s duration starting at 0.0 s

5. Add **Text → Heading** with text `PARIS UNITED`
   - Font: Cinzel or Playfair Display, **Bold/Black, size 56**, colour **#D4A574**
   - Letter spacing: **80** (very wide tracking)
   - Position directly below the mandala
6. Duplicate the text, change to `GROUP` — same style, below the first line
7. Add a thin gold rule (Elements → Lines → solid line, 1 px, colour #C49963, width 140 px) below the wordmark
8. Add **Text → Subheading** `— HOLDING —`
   - Font: Cinzel, **Regular, size 16**, colour **#8B6F3F**
   - Letter spacing: **300** (extreme tracking for the heritage feel)
9. Group all four elements (Shift-click → Cmd/Ctrl + G) and animate the group with **Rise** at 1.4 s starting at 0.2 s

## Step 5 — Add the headline (centre-left, dominates the frame)

Two-line serif headline that fades in word by word during scene B:

1. **Text → Heading** with `A heritage of trust.`
   - Font: Cormorant Garamond or Playfair Display, **Regular, size 80**
   - Colour: **#FFFFFF**
   - Position: x = 96, y = 500
2. Below it: `A family of brands.`
   - Same font, **Italic, size 80**
   - Colour: **#D4A574** (brand gold)
3. Animate both lines: **Animate → Fade** with 0.6 s duration, starting at 2.5 s (first line) and 3.0 s (second line)

## Step 6 — Add the CTA pills (below headline)

1. **Elements → Shapes → Rounded rectangle**, size 220 × 48 px, corner radius 4 px
2. Fill: **#D4A574** (solid gold)
3. Add text on top: `DISCOVER THE GROUP →` — Inter / Montserrat **Medium 500, size 13**, letter spacing 100, colour **#0A0E1A**
4. Group the shape + text
5. Duplicate beside it (8 px gap). Change duplicate to: fill transparent, stroke `#D4A574` 0.5 px, text colour `#D4A574`, change text to `▶ VISIT OUR STORES`
6. Position both pills at x = 96, y = 720
7. Animate the pill group: **Animate → Rise** with 0.8 s duration, starting at 5.0 s

## Step 7 — Add the small brand chip (top-right)

For the heritage signature in the corner:

1. **Text → Body** `EST. QATAR · 1998` — Inter Medium size 11, letter spacing 300, colour **#D4A574**
2. Position: top-right corner, x = 1660, y = 60
3. Add a small gold dot (Elements → Shapes → Circle, 6 × 6 px, fill #D4A574) to the left of the text
4. Group, animate **Fade** 0.6 s starting at 0.0 s

## Step 8 — Set up scene transitions on the page timeline

1. Click **…** menu top right → **Timer** → set page duration to **8.0 seconds**
2. For each of the three background photos, in the layers panel:
   - Scene A: visible 0.0 – 3.0 s
   - Scene B: visible 2.5 – 5.5 s
   - Scene C: visible 5.0 – 8.0 s
3. Add **Photo → Animate → Pan + Zoom** on each scene at "Slow" speed (Ken Burns effect — gives the locked camera life)
4. The 0.5 s overlap between scenes is your crossfade window — Canva blends them naturally

## Step 9 — Make the loop seamless

The critical step. In the last 0.5 seconds of the page (7.5 – 8.0 s):

1. Add a fourth instance of Scene A's photo on top
2. Set its opacity to 0 % at 7.5 s, animating to 100 % at 8.0 s (Animate → Fade in)
3. This means at the loop point the canvas is showing Scene A's first frame at full opacity — matching what plays at 0.0 s when the loop restarts

Test the loop by clicking **Play** twice in a row in Canva's preview. If you can see the seam, slow down the final crossfade to a full 1.0 s.

## Step 10 — Export the desktop MP4

1. **Share** (top right) → **Download**
2. File type: **MP4 Video**
3. Quality: **1080p**
4. Pages: leave default (single page)
5. Click **Download** — Canva renders the 8-second MP4 (typically 15–40 MB)

---

## Step 11 — Build the mobile version (9:16)

1. **File → Resize and Magic Switch** (or **Resize**) → enter **1080 × 1920 px** → click **Copy and resize**
2. This creates a new design with all elements transferred. Some will need repositioning:
   - Brand lockup: move to top of canvas (x = 90, y = 240)
   - Headline: centre horizontally, y = 800
   - CTA pills: stack vertically (one above the other), centre horizontally, y = 1450
   - Background scenes: re-crop to keep the family/subject centred in vertical frame
3. Rename: `PUG Hero — Mobile 9x16`
4. Repeat **Step 9** loop seamless step
5. Export same way (Step 10) — result is the vertical MP4

---

## Step 12 — Compress for web

Canva's MP4 is typically 15–40 MB; your hero budget is **≤ 4 MB**. Run these two `ffmpeg` commands on your machine (install with `winget install Gyan.FFmpeg` if needed):

```bash
# Desktop hero — 1280x720 web-optimised
ffmpeg -i pug_hero_desktop_canva.mp4 ^
  -vcodec libx264 -crf 28 -preset slow -profile:v main ^
  -vf "scale=1280:720" -an -movflags +faststart ^
  pug_hero_desktop.mp4

# WebM fallback (smaller for Chrome/Firefox/Edge)
ffmpeg -i pug_hero_desktop_canva.mp4 ^
  -c:v libvpx-vp9 -crf 34 -b:v 0 ^
  -vf "scale=1280:720" -an ^
  pug_hero_desktop.webm

# Mobile hero — 720x1280 web-optimised
ffmpeg -i pug_hero_mobile_canva.mp4 ^
  -vcodec libx264 -crf 28 -preset slow -profile:v main ^
  -vf "scale=720:1280" -an -movflags +faststart ^
  pug_hero_mobile.mp4

# Poster frames (LCP images)
ffmpeg -i pug_hero_desktop_canva.mp4 -ss 00:00:00.5 -vframes 1 -q:v 2 pug_hero_desktop_poster.jpg
ffmpeg -i pug_hero_mobile_canva.mp4 -ss 00:00:00.5 -vframes 1 -q:v 2 pug_hero_mobile_poster.jpg
```

Then optimise the posters to ~120 KB using any image tool (TinyPNG, Squoosh) at 70 % JPEG quality.

---

## Step 13 — Place files in the project

```
frontend/public/video/home/hero/
  pug_hero_desktop.mp4
  pug_hero_desktop.webm
  pug_hero_mobile.mp4

frontend/public/images/home/hero/posters/
  pug_hero_desktop_poster.jpg
  pug_hero_mobile_poster.jpg
```

## Step 14 — Wire it up in the admin CMS

Once your Hero schema migration (from `Hero_Model1_ClaudeCode_Prompt.md`) is deployed, create Hero Slide 1 in the admin:

- `media_type` = `video`
- `video_url` = `/video/home/hero/pug_hero_desktop.mp4`
- `video_webm_url` = `/video/home/hero/pug_hero_desktop.webm`
- `poster_url` = `/images/home/hero/posters/pug_hero_desktop_poster.jpg`
- `video_credit` = `Paris United Group` (or leave blank)
- `duration_ms` = `8000`
- `overlay_opacity` = `40` (lower than the cinematic-dark variant because the video itself is already overlaid in Canva)
- `theme` = `dark`
- `align` = `left`

For mobile, store the mobile variant in the same row using new optional fields (or add `video_url_mobile` to your schema as a follow-up — recommended for any responsive hero implementation).

---

## Photo licensing check (important)

Canva's **Pro Photos** are licensed for commercial use under their content licence (verify your plan covers commercial use — most paid plans do, free plans are limited to non-commercial). If you're on Canva Free, restrict your photo picks to those tagged **Free** in the search results. For Qatar-specific imagery — store openings, local family shoppers, GCC retail — Canva's stock library is thin; consider commissioning a half-day photo shoot at one of your supermarkets and uploading the JPEGs as Canva assets for full rights.

---

## Approval gates

1. **Storyboard alignment** — review the three scene picks before animating
2. **Brand lockup test** — render the first 2 seconds only, confirm the lockup reads cleanly at mobile size (320 px wide preview)
3. **Loop test** — play twice in a row, confirm seam is invisible
4. **Web performance test** — drop into a local Next.js dev environment and confirm MP4 loads ≤ 2 s on throttled 3G

---

## Why this matches your business (not the earlier cinematic-dark direction)

The earlier cinematic-dark, palatial-corridor direction was wrong for PUG. Your real business is **bright, warm, family-focused retail** — Carrefour-Qatar vibe with a heritage gold signature on top, not a dark luxury holding-group aesthetic. This recipe keeps the premium **brand signature** (gold mandala, classical serif wordmark, dignified typography) but lets the **imagery** be what your customers actually experience: shopping with their families in well-lit, welcoming aisles full of fresh produce. The dark gradient is a tool for text legibility, not the dominant mood. The gold accents and serif headline carry the "heritage of trust" — the photos carry the warmth.

---

*Generated as a planning document for the Paris United Group hero rebuild. No source code in the project was modified.*
