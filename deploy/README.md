# `deploy/` — Production deployment artifacts

Ready-to-copy configuration files for the Paris United Group corporate
website + HR ATS portal, tuned for the shared Ubuntu EC2 host that
already runs the **PUG Accounts** application. Each file's
destination path matches the runbook in
[`docs/deployment-guide.md`](../docs/deployment-guide.md).

| File | Destination on the server | Purpose |
|------|---------------------------|---------|
| [`systemd/pugweb-backend.service`](systemd/pugweb-backend.service) | `/etc/systemd/system/pugweb-backend.service` | FastAPI under Gunicorn + Uvicorn workers, bound to `127.0.0.1:8000`. |
| [`systemd/pugweb-frontend.service`](systemd/pugweb-frontend.service) | `/etc/systemd/system/pugweb-frontend.service` | Next.js in production mode (`npm run start`), bound to `127.0.0.1:3000`. |
| [`nginx/parisgroup.conf`](nginx/parisgroup.conf) | `/etc/nginx/sites-available/parisgroup` (then `ln -s …/sites-enabled/`) | Reverse proxy for `parisunitedgroup.com` + `www.…`. Phase 1 = HTTP only; Phase 2 = HTTPS via Cloudflare Origin Cert (commented section in the same file). Leaves the existing `pugaccounts` site config untouched. |
| [`scripts/pg_backup.sh`](scripts/pg_backup.sh) | `/usr/local/bin/pugweb-pg-backup` (chmod +x) | Daily `pg_dump` of `pug_holding` + 14-day retention, optional S3 push. |
| [`logrotate/pugweb`](logrotate/pugweb) | `/etc/logrotate.d/pugweb` | Rotates `/var/log/pugweb/*.log` (backup log, etc.). |

After copying:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pugweb-backend pugweb-frontend
sudo nginx -t && sudo systemctl reload nginx
```

The new services use the `parisgroup` Linux user and read from
`/home/parisgroup/PugWebSite`, matching the production deployment.
**Do not edit** the existing `pugaccounts.service` /
`/etc/nginx/sites-available/pugaccounts` files — the PUG Accounts
app on `pugfinapp.parisunitedgroup.com` must stay isolated.

For the full step-by-step — including PostgreSQL hardening,
Cloudflare DNS + Origin Certificate setup, restore drills, and a
troubleshooting matrix — see
[`docs/deployment-guide.md`](../docs/deployment-guide.md).
