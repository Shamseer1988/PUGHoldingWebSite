# Paris United Group Holding — Hero Video Production Brief

For commissioning a custom 12–18 second background video for the homepage hero. Hand this document to a videographer, motion designer, or stock-footage curator.

---

## Brand snapshot

- **Brand:** Paris United Group Holding
- **Sector:** Diversified holding group (distribution, retail, services) — Qatar
- **Mark:** Gold (`#C49963` / `#D4A574`) lotus-mandala emblem on dark background
- **Wordmark:** Classical serif, gold, all caps with wide tracking and a "HOLDING" sub-tag
- **Personality:** Heritage, trust, longevity, patience, refined, Middle-Eastern luxury fused with French elegance
- **Adjectives to chase:** cinematic, calm, dignified, monumental, warm
- **Adjectives to avoid:** corporate-stock, generic, busy, neon, frantic, "tech startup"

## Deliverable spec

| Field | Value |
|---|---|
| Duration | 12–18 seconds, seamless loop |
| Aspect | 16:9 master + 9:16 reframe for mobile (or shoot 16:9 with safe-action in centre 9:16) |
| Resolution | 1920 × 1080 master (provide 1280 × 720 web-optimised export) |
| Codec | H.264 MP4 (primary) + VP9 WebM (secondary) |
| File size | ≤ 4 MB for web-optimised export. Hard cap 6 MB |
| Audio | None — hero plays muted |
| Color | Cinematic dark grade, warm gold highlights, deep black shadows. Avoid pure white and saturated reds |
| Frame rate | 24 fps (cinematic) — never 60 |
| Bitrate | ~2.5 Mbps target |
| First frame | Must work as a poster JPEG (LCP image), so compose it deliberately |

## Visual direction

### Concept A — "Heritage in motion" (recommended)
Slow, deliberate camera moves over architectural and material details. No people. The viewer feels like they're walking through a quiet, well-built place at golden hour. Sequence ideas (pick 2–3, hold each ~5 seconds):

- Sunrise light raking across a brass mandala or geometric latticework
- Slow dolly along a marble corridor with warm pendant lighting
- Detail shot: gold leaf, brass switch, polished stone, fabric weave
- Wide dusk shot of Doha skyline with a single distant moving cargo ship or aircraft for subtle life
- Hand placing a small object (kept anonymous — no face) on a velvet surface

### Concept B — "Abstract gold motion" (lower budget alternative)
Pure motion graphics. Gold particles, slow ink-in-water, silk waves, light-ray sweeps — all in the brand palette. Easier to commission, easier to find as stock. Works well with the mandala as a subtle overlay.

### Concept C — "Operational scale" (B2B / investor variant)
If the hero is rotating slides, this is the **second** slide. Cold-chain truck doors opening, retail-floor wide shot before opening hour, distribution warehouse with conveyor belt. Same dark grade, same patience. Holds up over many viewings.

## Composition rules

- Subject **off-centre** — leave the left 40 % of the frame visually quieter so the headline and lockup land cleanly over it
- Movement should be **slow and continuous** — no cuts, no zooms, no whip pans
- Avoid bright skies on the left third of the frame (kills text contrast)
- The frame should look intentional as a still — that still is your LCP poster image

## Color grade

- Lift shadows just enough to keep detail in the blacks (do not crush)
- Push midtones warm (orange-gold around 3200K feel)
- Desaturate everything except gold/amber tones (subtle teal-orange split, but the teal is barely there)
- No lens flare, no chromatic aberration effects, no film grain overlay (keeps file size down)

## Motion design overlay (optional, post-production)

If desired, the videographer or motion artist can add a **very subtle** rotating outline of the PUG mandala in one of the dimmer areas of frame — like a brand watermark embossed in the image. Maximum 8–10 % opacity. Rotation period ~30 seconds. This is a nice touch but only if it doesn't read as added-on.

## Loop requirements

- The last 1 second of footage should match the first 1 second of footage in **luminance, composition, and motion vector** so the loop is invisible
- Cross-fade between end and start in post (~24 frames) if a clean match isn't possible in-camera
- Test the loop on a 30-second playthrough — if you can tell where it cuts, redo it

## Poster frame (LCP image — critical)

- Export frame 1 (or whichever frame is the most composed-looking still) as a separate JPEG at 1920 × 1080
- Re-encode to ~120 KB at 70 % quality, progressive JPEG
- This becomes the `poster_url` in the hero CMS — it's what the user sees before the video has buffered, and what search engines see as the LCP element

## File delivery

Deliver into a single zip containing:

```
/paris_united_group_hero_v1/
  master_1920x1080.mov          (ProRes 422 LT or similar — for archive)
  hero_1280x720.mp4             (H.264, web-optimised, ≤ 4 MB)
  hero_1280x720.webm            (VP9, web-optimised, ≤ 3 MB)
  hero_mobile_720x1280.mp4      (9:16 reframe)
  poster_1920x1080.jpg          (full quality)
  poster_web_1920x1080.jpg      (≤ 120 KB)
  poster_mobile_720x1280.jpg    (≤ 90 KB)
  README.txt                    (loop point, color notes, attribution if stock)
```

## Where the files go in the project

Once delivered, place the files in the frontend public folder (matches the existing convention in `public/video/home/` and `public/images/home/`):

```
frontend/public/video/home/hero/
  paris_united_group_hero_v1.mp4
  paris_united_group_hero_v1.webm
  paris_united_group_hero_v1_mobile.mp4

frontend/public/images/home/hero/posters/
  paris_united_group_hero_v1.jpg
  paris_united_group_hero_v1_mobile.jpg
```

Then in the admin CMS, create a Hero Slide with:

- `media_type` = `video`
- `video_url` = `/video/home/hero/paris_united_group_hero_v1.mp4`
- `video_webm_url` = `/video/home/hero/paris_united_group_hero_v1.webm`
- `poster_url` = `/images/home/hero/posters/paris_united_group_hero_v1.jpg`
- `video_credit` = Studio name (or blank for in-house)
- `duration_ms` = 8000 (or to match the loop length × 1000)
- `overlay_opacity` = 60

## Stock-footage alternative

If commissioning isn't feasible, the brief above doubles as a curation prompt. Search the following royalty-free libraries for clips that match the spec:

- pexels.com/videos — keywords: "gold dust particles black", "marble texture", "doha skyline dusk", "warm interior dolly", "gold silk slow motion"
- mixkit.co/free-stock-video — luxury / interior / abstract categories
- coverr.co — cinematic / hero categories

License terms vary — verify each clip is cleared for commercial use in Qatar before shipping.

## Budget guidance (informational)

- Curated stock footage: free (Pexels / Mixkit / Coverr) to ~$200 (Storyblocks / Artgrid)
- Motion-graphics-only abstract piece (animator): $400–1,200
- Half-day shoot in Doha with a local DP + grade: $1,500–4,000
- Full brand film with multiple sequences and motion overlay: $5,000–15,000

## Approval gates

1. **Storyboard / mood board** — text + reference stills before any shooting or animation begins
2. **Rough cut** — colour and pacing in place, no final grade
3. **Final delivery** — all files in the structure above, with the loop test verified

---

*Generated as a planning document for the Paris United Group hero rebuild. No source code in the project was modified.*
