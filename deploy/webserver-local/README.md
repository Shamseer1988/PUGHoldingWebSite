# Deploy PUG corporate website on the shared "Local Webserver"

Host the PUG Holding website (FastAPI + Next.js) on the **same Windows box**
that already runs the **Employee Housing Control Portal**, behind that
project's nginx (Cloudflare **Full (Strict)** + **Cloudflare Tunnel**).

This folder contains everything specific to that topology:

| File | Purpose |
|------|---------|
| [`../../docker-compose.webserver-local.yml`](../../docker-compose.webserver-local.yml) | The PUG web stack **without its own nginx**, joined to a shared docker network as `pugweb-api` / `pugweb-frontend`. |
| [`nginx-pugweb.conf`](nginx-pugweb.conf) | Drop-in **Host #3** vhost (+ upstreams) for the housing portal's `nginx.conf`. |
| [`../../backend/.env.webserver-local.example`](../../backend/.env.webserver-local.example) | Minimal required backend env for a clean production boot. |

```
Internet ─► Cloudflare (Full Strict) ─► cloudflared tunnel ─► nginx (housing portal)
                                                                 │  (TLS terminates here)
                          ┌──────────────────────────────────────┼─────────────────────────┐
                          │ accommodation.parisunitedgroup.com     │ parisunitedgroup.com      │
                          ▼ (Host #1, existing)                    ▼ (Host #3, NEW)            │
                  backend:5000 / frontend:3000          pugweb-api:8000 / pugweb-frontend:3000 │
                                                          (this repo, on the pug_edge network) │
                                                                                               │
   pug_edge  ── shared docker network: nginx ⇄ pugweb-api ⇄ pugweb-frontend ────────────────────┘
   internal  ── private: postgres + redis + backend + frontend + worker (not on pug_edge)
```

> **Why no second nginx / no TLS files here?** The housing portal's nginx is
> the single entry point for the box (it owns ports 80/443 and terminates the
> Cloudflare Origin Certificate). This stack only needs to expose its two app
> containers on a network nginx can reach. That's the whole integration.

---

## Prerequisites

- The Employee Housing portal is already deployed and serving traffic
  (so Docker Desktop, the tunnel, and the Origin cert are all working).
- The Cloudflare **Origin Certificate** in use covers **both**
  `*.parisunitedgroup.com` **and the apex** `parisunitedgroup.com`
  (apex is NOT covered by the wildcard alone). Check in the Cloudflare
  dashboard → SSL/TLS → Origin Server; reissue to include the apex if needed.
- DNS `parisunitedgroup.com` and `www` will be routed through the same
  Cloudflare Tunnel (Step 7).

All commands below are **PowerShell** on the host.

---

## Step 1 — Clone into `C:\Apps\PUGWebSite`

```powershell
cd C:\Apps
git clone https://github.com/Shamseer1988/PUGHoldingWebSite.git PUGWebSite
cd C:\Apps\PUGWebSite
git checkout WebserverLocal
```

## Step 2 — Create `backend\.env`

```powershell
copy backend\.env.webserver-local.example backend\.env
notepad backend\.env
```

Set at minimum (the API refuses to start in production otherwise):

- `SECRET_KEY` — generate a unique one:
  ```powershell
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
- `POSTGRES_PASSWORD` — a strong password.
- `CORS_ORIGINS=https://parisunitedgroup.com,https://www.parisunitedgroup.com`
- `PUBLIC_SITE_URL=https://parisunitedgroup.com`
- Optional but recommended for media: the `R2_*` block. Optional: `AI_*`,
  `SMTP_*`, `SENTRY_DSN`.

> Do **not** set `POSTGRES_HOST`, `REDIS_URL`, `APP_ENV`, or `UPLOAD_DIR` —
> the compose file injects the correct values for this topology.

The browser-facing URL (`NEXT_PUBLIC_API_BASE_URL`) is **baked at build time**
and already defaults to `https://parisunitedgroup.com/api/v1` in the compose
file — no `frontend\.env.local` needed. (Override only for a different domain:
`$env:NEXT_PUBLIC_API_BASE_URL="https://other.example/api/v1"` before build.)

## Step 3 — Create the shared edge network (once)

```powershell
docker network create pug_edge
```

## Step 4 — Attach the housing portal's nginx to `pug_edge`

Edit the **housing portal's** compose file
(`C:\Apps\Employee-Housing-Control-Portal\docker-compose.prod.yml`). Add
`pug_edge` to the **nginx** service and declare it external:

```yaml
services:
  nginx:
    # … existing config …
    networks:
      - default        # keep whatever network it already uses
      - pug_edge       # NEW — lets nginx reach pugweb-api / pugweb-frontend

networks:
  pug_edge:
    external: true
```

Recreate just the nginx container so it picks up the new network:

```powershell
cd C:\Apps\Employee-Housing-Control-Portal
docker compose -f docker-compose.prod.yml up -d nginx
```

> This is the only change on the housing-portal side. It does not touch
> Host #1 routing.

## Step 5 — Bring up the PUG web stack

