# Production Deployment Guide

This guide is the runbook for the **Paris United Group** corporate
website + HR ATS portal as it actually runs on the shared AWS EC2
host. The host already runs a separate **PUG Accounts** application
on `pugfinapp.parisunitedgroup.com`, so this guide is written to drop
the new stack alongside it without touching the existing config.

For local development setup, see [`setup-guide.md`](setup-guide.md).

Ready-to-copy config files referenced below live under
[`deploy/`](../deploy/) at the repo root.

---

## Critical: do not touch the PUG Accounts app

The following files belong to the existing PUG Accounts app and must
not be edited as part of this deployment:

```
/home/parisgroup/PugAccountsApp/
/etc/nginx/sites-available/pugaccounts
/etc/nginx/sites-enabled/pugaccounts
/etc/systemd/system/pugaccounts.service
```

PUG Accounts runs on `127.0.0.1:5000`. The new website backend
chooses `127.0.0.1:8000` and the new frontend `127.0.0.1:3000`
specifically so the two stacks coexist on the same box without
overlap.

---

## 1 · Architecture

```
                 ┌──────────────────────────────────────┐
   User browser ─┤   Cloudflare (DNS + Edge TLS)        │
                 └──────────────┬───────────────────────┘
                                │
              parisunitedgroup.com / www.            pugfinapp.parisunitedgroup.com
                                │                          │
                                ▼                          ▼
              ┌─────────────────────────────────────────────────────┐
              │                Ubuntu EC2 host                      │
              │                                                     │
              │   :80 / :443  Nginx (single nginx for both apps)    │
              │           │                                         │
              │           ├── parisunitedgroup.com   /        → :3000  Next.js │
              │           │                          /api/v1/  → :8000  FastAPI │
              │           │                                         │
              │           └── pugfinapp.parisunitedgroup.com → :5000 (existing) │
              │                                                     │
              │   :5432  PostgreSQL — pug_holding (loopback only)   │
              │                                                     │
              │   /var/www/pug/uploads/  CV + media                 │
              │                                                     │
              └─────────────────────────────────────────────────────┘
```

**Port map (after deployment).**

| Port  | Service                                  | Bind        | Reachable from           |
|-------|------------------------------------------|-------------|--------------------------|
| 80    | Nginx (HTTP)                             | `0.0.0.0`   | Public, redirects to 443 |
| 443   | Nginx (HTTPS)                            | `0.0.0.0`   | Public                   |
| 3000  | Next.js (`npm run start`)                | `127.0.0.1` | Localhost only           |
| 5000  | **PUG Accounts (existing, untouched)**   | `127.0.0.1` | Localhost only           |
| 8000  | FastAPI (gunicorn + uvicorn workers)     | `127.0.0.1` | Localhost only           |
| 5432  | PostgreSQL                               | `127.0.0.1` | Localhost only           |

**Final target paths.**

```
Project:    /home/parisgroup/PugWebSite
Backend:    /home/parisgroup/PugWebSite/backend
Frontend:   /home/parisgroup/PugWebSite/frontend
Uploads:    /var/www/pug/uploads
Logs:       /var/log/pugweb        (custom application logs)
Nginx site: /etc/nginx/sites-available/parisgroup
Backend service:  pugweb-backend.service
Frontend service: pugweb-frontend.service
```

---

## 2 · Login + verify the box

SSH in as the `ubuntu` user with the AWS key:

```bash
ssh -i ParisUnitedKey.pem ubuntu@<ec2-host>
```

Confirm the existing PUG Accounts app is healthy **before** changing
anything:

```bash
sudo systemctl status pugaccounts.service --no-pager
sudo ss -ltnp | grep -E ":5000|:80|:443"
ls -la /etc/nginx/sites-enabled
```

Expected:
- `pugaccounts.service` is **active (running)**.
- `127.0.0.1:5000` is listening.
- `nginx` is on `:80` (and `:443` if SSL is already set up).
- `/etc/nginx/sites-enabled` contains the `pugaccounts` symlink.

If any of these are broken, stop and investigate — do not proceed.

---

## 3 · Install required packages

