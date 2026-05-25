# Production Deployment Guide

This guide walks a single Ubuntu 22.04 LTS server through a complete
production deployment of the **Paris United Group Holding** stack:
FastAPI backend, Next.js frontend, PostgreSQL database, Nginx reverse
proxy, and Cloudflare DNS + SSL.

For local development setup, see [`setup-guide.md`](setup-guide.md).

Ready-to-copy config files referenced below live under
[`deploy/`](../deploy/) at the repo root.

---

## Architecture

```
                 ┌──────────────────────────────────────┐
   User browser ─┤   Cloudflare (DNS + Edge TLS)        │
                 └──────────────┬───────────────────────┘
                                │  https://www.parisunitedgroup.com
                                ▼
              ┌─────────────────────────────────────────┐
              │  Ubuntu 22.04 server (single box)       │
              │                                         │
              │   :80  Nginx ──► :443 TLS (Origin Cert) │
              │           │                             │
              │           ├── /             → :3000     │
              │           │      (Next.js — npm start)  │
              │           │                             │
              │           └── /api/v1/      → :8000     │
              │                  (FastAPI — gunicorn +  │
              │                   uvicorn workers)      │
              │                                         │
              │   :5432  PostgreSQL 14 (localhost only) │
              │                                         │
              │   /var/www/pug/uploads/  CV + media     │
              │                                         │
              └─────────────────────────────────────────┘
```

**Two-host variant.** If you split the database onto a managed instance
(Amazon RDS, Azure Database for PostgreSQL, etc.), swap the database
host in the backend `.env` and skip the local PostgreSQL section.
Everything else stays identical.

**Port map (after deployment).**

| Port  | Service               | Bind        | Reachable from           |
|-------|-----------------------|-------------|--------------------------|
| 80    | Nginx (HTTP)          | `0.0.0.0`   | Public, redirects to 443 |
| 443   | Nginx (HTTPS)         | `0.0.0.0`   | Public                   |
| 3000  | Next.js (`npm start`) | `127.0.0.1` | Localhost only           |
| 8000  | FastAPI (gunicorn)    | `127.0.0.1` | Localhost only           |
| 5432  | PostgreSQL            | `127.0.0.1` | Localhost only           |

---

## Pre-deployment checklist

- [ ] Ubuntu 22.04 LTS server provisioned (AWS EC2 t3.medium or larger
      recommended; 2 GB RAM minimum).
- [ ] DNS managed via Cloudflare with the `parisunitedgroup.com` zone
      created (or whichever domain you use).
- [ ] SSH access as a non-root sudoer.
- [ ] Open security-group ingress for ports **22** (SSH from your IP),
      **80**, and **443**. Keep **5432**, **3000**, **8000** closed.
- [ ] Production secrets prepared:
  - 32-byte `SECRET_KEY` (`openssl rand -hex 32`)
  - PostgreSQL password (long, randomly generated)
  - Azure OpenAI endpoint + key (or leave blank to disable AI)
  - SMTP credentials (or leave blank — contact form still records to DB)

---

## 1 · Server preparation

```bash
# As ubuntu user
sudo apt update && sudo apt upgrade -y

# Base toolchain + build deps
sudo apt install -y \
    build-essential git curl ca-certificates \
    python3.11 python3.11-venv python3.11-dev \
    libpq-dev \
    nginx \
    ufw fail2ban \
    unattended-upgrades

# Node.js 20 LTS via NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify versions
python3.11 --version    # Python 3.11.x
node --version          # v20.x.x
nginx -v
```

### Firewall (UFW)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow "Nginx Full"
sudo ufw enable
sudo ufw status verbose
```

### Dedicated service user

Running services as a non-login system user keeps file ownership clean
and reduces blast radius if a process is compromised.

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin --home-dir /var/lib/pug pug
sudo mkdir -p /opt/pug /var/log/pug /var/www/pug/uploads
sudo chown -R pug:pug /opt/pug /var/log/pug /var/www/pug
```

---

## 2 · PostgreSQL

### Install

```bash
sudo apt install -y postgresql-14
sudo systemctl enable --now postgresql
```

### Create database + role

