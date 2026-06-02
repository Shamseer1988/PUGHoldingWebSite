# Docker deployment — superseded

> ⚠️ **This runbook described the self-contained AWS Docker stack
> (`docker-compose.prod.yml` with its own baked-in nginx + `deploy/docker/`),
> which has been retired.**
>
> Production now runs behind the **standalone edge proxy** — a single shared
> nginx that terminates TLS and routes every app over the `pug_edge` docker
> network. See:
>
> - [`deploy/edge-proxy/README.md`](../deploy/edge-proxy/README.md) — the edge
>   proxy stack and its migration / day-2 runbook.
> - [`docker-compose.webserver-local.yml`](../docker-compose.webserver-local.yml)
>   — the PUG corporate site's container stack (no nginx of its own; joins
>   `pug_edge` as `pugweb-api` / `pugweb-frontend`).
>
> The previous Docker-on-EC2 instructions (Cloudflare Origin cert paste,
> security-group firewalling, `docker-compose.prod.yml` operations) remain in
> git history if you need them.