```bash
sudo apt update
sudo apt upgrade -y

sudo apt install -y \
    build-essential git curl ca-certificates \
    python3.11 python3.11-venv python3.11-dev \
    libpq-dev \
    nginx \
    postgresql postgresql-contrib \
    ufw fail2ban \
    unattended-upgrades \
    openssl
```

Install Node.js 20 LTS via NodeSource:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

Verify:

```bash
python3.11 --version    # Python 3.11.x
node --version          # v20.x.x
npm --version
psql --version
nginx -v
```

### Firewall

Only do this if the box does not already have UFW configured (the
existing PUG Accounts host probably does — check first).

```bash
sudo ufw status                  # check first
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow "Nginx Full"
sudo ufw enable
```

---

## 4 · Prepare the project folder

```bash
sudo mkdir -p /home/parisgroup/PugWebSite
sudo chown -R parisgroup:parisgroup /home/parisgroup/PugWebSite

# Log directory for custom application logs (backup script, etc.)
sudo mkdir -p /var/log/pugweb

# Uploads directory — the backend writes CV files + admin media here.
sudo mkdir -p /var/www/pug/uploads
sudo chown -R parisgroup:parisgroup /var/log/pugweb /var/www/pug
```

---

## 5 · GitHub SSH for the `parisgroup` user

Become `parisgroup` and generate a deploy key dedicated to this repo:

```bash
sudo -iu parisgroup
mkdir -p ~/.ssh && chmod 700 ~/.ssh

ssh-keygen -t ed25519 -C "pug-website-ec2" -f ~/.ssh/github_pug_website
# Press Enter to accept the empty passphrase.
```

Tell the SSH client which key to use for `github.com`:

```bash
cat > ~/.ssh/config <<'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_pug_website
    IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config

ssh-keyscan github.com >> ~/.ssh/known_hosts
chmod 644 ~/.ssh/known_hosts
```

Copy the public key and register it as a **deploy key** on the GitHub
repo (Settings → Deploy keys → Add deploy key, title
`EC2 PUG Website`, **Allow write access: OFF**):

```bash
cat ~/.ssh/github_pug_website.pub
```

Confirm the key works:

```bash
ssh -T git@github.com
# Hi <user>! You've successfully authenticated, but GitHub does not provide shell access.
```

---

## 6 · Clone the repository

Still as `parisgroup`:

```bash
cd /home/parisgroup
git clone git@github.com:Shamseer1988/PUGHoldingWebSite.git PugWebSite
```

If `/home/parisgroup/PugWebSite` already exists (created in step 4),
do this instead:

```bash
cd /home/parisgroup/PugWebSite
git init
git remote add origin git@github.com:Shamseer1988/PUGHoldingWebSite.git
git fetch origin
git checkout main
git pull origin main
```

Sanity-check the layout:

```bash
cd /home/parisgroup/PugWebSite
ls -la
# expect: backend/, frontend/, deploy/, docs/, README.md, …

find . -maxdepth 2 -name package.json
find . -maxdepth 2 -name requirements.txt
find . -maxdepth 3 -name alembic.ini
```

---

## 7 · PostgreSQL

Exit back to the `ubuntu` user (`exit` once) so you have sudo.

```bash
sudo systemctl enable --now postgresql
sudo systemctl status postgresql --no-pager
```

Generate a strong password and **save it in your password manager**
before pasting it into psql:

```bash
openssl rand -base64 32
```

Create the database role + database:

```bash
sudo -u postgres psql
```

Inside `psql` — replace `PASTE_STRONG_PASSWORD_HERE`:

```sql
CREATE USER pug_user WITH PASSWORD 'PASTE_STRONG_PASSWORD_HERE';
CREATE DATABASE pug_holding OWNER pug_user;
GRANT ALL PRIVILEGES ON DATABASE pug_holding TO pug_user;
\c pug_holding
GRANT ALL ON SCHEMA public TO pug_user;
ALTER SCHEMA public OWNER TO pug_user;
\q
```

Confirm:

```bash
PGPASSWORD='PASTE_STRONG_PASSWORD_HERE' \
  psql -h 127.0.0.1 -U pug_user -d pug_holding -c '\dt'
```

### Hardening

PostgreSQL on this host is shared with PUG Accounts. Don't change the
listen address — it stays on `localhost`. Confirm the existing
`pg_hba.conf` already requires `scram-sha-256` for local + host
connections. If it doesn't (rare), update it carefully and reload:

```bash
sudo grep -E "^(local|host)" /etc/postgresql/14/main/pg_hba.conf
sudo systemctl reload postgresql
```

---

## 8 · Backend `.env`

Become `parisgroup`:

```bash
sudo -iu parisgroup
cd /home/parisgroup/PugWebSite/backend

# Generate the JWT secret — save the output for the SECRET_KEY below.
openssl rand -hex 32

nano .env
```

Paste the production template, then replace placeholders:

```ini
APP_ENV=production
APP_DEBUG=false
APP_HOST=127.0.0.1
APP_PORT=8000

SECRET_KEY=PASTE_GENERATED_SECRET_KEY_HERE
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
ALGORITHM=HS256

POSTGRES_USER=pug_user
POSTGRES_PASSWORD=PASTE_POSTGRES_PASSWORD_HERE
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=pug_holding

CORS_ORIGINS=https://www.parisunitedgroup.com,https://parisunitedgroup.com

UPLOAD_DIR=/var/www/pug/uploads
MAX_UPLOAD_SIZE_MB=20

# Leave AI_ENABLED=false until the Azure deployment is provisioned.
# The HR AI review falls back to mock mode automatically when keys
# are missing.
AI_ENABLED=false
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=2024-08-01-preview

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@parisunitedgroup.com
SMTP_USE_TLS=true
```

Lock the file:

```bash
chmod 600 .env
```

---

## 9 · Install backend + run migrations

```bash
cd /home/parisgroup/PugWebSite/backend

python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip wheel
.venv/bin/pip install -r requirements.txt

# Apply every migration on a fresh database (idempotent — safe to
# re-run on later deploys).
.venv/bin/alembic upgrade head

# Confirm the seed scripts exist before running.
ls -la app/scripts
.venv/bin/python -m app.scripts.seed_users
.venv/bin/python -m app.scripts.seed_cms
.venv/bin/python -m app.scripts.seed_hr
```

**Change every seeded user's password before going live** — the seed
script writes a documented default. Log into each portal once and
rotate.

Quick smoke test (one-off run from the venv):

```bash
.venv/bin/gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker -w 3 -b 127.0.0.1:8000
```

From another SSH session:

```bash
curl -s http://127.0.0.1:8000/api/v1/health
# {"status":"ok","database":"connected", ...}
```

Stop the manual run with `Ctrl+C` once you confirm the health check.

---

## 10 · Backend systemd service

Exit back to `ubuntu` (`exit`).

Copy [`deploy/systemd/pugweb-backend.service`](../deploy/systemd/pugweb-backend.service)
to `/etc/systemd/system/pugweb-backend.service`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pugweb-backend.service
sudo systemctl status pugweb-backend.service --no-pager

curl -s http://127.0.0.1:8000/api/v1/health
```

If the service is stuck:

```bash
sudo journalctl -u pugweb-backend.service -n 100 --no-pager
```

---

## 11 · Frontend

```bash
sudo -iu parisgroup
cd /home/parisgroup/PugWebSite/frontend
nano .env.production
```

```ini
# Server-side (SSR) calls — loopback is fastest.
API_BASE_URL=http://127.0.0.1:8000/api/v1

# Browser calls — must be the PUBLIC origin so the browser can
# reach it via Nginx + Cloudflare.
NEXT_PUBLIC_API_BASE_URL=https://www.parisunitedgroup.com/api/v1

NEXT_PUBLIC_SITE_URL=https://www.parisunitedgroup.com
NEXT_PUBLIC_SITE_NAME=Paris United Group Holding
```

Install + build:

```bash
npm ci
# If npm ci fails (no package-lock.json on a clean clone) — fall back to:
# npm install

npm run build
```

One-off smoke test:

```bash
npm run start -- -p 3000 -H 127.0.0.1
```

From another session:

```bash
curl -I http://127.0.0.1:3000
# HTTP/1.1 200 OK
```

`Ctrl+C` to stop the manual run.

---

## 12 · Frontend systemd service

Exit back to `ubuntu` (`exit`).

Copy [`deploy/systemd/pugweb-frontend.service`](../deploy/systemd/pugweb-frontend.service)
to `/etc/systemd/system/pugweb-frontend.service`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pugweb-frontend.service
sudo systemctl status pugweb-frontend.service --no-pager

curl -I http://127.0.0.1:3000
```