```bash
sudo -u postgres psql <<'SQL'
CREATE USER pug_user WITH PASSWORD 'REPLACE_ME_STRONG_PASSWORD';
CREATE DATABASE pug_holding OWNER pug_user;
GRANT ALL PRIVILEGES ON DATABASE pug_holding TO pug_user;
\c pug_holding
GRANT ALL ON SCHEMA public TO pug_user;
SQL
```

### Hardening

Edit `/etc/postgresql/14/main/postgresql.conf`:

```ini
listen_addresses = 'localhost'    # never expose to the public Internet
```

Edit `/etc/postgresql/14/main/pg_hba.conf` — replace the default
`host all all 127.0.0.1/32 trust` line with:

```
local   all   postgres              peer
local   all   all                   scram-sha-256
host    all   all   127.0.0.1/32    scram-sha-256
host    all   all   ::1/128         scram-sha-256
```

Apply changes:

```bash
sudo systemctl restart postgresql
sudo -u postgres psql -c "SELECT version();"
```

### Connection check

```bash
PGPASSWORD='REPLACE_ME_STRONG_PASSWORD' \
  psql -h 127.0.0.1 -U pug_user -d pug_holding -c '\dt'
```

---

## 3 · Backend (FastAPI + gunicorn)

### Clone + virtualenv

```bash
sudo -u pug git clone <repo-url> /opt/pug/app
cd /opt/pug/app/backend

sudo -u pug python3.11 -m venv /opt/pug/app/backend/.venv
sudo -u pug /opt/pug/app/backend/.venv/bin/pip install --upgrade pip wheel
sudo -u pug /opt/pug/app/backend/.venv/bin/pip install -r requirements.txt
```

### Production `.env`

```bash
sudo -u pug cp /opt/pug/app/backend/.env.example /opt/pug/app/backend/.env
sudo -u pug nano /opt/pug/app/backend/.env
```

Set these values in `/opt/pug/app/backend/.env`:

```ini
APP_ENV=production
APP_DEBUG=false
APP_HOST=127.0.0.1          # bind to loopback — Nginx fronts the public traffic
APP_PORT=8000

SECRET_KEY=<output of `openssl rand -hex 32`>
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
ALGORITHM=HS256

POSTGRES_USER=pug_user
POSTGRES_PASSWORD=<the strong password from step 2>
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=pug_holding

# Comma-separated. ADD the production domain(s) so the browser can call
# the API. Localhost stays for local SSR fetches.
CORS_ORIGINS=https://www.parisunitedgroup.com,https://parisunitedgroup.com

UPLOAD_DIR=/var/www/pug/uploads
MAX_UPLOAD_SIZE_MB=20

# Leave AI_ENABLED=false until Azure OpenAI is provisioned. The HR AI
# review service falls back to mock mode automatically when keys are
# missing.
AI_ENABLED=true
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_DEPLOYMENT=<deployment-name>
AZURE_OPENAI_API_VERSION=2024-08-01-preview

SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=<api-key>
SMTP_FROM_EMAIL=noreply@parisunitedgroup.com
SMTP_USE_TLS=true
```

Lock the file down — it contains every secret:

```bash
sudo chown pug:pug /opt/pug/app/backend/.env
sudo chmod 600 /opt/pug/app/backend/.env
```

### Migrate + seed

```bash
cd /opt/pug/app/backend
sudo -u pug /opt/pug/app/backend/.venv/bin/alembic upgrade head
sudo -u pug /opt/pug/app/backend/.venv/bin/python -m app.scripts.seed_users
sudo -u pug /opt/pug/app/backend/.venv/bin/python -m app.scripts.seed_cms
sudo -u pug /opt/pug/app/backend/.venv/bin/python -m app.scripts.seed_hr
```

**Change every seeded user's password before going live** — the
default `ChangeMe!123` is documented and well known. Log into
each portal once and rotate.

### systemd unit

Copy [`deploy/systemd/pug-backend.service`](../deploy/systemd/pug-backend.service)
to `/etc/systemd/system/pug-backend.service`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pug-backend
sudo systemctl status pug-backend
```

Confirm health:

```bash
curl -s http://127.0.0.1:8000/api/v1/health
# {"status":"ok","database":"connected", ...}
```

---

## 4 · Frontend (Next.js)

### Clone + install

The frontend lives under the same repo. Re-use the clone from step 3
and just install + build:

```bash
cd /opt/pug/app/frontend
sudo -u pug npm ci
```

### Production `.env.production`

```bash
sudo -u pug nano /opt/pug/app/frontend/.env.production
```

```ini
# Server-side (SSR) calls — loopback is fastest.
API_BASE_URL=http://127.0.0.1:8000/api/v1

