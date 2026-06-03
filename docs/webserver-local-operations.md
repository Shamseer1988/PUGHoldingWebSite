# Operating the PUG corporate site (Local Webserver, behind the edge proxy)

Day-2 runbook for the PUG Holding website (FastAPI + Next.js) running as the
`pugweb` Docker Compose stack on the shared Windows host, **behind the
standalone edge proxy** (`deploy/edge-proxy/`). For the proxy itself — TLS,
routing, adding an app, rollback — see
[`deploy/edge-proxy/README.md`](../deploy/edge-proxy/README.md). First-time
bring-up is documented in the header of
[`docker-compose.webserver-local.yml`](../docker-compose.webserver-local.yml).

> Commands are CMD-friendly; lines marked **[PS]** are PowerShell. Replace
> `pug_user` / `pug_holding` if your `backend\.env` uses different
> `POSTGRES_USER` / `POSTGRES_DB`.

## 0 · Key facts

| | |
|---|---|
| PUG repo folder | `C:\Apps\PUGHoldingWebSite-Docker` |
| PUG compose file | `docker-compose.webserver-local.yml`  (project `pugweb`) |
| PUG branch | `WebserverLocal` |
| PUG containers | `pugweb-backend-1`, `pugweb-frontend-1`, `pugweb-postgres-1`, `pugweb-redis-1`  (`pugweb-worker-1` = opt-in) |
| Edge proxy | folder `C:\Apps\edge-proxy`, project `edge-proxy`, container `edge-proxy-nginx-1` |
| Shared network | `pug_edge` — joined by the edge proxy **and** `pugweb-api` / `pugweb-frontend` |
| On `pug_edge` | `pugweb-api:8000` (FastAPI / gunicorn), `pugweb-frontend:3000` (Next.js) |
| Public site | https://parisunitedgroup.com  (+ `www` → apex) |
| DB | user `pug_user` / database `pug_holding` |

> **Routing lives in the edge proxy now.** The `parisunitedgroup.com` vhost is
> already **Host #2** in `C:\Apps\edge-proxy\nginx.conf` (mounted, not baked).
> To change routing you **edit that file and reload — no image rebuild:**
> ```
> docker exec edge-proxy-nginx-1 nginx -t && docker exec edge-proxy-nginx-1 nginx -s reload
> ```

## 1 · Daily ops — status / logs / start / stop

```
cd C:\Apps\PUGHoldingWebSite-Docker

docker compose -f docker-compose.webserver-local.yml ps
docker compose -f docker-compose.webserver-local.yml logs -f backend
docker compose -f docker-compose.webserver-local.yml logs -f frontend

REM stop / start (KEEPS data)
docker compose -f docker-compose.webserver-local.yml stop
docker compose -f docker-compose.webserver-local.yml start

REM stop & remove containers (KEEPS volumes/data)
docker compose -f docker-compose.webserver-local.yml down

REM DANGER: also delete volumes (wipes the DB) — do not run casually
REM docker compose -f docker-compose.webserver-local.yml down -v
```

Health checks (from inside, over the edge aliases the proxy uses):
```
docker exec pugweb-backend-1 wget -qO- http://localhost:8000/api/v1/health
docker exec edge-proxy-nginx-1 wget -qO- http://pugweb-api:8000/api/v1/health
```

## 2 · Build & deploy (on the server)

```
cd C:\Apps\PUGHoldingWebSite-Docker
docker compose -f docker-compose.webserver-local.yml up -d --build
```

Flaky internet / small box? Build one image at a time and auto-retry — the
pip/npm cache mounts make each retry **resume** instead of re-downloading: **[PS]**
```
do { docker compose -f docker-compose.webserver-local.yml build backend }  until ($LASTEXITCODE -eq 0)
do { docker compose -f docker-compose.webserver-local.yml build frontend } until ($LASTEXITCODE -eq 0)
docker compose -f docker-compose.webserver-local.yml up -d
```

Confirm both stacks share the edge network (should list `edge-proxy-nginx-1`
plus `pugweb-api` / `pugweb-frontend`):
```
docker network inspect pug_edge --format "{{range .Containers}}{{.Name}} {{end}}"
```

> The frontend's browser-facing URL (`NEXT_PUBLIC_API_BASE_URL`) is **baked at
> build time** and defaults to `https://parisunitedgroup.com/api/v1`. Override
> it before building for a different domain.

## 3 · Update after code changes

```
cd C:\Apps\PUGHoldingWebSite-Docker
git pull origin WebserverLocal
docker compose -f docker-compose.webserver-local.yml up -d --build
```

The backend auto-runs `alembic upgrade head` on boot, so new migrations apply
automatically. **No edge-proxy reload needed after a PUG redeploy** — the proxy
resolves `pugweb-api` / `pugweb-frontend` at request time via Docker DNS
(`resolver 127.0.0.11`), so it picks up the recreated containers' new IPs on
its own.

## 4 · Build elsewhere → copy images over (zero build load on the server)