---

## 13 · Nginx reverse proxy

**Do not edit `/etc/nginx/sites-available/pugaccounts`** — the
existing PUG Accounts app stays isolated on
`pugfinapp.parisunitedgroup.com`.

Copy [`deploy/nginx/parisgroup.conf`](../deploy/nginx/parisgroup.conf)
to `/etc/nginx/sites-available/parisgroup`, then:

```bash
sudo ln -sf /etc/nginx/sites-available/parisgroup \
            /etc/nginx/sites-enabled/parisgroup

sudo nginx -t
sudo systemctl reload nginx
```

The config:

- Listens on **80** (HTTP) for `parisunitedgroup.com` and `www.…`.
- Proxies `/api/v1/` to FastAPI (`127.0.0.1:8000`).
- Proxies everything else to Next.js (`127.0.0.1:3000`).
- Serves `/api/v1/uploads/` directly from `/var/www/pug/uploads/`
  with `expires 7d` + `Cache-Control: public, immutable`.
- Sets `client_max_body_size 20m` so CV uploads aren't truncated.
- `proxy_buffering off` so streaming endpoints work.

HTTPS is added in step **15** after Cloudflare's Origin Cert is on
the server.

---

## 14 · Verify everything

```bash
echo '---- SERVICES ----'
sudo systemctl status pugweb-backend.service  --no-pager
sudo systemctl status pugweb-frontend.service --no-pager
sudo systemctl status pugaccounts.service     --no-pager

echo '---- PORTS ----'
sudo ss -ltnp | grep -E ':80|:443|:3000|:5000|:8000'

echo '---- NGINX ROUTING ----'
sudo nginx -T | grep -nE 'server_name|proxy_pass|parisunitedgroup|pugfinapp'

echo '---- BACKEND HEALTH ----'
curl -s http://127.0.0.1:8000/api/v1/health

echo '---- FRONTEND ----'
curl -I http://127.0.0.1:3000

echo '---- MAIN DOMAIN VIA NGINX ----'
curl -I -H 'Host: parisunitedgroup.com' http://127.0.0.1/

echo '---- ACCOUNTS APP STILL SEPARATE ----'
curl -I -H 'Host: pugfinapp.parisunitedgroup.com' http://127.0.0.1/login
```

Expected ports:

```
:80   nginx
127.0.0.1:3000  Next.js website
127.0.0.1:5000  PUG Accounts (existing — untouched)
127.0.0.1:8000  FastAPI website backend
```

Expected Nginx routing:

```
parisunitedgroup.com                  →  127.0.0.1:3000
parisunitedgroup.com/api/v1/          →  127.0.0.1:8000
pugfinapp.parisunitedgroup.com        →  127.0.0.1:5000   (existing)
```

---

## 15 · Cloudflare DNS + Full (strict) SSL

### DNS

In Cloudflare for the `parisunitedgroup.com` zone:

| Type | Name | Content              | Proxy   |
|------|------|----------------------|---------|
| A    | @    | <EC2 public IPv4>    | Proxied |
| A    | www  | <EC2 public IPv4>    | Proxied |

`pugfinapp` already has its own record from the existing deployment
— don't touch it.

### Origin Certificate (free, 15-year)

Cloudflare → **SSL/TLS → Origin Server → Create Certificate**:

```
Hostnames:
  parisunitedgroup.com
  *.parisunitedgroup.com
Validity: 15 years
```

Save the cert + key to the server:

```bash
sudo mkdir -p /etc/ssl/cloudflare
sudo nano /etc/ssl/cloudflare/origin.pem    # paste cert
sudo nano /etc/ssl/cloudflare/origin.key    # paste private key
sudo chmod 644 /etc/ssl/cloudflare/origin.pem
sudo chmod 600 /etc/ssl/cloudflare/origin.key
```

### Switch the Nginx site to HTTPS