# Client-side calls — must be the PUBLIC origin so the browser can
# reach it. With our Nginx config, /api/v1/* on the public domain is
# proxied to FastAPI, so we just use the site origin.
NEXT_PUBLIC_API_BASE_URL=https://www.parisunitedgroup.com/api/v1

NEXT_PUBLIC_SITE_URL=https://www.parisunitedgroup.com
NEXT_PUBLIC_SITE_NAME=Paris United Group Holding
```

### Build

```bash
cd /opt/pug/app/frontend
sudo -u pug npm run build
```

### systemd unit

Copy [`deploy/systemd/pug-frontend.service`](../deploy/systemd/pug-frontend.service)
to `/etc/systemd/system/pug-frontend.service`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pug-frontend
sudo systemctl status pug-frontend

# Smoke test
curl -sI http://127.0.0.1:3000 | head -1
# HTTP/1.1 200 OK
```

---

## 5 · Nginx reverse proxy

Copy [`deploy/nginx/pug-holding.conf`](../deploy/nginx/pug-holding.conf)
to `/etc/nginx/sites-available/pug-holding.conf` and adjust the
`server_name` and certificate paths. The config:

- Listens on **80** and **443**.
- Redirects HTTP → HTTPS.
- Proxies `/api/v1/` to FastAPI (`127.0.0.1:8000`).
- Proxies everything else to Next.js (`127.0.0.1:3000`).
- Sets `client_max_body_size 20m` so CV uploads aren't truncated.
- Adds reasonable security headers and gzip.
- Streams responses (no buffering) so SSE / future streaming endpoints
  work.

Enable + test + reload:

```bash
sudo ln -sf /etc/nginx/sites-available/pug-holding.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

---

## 6 · Cloudflare DNS + SSL

### DNS records

In the Cloudflare dashboard for the zone:

| Type | Name | Content              | Proxy   |
|------|------|----------------------|---------|
| A    | @    | <server public IPv4> | Proxied |
| A    | www  | <server public IPv4> | Proxied |

### SSL mode: **Full (strict)**

The "strict" mode requires a valid certificate on the origin. Cloudflare
issues a free 15-year **Origin Certificate** that's only trusted by
Cloudflare — perfect for this setup.

1. Cloudflare → SSL/TLS → Origin Server → **Create Certificate**.
2. Hostnames: `parisunitedgroup.com, *.parisunitedgroup.com`.
3. Validity: 15 years.
4. Save the certificate and private key to the server:

```bash
sudo mkdir -p /etc/ssl/cloudflare
sudo nano /etc/ssl/cloudflare/origin.pem    # paste cert
sudo nano /etc/ssl/cloudflare/origin.key    # paste private key
sudo chmod 644 /etc/ssl/cloudflare/origin.pem
sudo chmod 600 /etc/ssl/cloudflare/origin.key
```

The Nginx config from step 5 already references these paths.

### Cloudflare → SSL/TLS → Edge Certificates

- **Always Use HTTPS:** On
- **Automatic HTTPS Rewrites:** On
- **Minimum TLS Version:** TLS 1.2

### Verify

```bash
# From your laptop
curl -sI https://www.parisunitedgroup.com/api/v1/health
# HTTP/2 200
```

---

## 7 · Uploads + static files

Uploaded CVs, logos, and media files live under
`/var/www/pug/uploads/`. FastAPI mounts this path at
`/api/v1/uploads/...` automatically (configured by `UPLOAD_DIR`).

For better performance, serve uploads directly from Nginx without
hitting FastAPI. The provided Nginx config already does this:

```nginx
location /api/v1/uploads/ {
    alias /var/www/pug/uploads/;
    expires 7d;
    add_header Cache-Control "public, immutable";
}
```

---

## 8 · Backups

### Daily PostgreSQL dump → local

Install the cron job:

```bash
sudo cp /opt/pug/app/deploy/scripts/pg_backup.sh /usr/local/bin/pug-pg-backup
sudo chmod +x /usr/local/bin/pug-pg-backup
sudo install -d -o pug -g pug /var/backups/pug
```

Add to root's crontab (`sudo crontab -e`):

```cron
# Daily 02:30 UTC PostgreSQL dump + 14-day rotation
30 2 * * * /usr/local/bin/pug-pg-backup >> /var/log/pug/backup.log 2>&1
```

The script keeps the last 14 days. See
[`deploy/scripts/pg_backup.sh`](../deploy/scripts/pg_backup.sh) for the
implementation.

### Optional: push to S3

Uncomment the `aws s3 cp` line in the script and configure an IAM
role on the EC2 instance with `s3:PutObject` on your backup bucket.

### Restore

```bash
# Stop the API to prevent writes during restore
sudo systemctl stop pug-backend

