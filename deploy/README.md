# `deploy/` — Deployment notes

The Paris United Group apps are served by two pieces:

1. **The app stack** — [`../docker-compose.webserver-local.yml`](../docker-compose.webserver-local.yml)
   (FastAPI + Next.js, Postgres, Redis), with no nginx of its own. It joins the
   shared `pug_edge` docker network as `pugweb-api` / `pugweb-frontend`. For
   local access at http://localhost:3000, add the
   [`../docker-compose.local-access.yml`](../docker-compose.local-access.yml) overlay.
2. **A standalone edge proxy** — a single shared nginx that terminates TLS
   (Cloudflare Origin cert) behind the Cloudflare Tunnel and routes each
   hostname to the right app over `pug_edge`. It is **managed on the server at
   `C:\Apps\edge-proxy` and is not tracked in this repo** — its `nginx.conf` is
   a mounted file you edit + reload (`docker exec edge-proxy-nginx-1 nginx -s reload`),
   no rebuild.

```
Cloudflare ──► cloudflared ──► edge-proxy nginx (C:\Apps\edge-proxy, server-managed)
                                  │  accommodation.parisunitedgroup.com ─► housing-backend / -frontend
                                  └  parisunitedgroup.com (+ www)        ─► pugweb-api      / pugweb-frontend
```

Full operations runbook (build/deploy, update, seed, backup/restore, edge-proxy
+ Cloudflare, troubleshooting):
[`../docs/webserver-local-operations.md`](../docs/webserver-local-operations.md).

> **History:** the earlier bare-metal (systemd + host nginx) and self-contained
> AWS Docker (`docker-compose.prod.yml` + `deploy/docker/`) deployment paths
> were retired, and the in-repo copy of the edge-proxy stack was later removed
> too (it now lives only on the server). All remain in git history.
