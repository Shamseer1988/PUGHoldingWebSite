# Local Setup Guide

This guide walks through running the Paris United Group Holding stack
on a local development machine after a fresh clone.

## Prerequisites

| Tool          | Version    | Notes                                    |
| ------------- | ---------- | ---------------------------------------- |
| Python        | 3.11–3.12  | Backend (FastAPI + SQLAlchemy)           |
| Node.js       | 18.18+     | Frontend (Next.js 14, App Router)        |
| npm           | 9+         | Or pnpm/yarn if you prefer               |
| PostgreSQL    | 14+        | Database for both website and HR ATS     |
| Git           | any recent |                                          |

> Python 3.13/3.14 are not yet supported because some pinned wheels
> (e.g. `psycopg2-binary`) don't ship binary wheels for them on Windows.
> Use the official Python 3.11.x or 3.12.x installer from python.org and
> tick **Add Python to PATH** during install.

## 1. Clone the repository

```bash
git clone <repo-url>
cd PUGHoldingWebSite
```

## 2. PostgreSQL setup

Create a database and user. Defaults match the values in
`backend/.env.example`:

```sql
CREATE USER pug_user WITH PASSWORD 'pug_password';
CREATE DATABASE pug_holding OWNER pug_user;
GRANT ALL PRIVILEGES ON DATABASE pug_holding TO pug_user;
```

## 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env if your PostgreSQL credentials differ.

# Apply migrations (Phase 2 creates the auth tables).
alembic upgrade head

# Seed baseline roles, permissions, and users (idempotent).
python -m app.scripts.seed_users

# Run the API
python run.py
```

The API serves at <http://localhost:8000>:

- Swagger: <http://localhost:8000/docs>
- Health:  <http://localhost:8000/api/v1/health>
- Live:    <http://localhost:8000/api/v1/health/live>
- Admin login API:  `POST /api/v1/admin/auth/login`
- HR login API:     `POST /api/v1/hr/auth/login`

### Seed accounts

All seed users share the password **`ChangeMe!123`** (change immediately
outside development):

| Email                              | Role          | Scope        |
| ---------------------------------- | ------------- | ------------ |
| superadmin@pug.example.com         | Super Admin   | system (all) |
| websiteadmin@pug.example.com       | Website Admin | website      |
| hrmanager@pug.example.com          | HR Manager    | hr           |
| hrexecutive@pug.example.com        | HR Executive  | hr           |
| interviewer@pug.example.com        | Interviewer   | hr           |

Re-running `python -m app.scripts.seed_users` updates roles/permissions
but never overwrites a user's password.

## 4. Frontend

In a separate terminal:

```bash
cd frontend
npm install
cp .env.example .env.local
# Adjust NEXT_PUBLIC_API_BASE_URL if your backend isn't on :8000.
npm run dev
```

Browse to:

- <http://localhost:3000> — Phase 2 landing splash with backend health
  card and CTAs into both portals.
- <http://localhost:3000/admin/login> — Website Admin login.
- <http://localhost:3000/hr/login> — HR ATS login.

## 5. Verification commands

```bash
# Backend tests
cd backend && pytest -q

# Frontend type-check + build
cd frontend
npm run type-check
npm run build
```

## 6. Common issues

| Symptom                                      | Likely cause / fix                                                       |
| -------------------------------------------- | ------------------------------------------------------------------------ |
| `psycopg2` wheel build fails on Windows      | Using Python 3.13/3.14 — install Python 3.11 and recreate the venv.      |
| Health card shows "disconnected"             | Backend is reachable but cannot talk to PostgreSQL – check `.env`.       |
| Health card shows "Request to ... failed"    | Backend is not running, or CORS origin is wrong.                         |
| Login returns 422 "valid email address"      | Email-validator rejects reserved TLDs (`.local`, `.test`) — use `.com`.  |
| Login returns 403                            | Account exists but lacks the role scope for that portal.                 |
| `ModuleNotFoundError: app`                   | Activate the venv inside `backend/`.                                     |
| Next.js install fails after `audit fix`      | Don't use `npm audit fix --force`. Restore `package.json` from git.      |
