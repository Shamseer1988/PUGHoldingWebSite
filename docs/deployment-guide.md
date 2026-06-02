# Production Deployment Guide — superseded

> ⚠️ **This guide described the bare-metal deployment (FastAPI under systemd,
> Next.js under systemd, a host-installed nginx, `pg_backup.sh` + logrotate on
> the host). That path has been retired** along with its `deploy/{systemd,
> nginx,scripts,logrotate}/` artifacts.
>
> The apps now run as Docker Compose stacks behind the **standalone edge
> proxy** — a single shared nginx that terminates TLS (Cloudflare Origin cert)
> behind the Cloudflare Tunnel and routes every host over the `pug_edge`
> network. See:
>
> - [`deploy/edge-proxy/README.md`](../deploy/edge-proxy/README.md) — the edge
>   proxy stack, migration runbook, and day-2 operations.
> - [`docker-compose.webserver-local.yml`](../docker-compose.webserver-local.yml)
>   — the PUG corporate site's container stack (FastAPI + Next.js), joined to
>   `pug_edge` as `pugweb-api` / `pugweb-frontend`.
>
> For local development setup, see [`setup-guide.md`](setup-guide.md).
>
> The original bare-metal walkthrough (PostgreSQL hardening, Cloudflare DNS +
> Origin Certificate, backup/restore drills, rollback) remains in git history.