# Drop and recreate the database
sudo -u postgres psql -c "DROP DATABASE pug_holding;"
sudo -u postgres psql -c "CREATE DATABASE pug_holding OWNER pug_user;"

# Restore the chosen dump
gunzip -c /var/backups/pug/pug_holding-2026-05-25.sql.gz \
  | sudo -u postgres psql pug_holding

# Start the API
sudo systemctl start pug-backend
```

### Uploads backup

`/var/www/pug/uploads/` should be included in your filesystem backup.
A quick rsync to a sibling host:

```bash
rsync -aH --delete /var/www/pug/uploads/ backup-host:/srv/pug-uploads/
```

Add to the same daily cron for symmetry with the DB backup.

---

## 9 · Logs

```bash
# Backend (FastAPI / gunicorn / uvicorn) — most recent 200 lines, follow
sudo journalctl -u pug-backend -n 200 -f

# Frontend (Next.js)
sudo journalctl -u pug-frontend -n 200 -f

# Nginx
sudo tail -f /var/log/nginx/pug-access.log
sudo tail -f /var/log/nginx/pug-error.log

# PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-14-main.log

# Backup job
sudo tail -f /var/log/pug/backup.log
```

### Log rotation

systemd-journald rotates the service logs automatically. Nginx logs
are rotated by the `logrotate` package's default config under
`/etc/logrotate.d/nginx`. The custom `/var/log/pug/` directory uses the
file shipped at [`deploy/logrotate/pug`](../deploy/logrotate/pug):

```bash
sudo cp /opt/pug/app/deploy/logrotate/pug /etc/logrotate.d/pug
sudo logrotate -d /etc/logrotate.d/pug    # dry-run to verify
```

---

## 10 · Runbooks

### Restart everything

```bash
sudo systemctl restart pug-backend pug-frontend nginx
```

### Deploy new code

```bash
# 1. Pull
cd /opt/pug/app && sudo -u pug git pull

# 2. Backend deps (only if requirements.txt changed)
sudo -u pug /opt/pug/app/backend/.venv/bin/pip install -r /opt/pug/app/backend/requirements.txt

# 3. Database migrations (idempotent — safe to run every deploy)
cd /opt/pug/app/backend
sudo -u pug /opt/pug/app/backend/.venv/bin/alembic upgrade head

# 4. Frontend rebuild
cd /opt/pug/app/frontend
sudo -u pug npm ci          # only if package-lock.json changed
sudo -u pug npm run build

# 5. Restart services (one at a time to avoid downtime)
sudo systemctl restart pug-backend
sudo systemctl restart pug-frontend

# 6. Smoke test
curl -fsS https://www.parisunitedgroup.com/api/v1/health
curl -fsSI https://www.parisunitedgroup.com/ | head -1
```

### Rollback to previous commit

```bash
cd /opt/pug/app
sudo -u pug git log --oneline -5         # find the last-known-good SHA
sudo -u pug git checkout <good-sha>

# If a migration was applied that the rollback target doesn't include:
cd /opt/pug/app/backend
sudo -u pug /opt/pug/app/backend/.venv/bin/alembic downgrade <previous-revision>