Edit `/etc/nginx/sites-available/parisgroup` and replace the single
HTTP `server { … }` block with the **HTTP→HTTPS redirect** + **HTTPS
server** block at the bottom of
[`deploy/nginx/parisgroup.conf`](../deploy/nginx/parisgroup.conf).
The whole HTTPS config is included in the file as a commented
section — just uncomment after the origin cert is in place.

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Cloudflare → SSL/TLS → Edge Certificates

- **SSL/TLS mode:** Full (strict)
- **Always Use HTTPS:** On
- **Automatic HTTPS Rewrites:** On
- **Minimum TLS Version:** TLS 1.2

### Verify

From your laptop:

```bash
curl -sI https://www.parisunitedgroup.com/api/v1/health
# HTTP/2 200
```

---

## 16 · Backups

### Daily PostgreSQL dump

Install the cron job:

```bash
sudo cp /home/parisgroup/PugWebSite/deploy/scripts/pg_backup.sh \
        /usr/local/bin/pugweb-pg-backup
sudo chmod +x /usr/local/bin/pugweb-pg-backup
sudo install -d -o parisgroup -g parisgroup /var/backups/pug
```

Add to root's crontab (`sudo crontab -e`):

```cron
# Daily 02:30 UTC PostgreSQL dump + 14-day rotation
30 2 * * * /usr/local/bin/pugweb-pg-backup >> /var/log/pugweb/backup.log 2>&1
```

The script keeps the last 14 days locally. Uncomment the
`aws s3 cp` line and configure an EC2 IAM role with
`s3:PutObject` if you also want off-site copies.

### Restore drill

```bash
# Stop the API to prevent writes during restore.
sudo systemctl stop pugweb-backend

# Drop and recreate.
sudo -u postgres psql -c "DROP DATABASE pug_holding;"
sudo -u postgres psql -c "CREATE DATABASE pug_holding OWNER pug_user;"

gunzip -c /var/backups/pug/pug_holding-<DATE>.sql.gz \
  | sudo -u postgres psql pug_holding

sudo systemctl start pugweb-backend
```

### Uploads backup

Include `/var/www/pug/uploads/` in your file-system backup. Daily
rsync to a sibling host:

```bash
rsync -aH --delete /var/www/pug/uploads/ backup-host:/srv/pug-uploads/
```

---

## 17 · Logs

```bash
# Backend (FastAPI + gunicorn + uvicorn workers)
sudo journalctl -u pugweb-backend.service  -n 200 -f

# Frontend (Next.js)
sudo journalctl -u pugweb-frontend.service -n 200 -f

# Nginx
sudo tail -f /var/log/nginx/parisgroup-access.log
sudo tail -f /var/log/nginx/parisgroup-error.log

# PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-14-main.log

# Backup job (custom)
sudo tail -f /var/log/pugweb/backup.log
```

Install the logrotate config for the custom log directory:

```bash
sudo cp /home/parisgroup/PugWebSite/deploy/logrotate/pugweb \
        /etc/logrotate.d/pugweb
sudo logrotate -d /etc/logrotate.d/pugweb    # dry-run
```

---

## 18 · Future deployment updates

When new code lands on the branch you're deploying from:

```bash
sudo -iu parisgroup
cd /home/parisgroup/PugWebSite
git pull --ff-only origin main
```

Backend updates:

```bash
cd /home/parisgroup/PugWebSite/backend
.venv/bin/pip install -r requirements.txt    # only if requirements.txt changed
.venv/bin/alembic upgrade head                # safe to run every deploy — idempotent
```

Frontend rebuild:

```bash
cd /home/parisgroup/PugWebSite/frontend
npm ci                                        # only if package-lock.json changed
npm run build
```

Restart services:

```bash
exit
sudo systemctl restart pugweb-backend.service
sudo systemctl restart pugweb-frontend.service
sudo systemctl reload  nginx
```

Smoke test:

```bash
curl -s  http://127.0.0.1:8000/api/v1/health
curl -I  http://127.0.0.1:3000
curl -I  -H 'Host: parisunitedgroup.com' http://127.0.0.1/
curl -I  -H 'Host: pugfinapp.parisunitedgroup.com' http://127.0.0.1/login
```

### Rollback

```bash
sudo -iu parisgroup
cd /home/parisgroup/PugWebSite
git log --oneline -5         # find the last-known-good SHA
git checkout <good-sha>

# If a migration was applied that the rollback target doesn't include:
cd backend
.venv/bin/alembic downgrade <previous-revision>

cd ../frontend && npm run build
exit
sudo systemctl restart pugweb-backend.service pugweb-frontend.service
```

