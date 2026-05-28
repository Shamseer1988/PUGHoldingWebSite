# PUG Holding Website

Monorepo for the Paris United Group corporate website + HR ATS portal.

* `frontend/` — Next.js 14 (App Router), TypeScript, Tailwind, Framer Motion / GSAP
* `backend/` — FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, structlog, Sentry
* `deploy/` — Nginx, systemd, logrotate configs for the production server
* `docs/` — architecture + operational notes

See [`CLAUDE.md`](./CLAUDE.md) for the project conventions Claude Code reads at the start of every session.

---

## Running Locally with Docker

A single `docker compose up -d` boots the full stack — Postgres 16, Redis 7, the FastAPI backend, and the Next.js frontend — with hot-reload on both apps. The compose file lives at the repo root; the per-service Dockerfiles under `backend/` and `frontend/`.

### One-time setup

```sh
# 1. Copy the env templates. Edit the resulting files in your editor
#    of choice — secrets, SMTP creds, AI keys etc. Everything left
#    blank uses sensible defaults baked into the compose file.
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# 2. Build the images. First build takes a few minutes; subsequent
#    builds reuse the npm + pip cache layers.
docker compose build
```

### Bring up

```sh
docker compose up -d              # all four services in the background
docker compose ps                 # confirm everything's healthy
docker compose logs -f backend    # tail backend log in JSON / dev format
```

When the stack is healthy:

* Frontend: <http://localhost:3000>
* Backend:  <http://localhost:8000>
* OpenAPI docs: <http://localhost:8000/docs> (dev only — `APP_ENV=development` is set by compose)
* Postgres: `localhost:5432` (user `pug_user`, pw `pug_password`, db `pug_holding`)
* Redis:    `localhost:6379`

### Migrations

The backend service runs `alembic upgrade head` on every container start, so pulling a branch with new migrations and re-running `docker compose up -d` is enough.

Run migrations manually:

```sh
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "describe it"
```

### Seed the initial admin user

The HR seed script creates a Super Admin account, the default permission catalogue, and the seven HR roles:

```sh
docker compose exec backend python -m app.scripts.seed_hr
```

Login at <http://localhost:3000/admin/login> with the credentials printed by the script (the default is `admin@parisunited.example` / a per‑install random password; the script logs it once at the end of stdout).

### Common operations

```sh
# Drop into a backend shell
docker compose exec backend bash

# Drop into a psql session
docker compose exec postgres psql -U pug_user -d pug_holding

# Run the test suite inside the container
docker compose exec backend pytest -x -q

# Frontend type-check + lint
docker compose exec frontend npm run type-check
docker compose exec frontend npm run lint

# Stop everything but keep data
docker compose down

# Nuke postgres + redis volumes too (fresh DB next boot)
docker compose down -v
```

### Hot reload

The compose file bind-mounts `./backend` → `/app` and `./frontend` → `/app` so saves on the host trigger reloads in the containers:

* **Backend**: `uvicorn --reload --reload-dir /app/app`
* **Frontend**: `next dev` (Webpack watcher)

Frontend `node_modules` and `.next` are kept in anonymous volumes — the container builds them once at first start, and the host's bind-mount can't overwrite them. This matters when the host is macOS / arm64 and the container is linux/amd64.

### Production builds

The Dockerfiles' `runner` stages are production-shaped (Alembic + uvicorn for the backend, `next start` for the frontend). Build either explicitly:

```sh
docker build --target runner -t pug-backend:prod -f backend/Dockerfile .
docker build --target runner -t pug-frontend:prod -f frontend/Dockerfile .
```

CI / production deployment lives outside this file — see `deploy/` for the Nginx + systemd configs the production server uses today, and `.github/workflows/` (added in Phase B-6) for the pipeline.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `backend` keeps restarting with `connection refused` | postgres is still warming up | wait — `depends_on: condition: service_healthy` makes this self-correct in ~5–10 s |
| `frontend` runs but pages can't reach the API | host's `.env.local` overrides the compose `environment:` block with a host-machine URL | unset `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` or set it to `http://localhost:8000/api/v1` |
| `alembic` fails on first boot with "relation already exists" | a previous `docker compose down` left postgres data behind | `docker compose down -v` then `up -d` |
| Permission errors on bind-mounted files | UID mismatch between host + container | rebuild with `--build-arg HOST_UID=$(id -u)` (not yet implemented) or `chmod -R 777 backend/app/uploads` |
