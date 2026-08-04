# PUG Holding Website — Project Context for Claude Code

## Git Workflow (repo owner's standing instruction)
- **Default working branch is `claude/offer-letter-templates`.** Do all work on this branch — do **not** create new branches.
- Commit each completed task to `claude/offer-letter-templates` and keep using that same branch for subsequent work.
- **Only open a pull request when the repo owner explicitly asks.** Never open a PR proactively.

## Stack
- Frontend: Next.js 14 (App Router), TypeScript, Tailwind CSS, Framer Motion, GSAP
- Backend: FastAPI, SQLAlchemy 2.x (sync), PostgreSQL, Alembic, python-jose JWT, bcrypt
- AI: Azure OpenAI via `openai` SDK
- Testing: Vitest (frontend), pytest + pytest-asyncio (backend)
- Deploy: Nginx + Gunicorn + systemd (see /deploy/)

## Directory Layout
- /frontend      Next.js application
- /backend       FastAPI application
- /deploy        Nginx, systemd, logrotate configs
- /docs          Architecture and operational guides

## Coding Standards
- TypeScript strict mode; no `any` unless explicitly justified with a comment
- Python: type hints on all public functions; `from __future__ import annotations`
- All new backend routes must have at least one pytest test
- All new frontend hooks/utilities must have at least one Vitest test
- Run `npm run type-check` and `npm run lint` before declaring frontend work done
- Run `pytest` before declaring backend work done

## Important Constraints
- Never commit secrets or API keys
- Never set `force-dynamic` at the layout level — use per-route ISR instead
- Do not add new dependencies without explaining why an existing package cannot serve the purpose
- Keep migrations additive; never drop columns — use nullable + backfill pattern
- **Branch QR codes**: `marketing_qr_codes.slug` is immutable. The slug is encoded into QR artwork printed on in-store signage and flyers, which cannot be recalled — changing one silently breaks physical assets. `QrCodeUpdate` deliberately has no `slug` field and uses `extra="forbid"`, so an attempt is a 422 rather than a silent no-op; don't add one. Re-point a code via `target_url`; retire one via `is_active = false`, which routes scans down the fallback chain (`qr.fallback_url` → `division.fallback_url` → 404) instead of dead-ending. The `/q/{slug}` rewrite in `next.config.mjs` and `SHORT_URL_BASE` (backend) / `NEXT_PUBLIC_SHORT_URL_BASE` (frontend) must stay in step, or rendered artwork won't match the URL the admin UI displays.
- **Frontend motion**: prefer `framer-motion` (variants + `whileInView`) for everything new. GSAP is kept only for `hero-slider.tsx` and `featured-companies-showcase.tsx` because they rely on `ScrollTrigger.scrub` (live scroll-linked parallax / active-state) which framer-motion can replicate only with significant extra machinery. Don't reach for GSAP for new work without an equivalent justification.
- **Frontend i18n (Phase C-1)**: bilingual EN/AR on the public site. Translations live in `frontend/lib/i18n/messages/{en,ar}.json` (flat JSON, dotted keys). Read strings via `useT()` from `@/lib/i18n/locale-provider` in client components, or `getMessages(getLocale())` in server components. New keys must be added to both dictionaries — the test in `lib/i18n/__tests__/i18n.test.tsx` enforces parity. Direction is set on `<html>` by `app/layout.tsx`; use Tailwind's `rtl:` / `ltr:` variants for direction-sensitive layout. Admin + HR consoles are intentionally English-only (the middleware matcher excludes them). CMS content (companies, news, settings) is single-language until the backend grows a `locale` column.

## External Services
- Storage: Cloudflare R2 (S3-compatible, endpoint in .env as R2_ENDPOINT_URL)
- AI: Azure OpenAI (credentials in .env as AZURE_OPENAI_*)
- Error tracking: Sentry (DSN in .env as SENTRY_DSN_BACKEND / SENTRY_DSN_FRONTEND)
- Cache / Queue: Redis (in .env as REDIS_URL)