---

## 18.5 · Image + asset optimisation (post-launch perf pass)

If pages feel slow loading images or videos in production, walk
through these in order. The first three together cut transfer size
70-90 % for typical photographic uploads.

### A · Make sure the server-side WebP pipeline ran

Every image uploaded through `/admin/media` now gets resized to
three WebP variants (thumb 480 w, medium 960 w, large 1920 w) plus
JPEG fallbacks at the same widths — see
`backend/app/services/image_optimization.py`. The public
`ResponsiveImage` component prefers WebP and lets the browser pick
the smallest variant that matches its viewport via `srcset` /
`sizes`.

**Existing uploads** from before the pipeline existed have
`variants = NULL` and serve the full-resolution original. Backfill
them once after deploying:

```bash
sudo -iu parisgroup
cd /home/parisgroup/PugWebSite/backend
.venv/bin/python -m app.scripts.backfill_image_variants
```

The script is idempotent — re-running skips rows that already have
variants. Output prints `id=N ✓` per processed row and a summary at
the end (`processed / skipped / missing / errors`).

After deploying a new release, new uploads optimise automatically;
no manual step is needed.

### B · Enable Cloudflare image compression

You're already behind Cloudflare for DNS + TLS. Two dashboard
toggles give meaningful additional savings on top of the WebP
pipeline:

1. **Cloudflare → Speed → Optimization → Image Optimization → Polish: Lossy.**
   30-50 % size reduction on JPEG/PNG/WebP at the edge, fully
   transparent to the app.
2. **Speed → Optimization → Mirage.** Adapts image delivery to
   slow connections / small viewports. Free plans include it.
3. While in the same screen, confirm **Brotli** is on (it is by
   default — Brotli compresses HTML/CSS/JS so JSON API responses
   also shrink).
4. **Speed → Optimization → Early Hints: On.** Lets Cloudflare
   send `Link: rel=preload` hints from cache before the origin
   replies, shaving 100-300 ms off the LCP.

No code change required for any of these.

### C · Verify uploads aren't going through FastAPI

The Nginx site config in `deploy/nginx/parisgroup.conf` serves
`/api/v1/uploads/` straight off disk with `expires 7d` and
`Cache-Control: public, immutable`. Confirm:

```bash
curl -sI https://www.parisunitedgroup.com/api/v1/uploads/cms/<file>.jpg \
  | grep -iE 'cache-control|expires|server'
# expected: cache-control: public, immutable
#           expires: <some Date 7 days out>
```

If you see `cache-control: no-store` or no `expires` header, the
request is hitting FastAPI's `StaticFiles` mount instead of the
Nginx alias — re-check the `location /api/v1/uploads/ { alias … }`
block in `/etc/nginx/sites-available/parisgroup`.

### D · Admin upload hygiene

The optimization pipeline saves bytes downstream but **the original
file is still kept** (it's the source of truth for the lightbox and
admin downloads). A 12 MB original still costs 12 MB of disk + S3
backup space.

- Resize photos to ≤ 2400 px on the long edge before uploading.
- Export at JPEG quality 80-85 — visually identical to 100, half
  the bytes.
- Never upload PNGs of photographs (3-4× the size of an equivalent
  JPEG). Use PNG only for screenshots / logos with sharp edges /
  transparency.

### E · Videos

The frontend already uses `preload="metadata"` on video tiles so
visitors don't download the full file until they press play.
Production tweaks beyond that:

- Keep tile videos under **5 MB** and ≤ 720 p. Anything heavier
  belongs on YouTube/Vimeo with an `<iframe>` embed.
- Encode H.264 (`.mp4`) — every browser plays it without a poly­
  fill, and you save against more-modern but less-supported codecs.
- Always set the **poster** field on hero / company videos so the
  tile shows a static frame instead of a black box while the file
  fetches.

### F · Quick perf checklist after each deploy

```bash
curl -sIH 'Host: www.parisunitedgroup.com' http://127.0.0.1/api/v1/public/site-settings | grep -i cache-control
# expected: cache-control: public, max-age=0, s-maxage=60, stale-while-revalidate=3600
```

