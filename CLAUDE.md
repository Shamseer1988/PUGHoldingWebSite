# PUG Holding Website — Project Context for Claude Code

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
- **Frontend motion**: prefer `framer-motion` (variants + `whileInView`) for everything new. GSAP is kept only for `hero-slider.tsx` and `featured-companies-showcase.tsx` because they rely on `ScrollTrigger.scrub` (live scroll-linked parallax / active-state) which framer-motion can replicate only with significant extra machinery. Don't reach for GSAP for new work without an equivalent justification.

## External Services
- Storage: Cloudflare R2 (S3-compatible, endpoint in .env as R2_ENDPOINT_URL)
- AI: Azure OpenAI (credentials in .env as AZURE_OPENAI_*)
- Error tracking: Sentry (DSN in .env as SENTRY_DSN_BACKEND / SENTRY_DSN_FRONTEND)
- Cache / Queue: Redis (in .env as REDIS_URL)