**On a machine with good internet (linux/amd64):**
```
git clone https://github.com/Shamseer1988/PUGHoldingWebSite.git PUGWebSite
cd PUGWebSite && git checkout WebserverLocal
copy backend\.env.webserver-local.example backend\.env   REM placeholder; build ignores it
docker compose -f docker-compose.webserver-local.yml build
docker save -o pugweb-images.tar pugweb-backend:latest pugweb-frontend:latest
```
**On the server** (no build runs):
```
cd C:\Apps\PUGHoldingWebSite-Docker
docker load -i pugweb-images.tar
docker compose -f docker-compose.webserver-local.yml up -d --no-build
```
Notes: the build PC must produce **linux/amd64** (default on Intel/AMD); the
public URL is **baked at build**; `--no-build` forces use of the copied images —
don't rename them, the pinned `pugweb` project name is what lets it find them.
(If you run the optional ARQ worker, also `docker save pugweb-worker:latest`.)

## 5 · Seed baseline data (brand-new empty DB only — skip if you restored a backup)

```
docker compose -f docker-compose.webserver-local.yml exec backend python -m app.scripts.seed_users
docker compose -f docker-compose.webserver-local.yml exec backend python -m app.scripts.seed_cms
docker compose -f docker-compose.webserver-local.yml exec backend python -m app.scripts.seed_hr
```
Seeders are idempotent. **Change the seeded admin password immediately.**

## 6 · Backup — PostgreSQL (custom-format `.dump`)

```
docker exec pugweb-postgres-1 pg_dump -U pug_user -Fc -f /tmp/pug_backup.dump pug_holding
docker cp pugweb-postgres-1:/tmp/pug_backup.dump .\pug_backup_pug_holding.dump
```
Timestamped filename: **[PS]**
```
docker exec pugweb-postgres-1 pg_dump -U pug_user -Fc -f /tmp/pug_backup.dump pug_holding
docker cp pugweb-postgres-1:/tmp/pug_backup.dump ".\pug_backup_pug_holding_$(Get-Date -Format yyyyMMdd_HHmmss).dump"
```
Uploads (only if you store media on local disk instead of Cloudflare R2):
```
docker cp pugweb-backend-1:/app/uploads .\pug_uploads_backup
```

## 7 · Restore — PostgreSQL (the sequence that worked)

```
cd C:\Apps\PUGHoldingWebSite-Docker

REM 1) copy the dump into the postgres container (plain docker cp, NOT compose cp)
docker cp "pug_backup_pug_holding_<DATE>.dump" pugweb-postgres-1:/tmp/restore.dump

REM 2) stop the app so nothing holds DB connections during the restore
docker stop pugweb-backend-1

REM 3) recreate the DB and restore the dump into it
docker exec pugweb-postgres-1 psql -U pug_user -d postgres -c "DROP DATABASE IF EXISTS pug_holding;"
docker exec pugweb-postgres-1 psql -U pug_user -d postgres -c "CREATE DATABASE pug_holding OWNER pug_user;"
docker exec pugweb-postgres-1 pg_restore --no-owner --no-privileges -U pug_user -d pug_holding /tmp/restore.dump

REM 4) start the app again (runs alembic upgrade head to catch up if needed)
docker start pugweb-backend-1
```
If *"database … is being accessed by other users"*: kill connections, retry step 3:
```
docker exec pugweb-postgres-1 psql -U pug_user -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='pug_holding';"
```
If `pg_restore` says *"input file does not appear to be a valid archive"*, the
file is plain SQL, not custom format → use `psql -U pug_user -d pug_holding -f /tmp/restore.dump`.

## 8 · Edge proxy & Cloudflare

- The corporate vhost is **Host #2** in `C:\Apps\edge-proxy\nginx.conf` — there
  is nothing to add for `parisunitedgroup.com`. Routing edits = edit that file +
  `docker exec edge-proxy-nginx-1 nginx -s reload` (see
  [`deploy/edge-proxy/README.md`](../deploy/edge-proxy/README.md)).
- `parisunitedgroup.com` + `www` are public hostnames on the **same** Cloudflare
  Tunnel that serves `accommodation.parisunitedgroup.com`, pointing at the edge
  proxy. The Cloudflare **Origin Certificate must cover both** the apex
  (`parisunitedgroup.com`) and the wildcard (`*.parisunitedgroup.com`).

## 9 · Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `502 Bad Gateway` on parisunitedgroup.com | App down or not on `pug_edge`. Check `docker network inspect pug_edge` lists `edge-proxy-nginx-1` + `pugweb-api` + `pugweb-frontend`; bring the stack up (§1). No proxy reload needed — it re-resolves on its own. |
| `403 Forbidden` on every request | The `$cf_edge` gate — traffic didn't arrive via Cloudflare/tunnel. Test through `https://parisunitedgroup.com`, not the raw IP. |
| `wget: bad address 'pugweb-backend:8000'` | Wrong name. On `pug_edge` the backend's alias is **`pugweb-api`** (`pugweb-api:8000`); `pugweb-backend-1` is only the container name. |
| Backend exits immediately, log says `SECRET_KEY` / `CORS_ORIGINS` | Required production env missing in `backend\.env`. |
| Admin login calls `http://localhost:8000` / fonts blocked | Frontend image built with the wrong `NEXT_PUBLIC_API_BASE_URL`. Rebuild: `docker compose -f docker-compose.webserver-local.yml build --no-cache frontend` then `… up -d`. |
| Live site slows/stalls **while building** | Resource contention (RAM-hungry `next build`), not a conflict. Give Docker Desktop 6–8 GB, build one image at a time (§2), or build off-peak / elsewhere (§4). |
| `521`/`525` from Cloudflare | Origin cert doesn't cover the apex, or the tunnel/proxy is unreachable. Reissue the Origin cert to include `parisunitedgroup.com`. |