If the edge cache header is missing, the middleware in
`app/core/cache_headers.py` isn't running — make sure
`PUBLIC_CACHE_HEADERS_ENABLED` is not set to `false` in
`.env`.

---

## 19 · Troubleshooting

| Symptom                                                              | Cause / fix                                                                                                                              |
|----------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `502 Bad Gateway` from Nginx                                         | Backend or frontend service is down. `systemctl status pugweb-backend pugweb-frontend` then `journalctl -u <service> -n 100`.            |
| Backend logs `connection refused` to PostgreSQL                      | DB is stopped or `pg_hba.conf` rejects the role. `systemctl status postgresql` and verify the role + host line.                          |
| `psycopg2.errors.UndefinedTable`                                     | Migrations not applied. `cd backend && .venv/bin/alembic upgrade head`.                                                                  |
| Frontend renders but every API call 404s                             | `NEXT_PUBLIC_API_BASE_URL` baked into the build is wrong. Edit `.env.production`, then `npm run build && systemctl restart pugweb-frontend`. |
| CV upload silently fails for files > 1 MB                            | Nginx default `client_max_body_size` is 1 MB. Confirm the production config sets `client_max_body_size 20m;` and reload.                 |
| AI review is always "mock"                                           | `AI_ENABLED=false` or one of the four `AZURE_OPENAI_*` vars is empty. Set all four, restart backend.                                     |
| `OperationalError: SSL connection has been closed unexpectedly`      | Long-running idle connection killed by Cloudflare. Set `proxy_read_timeout 600s;` on the relevant Nginx location.                        |
| `next: command not found` in systemd unit                            | `node` not on the service `PATH`. Verify the unit's `Environment=PATH=…` line includes `/usr/bin`.                                       |
| Browser shows mixed-content warnings                                 | A page rendered an `http://…` asset. Confirm `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_SITE_URL` both use `https://`.                   |
| `Permission denied` writing to `/var/www/pug/uploads/`               | `parisgroup` user doesn't own the dir. `sudo chown -R parisgroup:parisgroup /var/www/pug`.                                               |
| Public AI assistant returns "AI is currently disabled"               | `AI_ENABLED=true` controls HR review; the public assistant uses the **AI Settings** admin page's `public_enabled` flag.                  |
| Backup script reports `pg_dump: server version mismatch`             | `pg_dump` from a different major version than the running cluster. Install `postgresql-client-14` to match.                              |
| Accounts app at `pugfinapp` 502s after this deploy                   | You edited the wrong Nginx file. Restore `/etc/nginx/sites-available/pugaccounts` from `git`/backup and reload nginx.                    |

### Quick health snapshot

```bash
echo '--- services ---' && \
  systemctl is-active pugweb-backend pugweb-frontend nginx postgresql pugaccounts
echo '--- api ---' && \
  curl -fsS https://www.parisunitedgroup.com/api/v1/health
echo '--- site ---' && \
  curl -fsSI https://www.parisunitedgroup.com/ | head -1
echo '--- accounts (isolation) ---' && \
  curl -fsSI -H 'Host: pugfinapp.parisunitedgroup.com' http://127.0.0.1/login | head -1
echo '--- disk ---' && \
  df -h /
echo '--- uploads ---' && \
  du -sh /var/www/pug/uploads
echo '--- last backup ---' && \
  ls -lh /var/backups/pug | tail -3
```

---

## 20 · Final pre-launch checklist

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
- [ ] `pugfinapp.parisunitedgroup.com` still serves the PUG Accounts
      app — visit `/login` and confirm.
- [ ] Daily backup cron job has run at least once and produced a
      readable `.sql.gz` file under `/var/backups/pug/`.
- [ ] You've performed at least one restore drill on a staging box.
- [ ] Admin and HR portals are reachable and login works.
- [ ] A CV upload through the public Apply Now form completes and the
      file appears under `/var/www/pug/uploads/cv/`.
- [ ] Public AI assistant is toggled correctly for go-live (you may
      want it disabled at launch and enabled in a follow-up).
- [ ] Search Console + Cloudflare Analytics added to the SEO admin
      page so traffic is tracked.

When every box is ticked, the deployment is production-ready.
