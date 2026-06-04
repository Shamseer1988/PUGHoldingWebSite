# PUG Holding Website

Monorepo for the Paris United Group corporate website + HR ATS portal.

* `frontend/` — Next.js 14 (App Router), TypeScript, Tailwind, Framer Motion / GSAP
* `backend/` — FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, structlog, Sentry
* `deploy/` — Nginx, systemd, logrotate configs for the production server
* `docs/` — architecture + operational notes

See [`CLAUDE.md`](./CLAUDE.md) for the project conventions Claude Code reads at the start of every session.

The site runs **natively — no Docker**: in development as local processes, in production inside a Proxmox **LXC container** supervised by `systemd`. (The repo still carries `docker-compose*.yml` / `Dockerfile`s from an earlier containerised experiment; they are no longer the supported path.)

---

## Running locally (no Docker)

You need four things on your machine (or a dev VM): **Python 3.11**, **Node 20**, a **PostgreSQL** server, and **Redis**. On Debian/Ubuntu: `sudo apt install postgresql redis-server`.

Create the database once:

```sh
sudo -u postgres psql -c "CREATE USER pug_user WITH PASSWORD 'pug_password';"
sudo -u postgres psql -c "CREATE DATABASE pug_holding OWNER pug_user;"
```

### Backend (FastAPI)

```sh
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env                       # edit: DB creds, Redis URL, AI keys, secrets

.venv/bin/alembic upgrade head             # apply migrations
.venv/bin/python -m app.scripts.seed_hr    # Super Admin + permission catalogue + HR roles
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The HR seed prints a one-time random password for `admin@parisunited.example` on the last line of stdout — log in with it at `/admin/login`. The backend config defaults to `localhost` for Postgres and Redis, so the values above work with no extra wiring.

### Frontend (Next.js)

```sh
cd frontend
npm install
cp .env.example .env.local                 # set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
npm run dev
```

| Service | URL |
|---|---|
| Frontend | <http://localhost:3000> |
| Backend | <http://localhost:8000> |
| OpenAPI docs | <http://localhost:8000/docs> (when `APP_ENV=development`) |
| Health | <http://localhost:8000/api/v1/health> |

---

## Testing

```sh
# Backend — from backend/ with the venv
.venv/bin/pytest -x -q

# Frontend — from frontend/
npm run type-check     # tsc --noEmit
npm run lint           # next lint
npm test               # vitest run
```

Run `npm run type-check` + `npm run lint` (frontend) and `pytest` (backend) before declaring work done — see `CLAUDE.md`.

---

## Production deployment — Proxmox LXC (no Docker)

The corporate site is **CT 112 (`pugweb`)** in the Proxmox cluster: Next.js, FastAPI, PostgreSQL 17 and Redis all run as **native processes under `systemd`** inside one unprivileged LXC. TLS terminates on a separate **edge-nginx LXC (CT 111)**, which is reached through a **Cloudflare Tunnel** — so no router ports are forwarded anywhere. (The full multi-container build — the Cloudflare Tunnel CT, the edge nginx, and the sibling Housing / Finance apps — is covered by the Proxmox deployment guide; the corporate-site essentials are below.)

| | CT 112 |
|---|---|
| Hostname | `pugweb` |
| Resources | 4 vCPU · 4 GB RAM · 40 GB disk |
| Internal IP | `192.168.100.51` |
| Listens on | `:3000` (Next.js) · `:8000` (FastAPI) |
| App root | `/opt/pugweb` (owned by the `pugweb` system user) |
| Database | PostgreSQL 17 — `pug_holding` / `pug_user`, on `localhost` |
| Cache | Redis, on `localhost` |

### Provision once

Inside the container (as `root`), the one-time setup is: install Python 3.11 / Node 20 / PostgreSQL 17 / Redis → create the `pug_holding` DB and `pugweb` app user → `git clone` into `/opt/pugweb` → backend venv + `.env` + `alembic upgrade head` → frontend `.env.production` (with the public `NEXT_PUBLIC_API_BASE_URL`) + `npm ci && npm run build` → install the two `systemd` units. The step-by-step commands live in the Proxmox deployment guide.

### Services

Two `systemd` units run the app; both bind `0.0.0.0` because the edge nginx is a *separate* container:

* **`pugweb-backend`** — `gunicorn app.main:app` with `uvicorn` workers on `:8000`
* **`pugweb-frontend`** — `npm run start` (`next start`) on `:3000`
* *(optional)* a background-jobs worker via `.venv/bin/python worker_runner.py`, if you enable ARQ

```sh
systemctl status pugweb-backend pugweb-frontend
journalctl -u pugweb-backend -f          # live backend log
```

The reference unit files, the nginx server block, and the logrotate config live in [`deploy/`](./deploy).

### Redeploy after a git push

Pull, install, migrate, rebuild, restart — app-level commands as the `pugweb` user, `systemctl` with `sudo`:

```sh
sudo -u pugweb bash -lc 'cd /opt/pugweb && git pull \
  && cd backend   && .venv/bin/pip install -r requirements.txt && .venv/bin/alembic upgrade head \
  && cd ../frontend && npm ci && npm run build'

sudo systemctl restart pugweb-backend pugweb-frontend
```

`alembic upgrade head` is idempotent and safe on every deploy. Migrations are additive (never destructive) per `CLAUDE.md`, so a rollback is `git checkout <prev-sha>` → `.venv/bin/alembic downgrade -1` → rebuild. Snapshot the CT first for an instant rollback: `pct snapshot 112 pre-update` on the Proxmox host.

> **WebSocket note:** the HR consoles hold a live WebSocket at `/api/v1/ws/hr` for realtime multi-operator sync. The edge-nginx `location /api/v1/` must forward the `Upgrade` / `Connection "upgrade"` headers (a dedicated `location /api/v1/ws/` block is cleanest) or realtime updates won't connect.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pugweb-backend` won't start — `connection refused` to Postgres | Postgres/Redis not up yet | `systemctl status postgresql redis-server`; the unit's `After=`/`Wants=` ordering self-corrects on boot |
| Frontend loads but API calls fail (404 / CORS) | `NEXT_PUBLIC_API_BASE_URL` baked wrong at build time | set it in `frontend/.env.production` **before** `npm run build`, then rebuild |
| `next build` gets killed (OOM) | 4 GB CT is tight for a large build | raise CT RAM temporarily, or `NODE_OPTIONS=--max-old-space-size=3072 npm run build` |
| HR consoles don't live-update across operators | edge nginx isn't upgrading the `/api/v1/ws/hr` WebSocket | add the `Upgrade`/`Connection` headers on the edge nginx (see note above) |
| `alembic upgrade head` fails on a CHECK constraint | existing rows violate a newly-added constraint | the migration rolls back cleanly — fix the offending rows, then re-run |
