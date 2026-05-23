# Local Setup Guide

This guide walks through running the Paris United Group Holding stack
on a local development machine after a fresh clone.

## Prerequisites

| Tool          | Version    | Notes                                    |
| ------------- | ---------- | ---------------------------------------- |
| Python        | 3.11+      | Backend (FastAPI + SQLAlchemy)           |
| Node.js       | 18.18+     | Frontend (Next.js 14, App Router)        |
| npm           | 9+         | Or pnpm/yarn if you prefer               |
| PostgreSQL    | 14+        | Database for both website and HR ATS     |
| Git           | any recent |                                          |

> Phase 1 does not yet seed any data; you only need an empty database
> with credentials matching `backend/.env`.

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

# Apply migrations (Phase 1 ships none yet, command is still safe to run).
alembic upgrade head

# Run the API
python run.py
```

The API serves at <http://localhost:8000>:

- Swagger: <http://localhost:8000/docs>
- Health:  <http://localhost:8000/api/v1/health>
- Live:    <http://localhost:8000/api/v1/health/live>

## 4. Frontend

In a separate terminal:

```bash
cd frontend
npm install
cp .env.example .env.local
# Adjust NEXT_PUBLIC_API_BASE_URL if your backend isn't on :8000.
npm run dev
```

Browse to <http://localhost:3000>. The landing splash automatically
calls `/api/v1/health` on the backend and reports the result.

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

| Symptom                                      | Likely cause / fix                                                |
| -------------------------------------------- | ----------------------------------------------------------------- |
| `psycopg2` install fails                     | Install PostgreSQL dev headers (`libpq-dev`).                     |
| Health card shows "disconnected"             | Backend is reachable but cannot talk to PostgreSQL – check `.env`.|
| Health card shows "Request to ... failed"    | Backend is not running, or CORS origin is wrong.                  |
| `ModuleNotFoundError: app`                   | Activate the venv inside `backend/`.                              |
| Next.js build fails on first install         | Delete `frontend/node_modules` and `package-lock.json`, reinstall.|
