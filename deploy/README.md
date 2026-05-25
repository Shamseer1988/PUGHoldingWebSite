# `deploy/` — Production deployment artifacts

Ready-to-copy configuration files for the production stack described in
[`docs/deployment-guide.md`](../docs/deployment-guide.md). Use them as
starting points and adjust the domain, paths, and tuning to match your
environment.

| File | Destination on the server | Purpose |
|------|---------------------------|---------|
| [`systemd/pug-backend.service`](systemd/pug-backend.service) | `/etc/systemd/system/pug-backend.service` | FastAPI under Gunicorn + Uvicorn workers |
| [`systemd/pug-frontend.service`](systemd/pug-frontend.service) | `/etc/systemd/system/pug-frontend.service` | Next.js in production mode (`next start`) |
| [`nginx/pug-holding.conf`](nginx/pug-holding.conf) | `/etc/nginx/sites-available/pug-holding.conf` | Reverse proxy, TLS, static-asset serving, security headers |
| [`scripts/pg_backup.sh`](scripts/pg_backup.sh) | `/usr/local/bin/pug-pg-backup` (chmod +x) | Daily PostgreSQL dump + 14-day retention, optional S3 push |
| [`logrotate/pug`](logrotate/pug) | `/etc/logrotate.d/pug` | Rotates `/var/log/pug/*.log` (backup log, etc.) |

After copying:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pug-backend pug-frontend
sudo nginx -t && sudo systemctl reload nginx
```

For the full step-by-step walkthrough — including PostgreSQL hardening,
Cloudflare DNS + Origin Certificate setup, restore drills, and a
troubleshooting matrix — see
[`docs/deployment-guide.md`](../docs/deployment-guide.md).
