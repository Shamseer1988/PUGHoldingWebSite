# Standalone edge proxy — migration runbook

Move nginx **out of** the Employee-Housing project into its own
`C:\Apps\edge-proxy` stack, so the reverse proxy is shared infrastructure that
every app sits behind — and its config is a **mounted file** you edit + reload
(no more rebuilding an app to change routing).

```
BEFORE                                   AFTER
------                                   -----
cloudflared                              cloudflared
   |                                        |
 nginx  (inside pug-accommodation-prod)   nginx  (C:\Apps\edge-proxy, standalone)
   |  default net -> housing back/front      |  pug_edge -> housing-backend / -frontend
   |  pug_edge   -> pugweb-api / -frontend    |          -> pugweb-api / pugweb-frontend
                                              |          -> pugfin-* (later)
 housing app + pugweb app                  housing app + pugweb app
   (each with its own DB/redis)              (each on its own private net + pug_edge)
```

Everything talks over the existing **`pug_edge`** network. Each app keeps its
DB/Redis on its own private network; only the `backend`/`frontend` join
`pug_edge` so the proxy can reach them.

> ⚠️ This swaps the live proxy, so there's a **few-seconds downtime** for both
> sites during the cutover. Do it at a quiet time. A rollback is at the bottom.

---

## Step 1 — Create `C:\Apps\edge-proxy` with these files

Pull the repo and copy the folder (or save the files I sent):
```powershell
cd C:\Apps\PUGHoldingWebSite-Docker
git pull origin WebserverLocal
xcopy /E /I deploy\edge-proxy C:\Apps\edge-proxy
```
You should have: `docker-compose.yml`, `nginx.conf`, `snippets\*.conf`, and an
empty `ssl\` folder to fill next.

## Step 2 — Copy the SSL cert (and, if you customised them, the snippets)

```powershell
mkdir C:\Apps\edge-proxy\ssl 2>NUL
copy C:\Apps\Employee-Housing-Control-Portal\deploy\ssl\origin.crt C:\Apps\edge-proxy\ssl\
copy C:\Apps\Employee-Housing-Control-Portal\deploy\ssl\origin.key C:\Apps\edge-proxy\ssl\
```
> The `snippets\` in this folder are standard, working versions. If your
> housing `deploy\snippets\` differ, copy those over the ones here so behaviour
> stays identical:
> `copy C:\Apps\Employee-Housing-Control-Portal\deploy\snippets\*.conf C:\Apps\edge-proxy\snippets\`

## Step 3 — Edit the Housing compose: apps onto `pug_edge`, drop its nginx

In `C:\Apps\Employee-Housing-Control-Portal\docker-compose.prod.yml`:

**a) Put `backend` and `frontend` on the shared network with stable aliases.**
Add a `networks:` block to each (keep `default` so they still reach db/redis):
```yaml
  backend:
    # ... everything you already have ...
    networks:
      default: {}
      edge:
        aliases:
          - housing-backend     # nginx Host #1 /api/ + /health target

  frontend:
    # ... everything you already have ...
    networks:
      default: {}
      edge:
        aliases:
          - housing-frontend    # nginx Host #1 / target
```

**b) DELETE the entire `nginx:` service** from this file (the standalone stack
replaces it). Leave `db`, `redis`, `backend`, `frontend`, `worker`, `beat`
as they are (no `networks:` key → they stay on the private `default` net).

**c) Make sure the external network is declared** at the bottom (it already is):
```yaml
networks:
  edge:
    external: true
    name: pug_edge
```

## Step 4 — Cut over (the few-seconds swap)

```powershell
REM 1) Recreate the housing app: backend/frontend join pug_edge, old nginx removed
cd C:\Apps\Employee-Housing-Control-Portal
docker compose -f docker-compose.prod.yml up -d --remove-orphans
REM   (--remove-orphans deletes the now-undefined nginx container, freeing :80/:443)

REM 2) Start the standalone edge proxy (binds :80/:443)
cd C:\Apps\edge-proxy
docker compose up -d
```

## Step 5 — Verify

```powershell
REM pug_edge should now list: edge-proxy-nginx-1, housing-backend/-frontend (the
REM housing backend/frontend containers), pugweb-backend-1, pugweb-frontend-1
docker network inspect pug_edge --format "{{range .Containers}}{{.Name}} {{end}}"

docker exec edge-proxy-nginx-1 nginx -t
docker exec edge-proxy-nginx-1 wget -qO- http://housing-backend:5000/api/v1/health
docker exec edge-proxy-nginx-1 wget -qO- http://pugweb-api:8000/api/v1/health
```
Then load both sites:
- https://accommodation.parisunitedgroup.com
- https://parisunitedgroup.com  (+ /admin/login)

## Step 6 — ⚠️ Cloudflare Tunnel target (check BEFORE you trust the cutover)

How does your `cloudflared` reach nginx today?
- **Targets the host port** (ingress like `https://localhost:443` / `http://localhost:80`):
  nothing to change — the edge proxy binds the same host ports, so it's
  transparent. ✅
- **Targets the docker service name** (ingress like `https://nginx:443`) and
  `cloudflared` runs as a container: the edge proxy is reachable as **`nginx`**
  on `pug_edge`, so add `cloudflared` to the `pug_edge` network (or move it into
  this stack). Otherwise it can't find the proxy after the move.

If unsure, check your cloudflared config / `config.yml` ingress before cutover.

---

## Rollback (if anything's off)

```powershell
REM 1) Stop the standalone proxy (frees :80/:443)
cd C:\Apps\edge-proxy
docker compose down

REM 2) Restore the nginx service you deleted in Step 3b (git/editor undo), then:
cd C:\Apps\Employee-Housing-Control-Portal
docker compose -f docker-compose.prod.yml up -d --build nginx
```
You're back to the previous setup. (Keeping the backend/frontend `networks:`
additions from Step 3a is harmless either way.)

---

## Day-2: change routing WITHOUT a rebuild

The whole point of this stack — edit the mounted config and reload:
```powershell
notepad C:\Apps\edge-proxy\nginx.conf
docker exec edge-proxy-nginx-1 nginx -t      && ^
docker exec edge-proxy-nginx-1 nginx -s reload
```
Adding the finance app later = put its services on `pug_edge` (aliases
`pugfin-backend` / `pugfin-frontend`), uncomment Host #3 in `nginx.conf`,
reload. No image builds anywhere.