```powershell
cd C:\Apps\PUGWebSite
docker compose -f docker-compose.webserver-local.yml up -d --build
docker compose -f docker-compose.webserver-local.yml ps
docker compose -f docker-compose.webserver-local.yml logs -f backend   # watch migrations + gunicorn boot
```

The backend runs `alembic upgrade head` automatically before gunicorn starts.

> **Don't let the build disrupt the live housing portal.** The image build
> (especially the frontend `next build`) is RAM/CPU-heavy and, on a small
> Docker Desktop VM, can starve the *running* accommodation containers until
> the build finishes. The two stacks don't conflict (separate project, no
> shared host ports, separate volumes) — it's pure resource contention during
> **build only**; runtime (`up -d`) is light. To build gently:
>
> 1. Give Docker Desktop **6–8 GB** RAM (Settings → Resources).
> 2. Build the two images **one at a time** so the heavy steps don't overlap,
>    with an auto-retry loop for flaky networks (PowerShell):
>    ```powershell
>    do { docker compose -f docker-compose.webserver-local.yml build backend }  until ($LASTEXITCODE -eq 0)
>    do { docker compose -f docker-compose.webserver-local.yml build frontend } until ($LASTEXITCODE -eq 0)
>    docker compose -f docker-compose.webserver-local.yml up -d
>    ```
>    The pip/npm cache mounts mean each retry resumes instead of re-downloading.
> 3. Or build during off-peak hours, or build on another machine and copy the
>    images over with `docker save` / `docker load` so the server never runs a
>    heavy build next to the live app.

## Step 6 — Seed baseline data (first deploy only)

```powershell
docker compose -f docker-compose.webserver-local.yml exec backend python -m app.scripts.seed_users
docker compose -f docker-compose.webserver-local.yml exec backend python -m app.scripts.seed_cms
docker compose -f docker-compose.webserver-local.yml exec backend python -m app.scripts.seed_hr
```

Seeders are idempotent. **Change the seeded admin password immediately.**

## Step 7 — Add the Host #3 vhost to nginx

Open `C:\Apps\Employee-Housing-Control-Portal\deploy\nginx.conf` and make the
three edits described at the top of [`nginx-pugweb.conf`](nginx-pugweb.conf):

1. Paste the two `upstream pugweb_*` blocks into the upstreams section.
2. Add `parisunitedgroup.com www.parisunitedgroup.com` to the `server_name`
   of the `listen 80` redirect block.
3. Paste the Host #3 `server { … }` block after Host #1.

Validate and reload (inside the nginx container — find its name with
`docker ps`):

```powershell
docker exec <housing-nginx> nginx -t
docker exec <housing-nginx> nginx -s reload
```

## Step 8 — Route the hostnames through Cloudflare Tunnel

