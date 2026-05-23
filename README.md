# Paris United Group Holding

Monorepo for the Paris United Group Holding corporate website and the
separate HR Admin / ATS portal.

## Status

**Phase 1 — Project foundation: complete.**

Phase 1 delivers the project skeleton, dev tooling, configuration, and
the health-check API. Subsequent phases (auth, public website, CMS, HR
ATS, AI assistant, production deployment) are tracked in
[`docs/phase-implementation-guide.md`](docs/phase-implementation-guide.md).

## Repository layout

```
PUGHoldingWebSite/
├── backend/        FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL
├── frontend/       Next.js 14 App Router + Tailwind + shadcn/ui + Framer Motion
├── docs/           Setup, deployment, admin/HR guides, API reference
└── PUG_Dynamic_Website_HR_ATS_Phase_Prompt.txt   Project master prompt
```

Each app has its own README:

- [`backend/README.md`](backend/README.md)
- [`frontend/README.md`](frontend/README.md)

## Quick start

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py            # http://localhost:8000

# Frontend (separate terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev              # http://localhost:3000
```

See [`docs/setup-guide.md`](docs/setup-guide.md) for the full guide
including PostgreSQL setup and verification commands.

## Tech stack

- **Frontend:** Next.js 14, TypeScript, Tailwind CSS, shadcn/ui,
  Framer Motion, Lucide React, Recharts, next-themes.
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2,
  PostgreSQL.
- **AI (later phases):** Azure OpenAI for the public assistant and HR
  candidate review.
- **Deployment (later phases):** AWS Ubuntu, Nginx, Gunicorn/Uvicorn,
  PM2 or systemd, Cloudflare SSL.
