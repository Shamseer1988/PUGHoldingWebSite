# Paris United Group Holding — Google Veo 3.1 Prompts

Ready-to-paste prompts for generating the hero background video(s) with Google Veo 3.1 (available via Google Vids, Gemini Advanced, or Vertex AI). Each prompt is tuned for the PUG brand — cinematic dark, warm gold accents, heritage/luxury holding-group feel, no people, no audio dialogue, designed to sit *behind* a headline.

---

## How Veo 3.1 prompts should be structured

Veo responds best to a **single dense paragraph** that names, in this order:

1. **Shot type** (e.g. "extreme close-up", "slow dolly-in", "wide aerial")
2. **Subject** (the thing on screen)
3. **Action** (what it's doing, slowly)
4. **Environment** (where it is)
5. **Lighting** (golden hour, low-key, rim-lit, etc.)
6. **Color palette** (explicit hex or named tones)
7. **Camera move** (dolly, pan, push-in, locked, handheld)
8. **Lens / depth of field** (anamorphic, 35mm, shallow DOF)
9. **Style references** (cinematographer or film names work well)
10. **Mood + duration cue** ("calm, contemplative, slow", "8 seconds, seamless loop")

Avoid bullet lists, multiple sentences shouting separate ideas, or emojis. One long, deliberate paragraph beats fragmented instructions.

---

## Universal settings (apply to every generation)

| Setting | Value |
|---|---|
| Aspect ratio | 16:9 |
| Duration | 8 seconds (Veo 3.1 max per clip) |
| Resolution | 1080p (upgrade to 4K only if you can afford the storage) |
| Audio | Mute / "no dialogue, no music, ambient only" — hero plays muted |
| Generations per prompt | 3–4 takes, pick the best loop candidate |
| Seed | Lock the seed once you find a good take, then iterate on prompt wording |

---

## Prompt 1 — "Heritage in motion" (recommended Slide 1)

Paste this verbatim into Veo 3.1:

```
A slow, deliberate dolly-in shot moving through a quiet, palatial interior corridor at golden hour, the warm sunlight raking diagonally across a polished marble floor and catching the edges of carved brass latticework on the walls, a faint geometric mandala pattern projected by the light onto the floor in the foreground, the camera gliding forward at the pace of a slow exhale, no people visible, no movement other than soft floating dust motes drifting upward through the shafts of warm light, captured on an Arri Alexa with a 40mm anamorphic lens at f/2.8, shallow depth of field with the brass detail in sharp focus and the far end of the corridor falling into soft warm bokeh, color palette of deep charcoal black 0x07090f for shadows and warm gold 0xc49963 for highlights with a subtle teal lift in the mid-shadows, cinematic dark grade in the style of Roger Deakins lighting Blade Runner 2049 and the interior cinematography of The Grand Budapest Hotel, calm contemplative monumental mood, 8 seconds long, designed to loop seamlessly with matching luminance and camera vector between first and last frame, no audio, no text, no people, no logos.
```

**What this gives you:** an architecturally elegant, brand-aligned hero plate with motion in the dust and light only — perfect for headline text to sit on top of without competition.

---

## Prompt 2 — "Abstract gold motion" (mandala-adjacent, easiest to loop)

Paste this verbatim into Veo 3.1:

```
A macro-scale extreme close-up of liquid gold and dark amber ink slowly blooming and unfurling into deep black water, the gold tendrils opening into a soft eight-fold radial pattern reminiscent of a lotus mandala without ever resolving into a literal flower, captured at 240 frames per second and conformed to 24 fps for dreamlike slow motion, the camera locked off with no movement, only the ink moves, lit from a single warm key light above and behind for strong rim definition on the ink edges, color palette of pure black 0x000000 background and warm metallic gold 0xd4a574 to 0xc49963 for the ink with subtle bronze 0x8b6f3f in the deeper folds, cinematic dark grade with high contrast and rich saturation only on the gold, in the style of high-end perfume commercial cinematography and Apple product launch fluid motion, ethereal hypnotic luxurious mood, 8 seconds long, designed to loop seamlessly by playing forward then reversing or by starting and ending on near-black frames, no audio, no text, no people, no logos.
```

**What this gives you:** an abstract, brand-coded motion piece that *suggests* your mandala without copying it — perfect as the default Slide 1 because it loops cleanly and any headline reads against it.

---

## Prompt 3 — "Doha at the golden hour" (cityscape / scale)

Paste this verbatim into Veo 3.1:

```
A slow-motion wide cinematic aerial shot drifting laterally across the Doha skyline at dusk just after the call to maghrib, the silhouettes of the Aspire Tower, the curved towers of West Bay and the Museum of Islamic Art rendered as warm bronze cutouts against a deepening indigo sky, a single distant cargo aircraft tracing a slow arc on the horizon, the city lights just beginning to glow with warm amber pinpoints, captured on a Cineflex gyro-stabilised system with a long 85mm lens compressing the cityscape into layered planes, color palette dominated by deep navy 0x07090f for the sky transitioning to warm sodium amber 0xc49963 along the lower horizon line with the building silhouettes as pure black 0x000000, cinematic dark teal-and-orange grade in the style of Denis Villeneuve's establishing shots and the title sequences of HBO prestige drama, monumental serene long-term mood evoking a city built for the next century, 8 seconds long, the camera continuing its lateral drift through the entire clip so the loop matches by starting position equalling end position plus one full cycle, no audio, no text, no people, no logos.
```

**What this gives you:** a sense-of-place and sense-of-scale slide — appropriate as the second slide in a rotation if Slide 1 is abstract.

---

## Prompt 4 — "Retail interior, dawn light" (for the Retail sector slide)

```
A slow tracking shot moving silently down the central aisle of an empty high-end retail boutique just before opening hour, the polished floor reflecting warm pendant lights overhead, neatly arranged displays of luxury goods slightly out of focus on both sides, the front entrance glowing with cool blue-grey morning light at the far end of the aisle creating a strong contrast against the warm interior lighting, captured on an Arri Alexa with a 35mm lens at f/2.0, shallow depth of field, the camera moving forward at slow walking pace, no people visible anywhere in the frame, no merchandise text or logos legible, color palette of warm amber 0xc49963 for the interior lighting transitioning to cool morning blue 0x4a6b85 at the entrance, cinematic dark grade with deep blacks and protected gold highlights, in the style of luxury fashion brand films and the interior cinematography of In the Mood for Love, refined patient anticipatory mood, 8 seconds long, designed to loop seamlessly by having the camera approach but never reach the entrance, no audio, no text, no people, no logos.
```

---

## Prompt 5 — "Distribution and logistics scale" (B2B slide)

```
A slow rising crane shot over a vast modern distribution warehouse interior at the blue hour just before dawn, neat rows of palletised goods stretching toward a vanishing point under a high ceiling lit by cool overhead industrial LEDs, a single automated forklift moving silently along an aisle far in the background as the only motion, dust suspended in the air catching the cool light, captured on a RED Komodo with a 24mm lens at f/4, deep focus throughout, the camera rising and slowly pulling back, color palette of cool steel grey 0x8b9aa8 and deep industrial navy 0x1a2638 for the architecture with single accents of warm safety amber 0xc49963 from the forklift's hazard lights, cinematic dark grade with desaturated cool tones and one warm accent, in the style of Christopher Nolan's industrial scale shots and the cinematography of Tenet, monumental quiet competent mood evoking a backbone you don't usually see, 8 seconds long, designed to loop seamlessly with the camera's continuous rise hidden by a subtle crossfade in post, no audio, no text, no people, no logos.
```

---

## Negative prompt (use Veo's "what to avoid" field where available)

Paste this in the negative-prompt slot for any of the above:

```
people, faces, hands, text overlays, captions, logos, brand marks, watermarks, lens flares, chromatic aberration, film grain, vintage filter, sepia tone, cartoon style, illustration style, anime, 3D render look, video game look, low resolution, motion blur from fast camera moves, handheld shake, drone propeller noise, voice-over, music, dialogue, on-screen typography, saturated reds, neon colors, lightning, fire, water splashes, fast cuts, jump cuts, montage editing, slow zoom-out into a different scene
```

---

## Post-generation steps

### Make it loop seamlessly

Veo 3.1 generates discrete 8-second clips that almost never loop perfectly on their own. After download:

1. Open in DaVinci Resolve (free) or Adobe Premiere
2. Duplicate the clip on a track above the original, offset by ~0.5 second
3. Crossfade the boundary between end and start (24-frame dissolve)
4. Export as a 7.5-second loop — the dissolve hides the seam

Or use a simpler trick: **ping-pong** the clip (play forward then reverse) — gives you 16 seconds of guaranteed seamless motion. Works well for Prompt 2 (ink) and Prompt 5 (warehouse rise).

### Compress for web

Veo outputs are ~30–80 MB per 8 seconds at 1080p. The hero budget is **≤ 4 MB**. Use `ffmpeg`:

```bash
ffmpeg -i veo_output.mp4 \
  -vcodec libx264 -crf 28 -preset slow -profile:v main \
  -vf "scale=1280:720" -an -movflags +faststart \
  hero_slide_1.mp4
```

For the WebM fallback:

```bash
ffmpeg -i veo_output.mp4 \
  -c:v libvpx-vp9 -crf 34 -b:v 0 \
  -vf "scale=1280:720" -an \
  hero_slide_1.webm
```

### Extract the poster frame

```bash
ffmpeg -i veo_output.mp4 -ss 00:00:00.5 -vframes 1 -q:v 2 hero_slide_1_poster.jpg
```

Then re-encode at 70 % quality to ~120 KB using any image tool.

---

## Where the files go

Drop the processed files into your existing public-folder convention:

```
frontend/public/video/home/hero/
  pug_heritage_corridor.mp4
  pug_heritage_corridor.webm

frontend/public/images/home/hero/posters/
  pug_heritage_corridor.jpg
```

Then in the admin CMS create a Hero Slide with:

- `media_type` = `video`
- `video_url` = `/video/home/hero/pug_heritage_corridor.mp4`
- `video_webm_url` = `/video/home/hero/pug_heritage_corridor.webm`
- `poster_url` = `/images/home/hero/posters/pug_heritage_corridor.jpg`
- `video_credit` = `Generated with Google Veo 3.1`
- `duration_ms` = `7500`
- `overlay_opacity` = `60`

---

## Iteration tips

- Run each prompt **3–4 times** before judging it. Veo varies per generation — the third take often beats the first
- If a take is 80 % right, **edit only one phrase** at a time and regenerate with the same seed. Don't rewrite the whole prompt
- Lighting and color phrases have the strongest effect. Camera-movement phrases are second. Style-reference phrases (Roger Deakins, Villeneuve, Wong Kar-wai) are surprisingly powerful — use sparingly
- If Veo inserts people despite the negative prompt, add to the positive prompt: *"the space is empty of any human presence, no figures, no silhouettes"*
- If Veo over-saturates, add to the positive prompt: *"desaturated cinematic grade, muted palette, gold tones the only colour permitted to fully saturate"*

---

## Veo 3.1 access (current as of brief writing)

- **Google Vids** (workspace.google.com) — integrated Veo, easiest UI
- **Gemini Advanced** (gemini.google.com) — direct video generation with Veo
- **Vertex AI Studio** (cloud.google.com) — API access, suitable for batch generation
- **Whisk** (labs.google) — experimental, sometimes carries newest Veo features first

Generation cost varies by tier; budget ~$1–3 per 8-second clip on consumer tiers, less via Vertex API at volume.

---

*Generated as a planning document for the Paris United Group hero rebuild. No source code in the project was modified.*