# Rebuild and restart
cd /opt/pug/app/frontend && sudo -u pug npm run build
sudo systemctl restart pug-backend pug-frontend
```

### Add a new admin user

```bash
sudo -u pug /opt/pug/app/backend/.venv/bin/python -m app.scripts.seed_users
# Then log in once via /admin/login or /hr/login and rotate the password.
```

For one-off accounts outside the seed list, use the admin UI under
`/admin/system/users` (super-admin only).

---

## 11 · Troubleshooting

| Symptom                                                              | Cause / fix                                                                                                                       |
|----------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| `502 Bad Gateway` from Nginx                                         | Backend or frontend service is down. `systemctl status pug-backend pug-frontend` then `journalctl -u <service> -n 100`.            |
| Backend logs `connection refused` to PostgreSQL                      | DB is stopped or `pg_hba.conf` rejects the role. `systemctl status postgresql` and verify the role + host line.                   |
| `psycopg2.errors.UndefinedTable`                                     | Migrations not applied. `cd backend && .venv/bin/alembic upgrade head`.                                                            |
| Frontend renders but every API call 404s                             | `NEXT_PUBLIC_API_BASE_URL` baked into the build is wrong. Edit `.env.production`, then `npm run build && systemctl restart pug-frontend`. |
| CV upload silently fails for files > 1 MB                            | Nginx default `client_max_body_size` is 1 MB. Confirm the production config sets `client_max_body_size 20m;` and reload.           |
| AI review is always "mock"                                           | `AI_ENABLED=false` or one of the four `AZURE_OPENAI_*` vars is empty. Set all four, restart backend.                              |
| `OperationalError: SSL connection has been closed unexpectedly`      | Long-running idle connection killed by Cloudflare. Set `proxy_read_timeout 600s;` on the relevant Nginx location.                  |
| `next: command not found` in systemd unit                            | `node` not on the service `PATH`. Verify the unit's `Environment=PATH=...` line includes `/usr/bin`.                              |
| Browser shows mixed-content warnings                                 | A page rendered an `http://...` asset. Confirm `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_SITE_URL` both use `https://`.          |
| `Permission denied` writing to `/var/www/pug/uploads/`               | `pug` user doesn't own the dir. `sudo chown -R pug:pug /var/www/pug`.                                                              |
| Public AI assistant returns "AI is currently disabled"               | `AI_ENABLED=true` controls HR review; the public assistant uses the **AI Settings** admin page's `public_enabled` flag. Toggle it in `/admin/ai-settings`. |
| Backup script reports `pg_dump: server version mismatch`             | `pg_dump` from a different major version than the running cluster. Install `postgresql-client-14` to match.                       |

### Quick health snapshot

```bash
echo '--- services ---' && \
  systemctl is-active pug-backend pug-frontend nginx postgresql
echo '--- api ---' && \
  curl -fsS https://www.parisunitedgroup.com/api/v1/health
echo '--- site ---' && \
  curl -fsSI https://www.parisunitedgroup.com/ | head -1
echo '--- disk ---' && \
  df -h /
echo '--- uploads ---' && \
  du -sh /var/www/pug/uploads
echo '--- last backup ---' && \
  ls -lh /var/backups/pug | tail -3
```

---

## 12 · Final pre-launch checklist

- [ ] All 5 seeded users have had their passwords rotated.
- [ ] `SECRET_KEY` is unique to production (not the value from
      `.env.example`).
- [ ] Postgres password is unique, long, and stored in your team's
      password manager.
- [ ] `CORS_ORIGINS` lists only the production domain(s) — no
      `localhost`.
- [ ] HTTPS works on both `parisunitedgroup.com` and
      `www.parisunitedgroup.com`.
- [ ] Cloudflare SSL mode is **Full (strict)**.
- [ ] Daily backup cron job has run at least once and produced a
      readable `.sql.gz` file.
- [ ] You've performed at least one restore drill on a staging box.
- [ ] Admin and HR portals are reachable and login works.
- [ ] A CV upload through the public Apply Now form completes and the
      file appears under `/var/www/pug/uploads/cv/`.
- [ ] Public AI assistant is toggled correctly for go-live (you may
      want it disabled at launch and enabled in a follow-up).
- [ ] Search Console + Cloudflare Analytics added to the SEO admin
      page so traffic is tracked.

When every box is ticked, the deployment is production-ready.
