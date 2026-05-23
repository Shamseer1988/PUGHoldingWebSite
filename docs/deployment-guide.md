# Deployment Guide (placeholder)

The full AWS Ubuntu + Nginx + Cloudflare + systemd / Gunicorn / Uvicorn
deployment guide is delivered in **Phase 20**.

This page is intentionally short during Phase 1; later phases will add:

- AWS Ubuntu / Debian server preparation.
- PostgreSQL installation, hardening, and backups.
- Backend service (Gunicorn + Uvicorn workers via systemd).
- Frontend service (Next.js standalone build under PM2 or systemd).
- Nginx reverse proxy configuration.
- Cloudflare DNS and SSL.
- Environment variable management for production.
- Log inspection and restart runbooks.
- Troubleshooting guide.

## Phase 1 placeholders

For now you only need:

- A Linux host with Python 3.11+, Node 18.18+, PostgreSQL 14+.
- The `setup-guide.md` instructions adapted to your environment.
- A reverse proxy that forwards `/` to Next.js (port 3000) and
  `/api` to FastAPI (port 8000) once Phase 2 introduces real APIs.
