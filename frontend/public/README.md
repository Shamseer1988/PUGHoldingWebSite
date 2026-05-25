# Public assets

This directory is served as-is at the site root.

## Logo files (required)

Save the official Paris United Group Holding logo files here:

| File                   | Purpose                                                  |
| ---------------------- | -------------------------------------------------------- |
| `logo.png`             | Full logo for **light** surfaces (green wordmark + gold mandala). |
| `logo-light.png`       | Full logo for **dark** surfaces (light/cream wordmark + gold mandala). |
| `logo-mark.png`        | Mandala only (square crop) — used in tight spaces and as an Open Graph fallback. |

Recommended dimensions:

- `logo.png` / `logo-light.png`: about **600 × 250 px** (transparent PNG).
- `logo-mark.png`: square **256 × 256 px** (transparent PNG).

Once the files are present here, the navbar, footer, admin sidebar,
login pages, and Open Graph cards all pick them up automatically.

## Favicon

The favicon is wired through the Next.js **App Router icon convention**
in [`/app/icon.png`](../app/icon.png) — drop a square 512 × 512 PNG of
the mandala there and Next.js generates every favicon size for you. An
optional [`/app/apple-icon.png`](../app/apple-icon.png) can be added for
iOS.
