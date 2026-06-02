# `deploy/` — Production deployment artifacts

Everything needed to put the Paris United Group apps online is the
**standalone edge proxy** in [`edge-proxy/`](edge-proxy/) — a single nginx
that terminates TLS (Cloudflare Origin cert) behind the Cloudflare Tunnel and
routes each hostname to the right app over the shared `pug_edge` docker
network. It is shared infrastructure: it is **not** part of any one app's
compose project, and its config is a **mounted file you edit + reload** — no
image rebuild to change routing.

```
Cloudflare ──► cloudflared ──► edge-proxy nginx (deploy/edge-proxy/)
                                  │  accommodation.parisunitedgroup.com ─► housing-backend / -frontend
                                  │  parisunitedgroup.com (+ www)        ─► pugweb-api      / pugweb-frontend
                                  └  pugfin.parisunitedgroup.com         ─► (planned)
```

| Path | Purpose |
|------|---------|
| [`edge-proxy/`](edge-proxy/) | The standalone reverse proxy — `docker-compose.yml`, the mounted multi-vhost `nginx.conf`, `snippets/`, and an `ssl/` slot for the Origin cert. Start here. |
| [`edge-proxy/README.md`](edge-proxy/README.md) | Migration runbook + day-2 ops (add an app, change routing, reload, rollback). |

The PUG corporate site's own container stack (FastAPI + Next.js, no nginx of
its own) lives in [`../docker-compose.webserver-local.yml`](../docker-compose.webserver-local.yml)
at the repo root; it joins `pug_edge` as `pugweb-api` / `pugweb-frontend`, the
exact aliases `edge-proxy/nginx.conf` resolves for `parisunitedgroup.com`.

> **History:** the earlier bare-metal (systemd + host nginx) and self-contained
> AWS Docker (`docker-compose.prod.yml` + `deploy/docker/`) deployment paths
> were retired in favour of this shared edge proxy. They remain in git history
> if ever needed.