Add the two public hostnames to the **same tunnel** that already serves
`accommodation.parisunitedgroup.com`, pointing at the **nginx** service
(same origin service you already use for Host #1). Either:

- **Dashboard** (Zero Trust → Networks → Tunnels → your tunnel → Public
  Hostname → Add): `parisunitedgroup.com` and `www.parisunitedgroup.com` →
  service **HTTPS → nginx** (e.g. `https://nginx:443`), matching Host #1's
  config. Set "Origin Server Name" / no-TLS-verify the same way Host #1 does.
- **or `config.yml`** ingress: add two `hostname:` entries above the
  `service: http_status:404` catch-all, mirroring the accommodation entry.

Cloudflare DNS: ensure `parisunitedgroup.com` (apex) and `www` are **proxied
(orange-cloud) CNAMEs to the tunnel** — the dashboard adds these for you when
you create the public hostnames.

## Step 9 — Smoke test

```powershell
# From the host, straight at nginx via the edge network (bypasses Cloudflare):
docker exec <housing-nginx> wget -qO- --no-check-certificate https://parisunitedgroup.com/api/v1/health
#   (or curl from inside the pugweb-api container)
docker compose -f docker-compose.webserver-local.yml exec backend wget -qO- http://localhost:8000/api/v1/health

# End-to-end through Cloudflare (from anywhere):
#   https://parisunitedgroup.com/                      -> marketing site
#   https://parisunitedgroup.com/admin/login           -> Website Admin
#   https://parisunitedgroup.com/hr/login              -> HR ATS
#   https://www.parisunitedgroup.com/                  -> 301 to apex
```

You should get `{"status":"ok",...}` from the health endpoint and a working
login. HR realtime notifications connect over `wss://parisunitedgroup.com/api/v1/ws/`.

---

## Day-2 operations

> All commands run from `C:\Apps\PUGWebSite` with
> `-f docker-compose.webserver-local.yml` (project name `pugweb`).
> The general runbook (`docs/operations-runbook.html`) applies — just swap in
> this compose file.

### Update after code changes

```powershell
cd C:\Apps\PUGWebSite
git pull --ff-only origin WebserverLocal
docker compose -f docker-compose.webserver-local.yml up -d --build
# IMPORTANT: container IPs change on recreate; nginx caches upstream IPs at
# startup, so reload it or you'll get 502s on parisunitedgroup.com:
docker exec <housing-nginx> nginx -s reload
```

### Build elsewhere & copy images over (zero build load on the live server)

Use this instead of building on the server when the box is small or the live
housing portal must not be disturbed. Build on any machine with good internet,
then ship the finished images.

**On the BUILD machine** (good internet, x86-64):

```powershell
git clone https://github.com/Shamseer1988/PUGHoldingWebSite.git PUGWebSite
cd PUGWebSite
git checkout WebserverLocal
copy backend\.env.webserver-local.example backend\.env   # placeholder; build ignores its values
docker compose -f docker-compose.webserver-local.yml build
docker save -o pugweb-images.tar pugweb-backend:latest pugweb-frontend:latest
```

Copy `pugweb-images.tar` to the server (USB / share / scp).

**On the PRODUCTION server** (no build runs here):

```powershell
cd C:\Apps\PUGHoldingWebSite-Docker
docker load -i pugweb-images.tar
docker images | findstr pugweb         # confirm pugweb-backend:latest + pugweb-frontend:latest
docker compose -f docker-compose.webserver-local.yml up -d --no-build
docker exec <housing-nginx> nginx -s reload
```

`--no-build` forces Compose to use the copied images and never build. Three
musts: (1) the build PC produces **linux/amd64** (default on Intel/AMD; on an
Apple-Silicon Mac set `DOCKER_DEFAULT_PLATFORM=linux/amd64` first); (2) the
frontend's public URL is **baked at build** — building via this compose file
bakes `https://parisunitedgroup.com`, so override `NEXT_PUBLIC_API_BASE_URL` /
`NEXT_PUBLIC_SITE_URL` before building for another domain; (3) don't rename the
images — the pinned project name `pugweb` is what lets `--no-build` find them.
(If you enable the optional ARQ worker, also `docker save pugweb-worker:latest`.)

### Backup (PostgreSQL — runs inside the container; no host port published)

```powershell
docker compose -f docker-compose.webserver-local.yml exec -T postgres `
  sh -c 'pg_dump -U "$POSTGRES_USER" --no-owner --no-privileges --clean --if-exists "$POSTGRES_DB"' `
  | gzip > pug_holding-$(Get-Date -Format yyyy-MM-dd).sql.gz
```

### Restore (dumps use `--clean --if-exists`, so no DROP DATABASE needed)

```powershell
docker compose -f docker-compose.webserver-local.yml stop backend worker
# Copy the gzipped dump into the postgres container, then gunzip | psql there
# (avoids needing gunzip/psql on the Windows host).
docker compose -f docker-compose.webserver-local.yml cp pug_holding-<DATE>.sql.gz postgres:/tmp/r.sql.gz
docker compose -f docker-compose.webserver-local.yml exec -T postgres `
  sh -c 'gunzip -c /tmp/r.sql.gz | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose -f docker-compose.webserver-local.yml start backend worker
```

### Logs / stop

```powershell
docker compose -f docker-compose.webserver-local.yml logs -f backend
docker compose -f docker-compose.webserver-local.yml down           # stop (keeps data)
# docker compose -f docker-compose.webserver-local.yml down -v       # DESTRUCTIVE: drops DB
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Housing portal becomes slow/unresponsive **while building** PUG web | Resource contention, **not** a conflict (separate project, no shared host ports, separate volumes). The frontend `next build` is RAM-hungry and squeezes the running app on a small Docker VM. Raise Docker Desktop RAM to 6–8 GB, build one service at a time (`build backend` then `build frontend`), or build off-peak / on another machine (`docker save`/`load`). Runtime (`up -d`) is light and doesn't affect the live app. See the note under Step 5. |
| `502 Bad Gateway` on parisunitedgroup.com (esp. after a redeploy) | nginx cached the old container IP. `docker exec <housing-nginx> nginx -s reload`. Confirm both stacks share `pug_edge`: `docker network inspect pug_edge` should list the nginx, `pugweb-api`, and `pugweb-frontend` containers. |
| `nginx: host not found in upstream "pugweb-api"` on reload/start | The PUG stack isn't up yet, or nginx isn't on `pug_edge`. Start Step 5 first, redo Step 4, then reload. |
| `403 Forbidden` on every request | `$cf_edge` gate. Traffic isn't arriving via Cloudflare/tunnel (peer not in the allowlist). Confirm the tunnel ingress points at nginx and you're testing through `https://parisunitedgroup.com`, not the raw IP. |
| Backend container exits immediately, log says `SECRET_KEY` / `CORS_ORIGINS` | Required prod env missing in `backend\.env` (Step 2). |
| Fonts / analytics / images blocked in the browser console | A second CSP was added at nginx. The app owns its CSP — remove `add_header Content-Security-Policy …` from the Host #3 block (the drop-in already omits it). |
| Admin login fails; browser calls `http://localhost:8000/...` | The frontend image was built without the right `NEXT_PUBLIC_API_BASE_URL`. Rebuild: `docker compose -f docker-compose.webserver-local.yml build --no-cache frontend && … up -d`. |
| 521/525 from Cloudflare | Origin cert doesn't cover the apex, or the tunnel/nginx isn't reachable. Reissue the Origin cert to include `parisunitedgroup.com` (Prerequisites). |
