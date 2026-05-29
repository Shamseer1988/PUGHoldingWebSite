# Docker deployment on AWS EC2

End-to-end runbook for deploying the PUG Holding website + HR ATS as a
production Docker Compose stack on a fresh Ubuntu EC2 host. Uses:

* `docker-compose.prod.yml` — Postgres + Redis + backend + frontend + Nginx, no
  source bind-mounts, no `--reload`, multi-worker gunicorn.
* Cloudflare Origin Certificate for TLS (free, 15-year validity, no renewal cron).
* EC2 Security Group as the firewall — Docker bind addresses do the rest.

For the *non-Docker* (systemd + host Nginx) variant — preserved because PUG
Accounts used it — see `deployment-guide.md`.

---

## 1 · Prerequisites

| What | Why |
|---|---|
| Ubuntu 22.04+ EC2 instance (t3.small or larger, 2+ GB RAM) | Runs Docker + 4 gunicorn workers + Next.js + Postgres + Redis comfortably |
| EC2 Security Group: inbound 22 (your IP), 80, 443 (anywhere); everything else **denied** | The compose stack only exposes 80/443 — never expose 5432 or 6379 |
| DNS A records for `parisunitedgroup.com` + `www.parisunitedgroup.com` pointing at the EC2 public IP | Required before issuing the Cloudflare Origin Cert |
| Cloudflare zone for `parisunitedgroup.com` in **Full (strict)** SSL mode | Origin Cert pinning + edge TLS terminate |
| Production R2 bucket + admin credentials (see `r2-setup.md`) | Optional but recommended — files survive box rebuilds |

---

## 2 · Install Docker on the EC2 host

```bash
ssh -i ParisUnitedKey.pem ubuntu@<ec2-public-ip>

# Official Docker install script — installs Docker Engine + Compose v2 plugin.
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu

# Re-evaluate group membership without logging out.
exec sg docker -c "bash"
docker --version            # Docker version 27.x or newer
docker compose version      # Docker Compose v2.x
```

---

## 3 · Generate the Cloudflare Origin Certificate

1. Cloudflare dashboard → your zone → **SSL/TLS** → **Origin Server** → **Create Certificate**
2. Private key type: **RSA (2048)** (or ECDSA if you prefer)
3. Hostnames: `parisunitedgroup.com`, `*.parisunitedgroup.com`
4. Certificate validity: **15 years**
5. Copy the displayed `Origin Certificate` and `Private Key` — they're only shown once.

You'll paste them into the EC2 host in step 5 below.

While you're in the Cloudflare dashboard, also set:

* SSL/TLS → Overview → **Full (strict)**
* SSL/TLS → Edge Certificates → **Always Use HTTPS** = On
* SSL/TLS → Edge Certificates → **Automatic HTTPS Rewrites** = On

---

## 4 · Clone the repo on the EC2 host

```bash
# /opt is a conventional home for application code on Ubuntu.
sudo mkdir -p /opt/pugwebsite
sudo chown ubuntu:ubuntu /opt/pugwebsite
cd /opt/pugwebsite

git clone https://github.com/Shamseer1988/PUGHoldingWebSite.git .
git checkout main
git log --oneline -1     # should show the latest merge commit on main
```

---

## 5 · Drop the Cloudflare Origin Cert into the host

```bash
sudo tee /opt/pugwebsite/deploy/docker/tls/origin.crt > /dev/null <<'EOF'
-----BEGIN CERTIFICATE-----
…paste the Certificate block from Cloudflare here…
-----END CERTIFICATE-----
EOF

sudo tee /opt/pugwebsite/deploy/docker/tls/origin.key > /dev/null <<'EOF'
-----BEGIN PRIVATE KEY-----
…paste the Private Key block from Cloudflare here…
-----END PRIVATE KEY-----
EOF

sudo chmod 644 /opt/pugwebsite/deploy/docker/tls/origin.crt
sudo chmod 600 /opt/pugwebsite/deploy/docker/tls/origin.key
sudo chown ubuntu:ubuntu /opt/pugwebsite/deploy/docker/tls/origin.*
```

---

## 6 · Set production env vars

### `backend/.env`

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Critical values:

```dotenv
APP_ENV=production
SECRET_KEY=<run: python3 -c "import secrets; print(secrets.token_urlsafe(64))">
PUBLIC_SITE_URL=https://parisunitedgroup.com
CORS_ALLOWED_ORIGINS=https://parisunitedgroup.com,https://www.parisunitedgroup.com

# All three must be present — the Postgres container reads them
# directly from ``backend/.env`` via the compose's ``env_file:`` block.
POSTGRES_USER=pug_user
POSTGRES_PASSWORD=<strong random>
POSTGRES_DB=pug_holding

# R2 (recommended)
R2_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<token id>
R2_SECRET_ACCESS_KEY=<token secret>
R2_BUCKET_NAME=pug-media
R2_PUBLIC_BASE_URL=https://pug-media.parisunitedgroup.com

# Sentry (recommended)
SENTRY_DSN_BACKEND=https://…@sentry.io/…

# Azure OpenAI (only if AI features used)
AZURE_OPENAI_ENDPOINT=https://<name>.openai.azure.com
AZURE_OPENAI_API_KEY=…
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
```

SMTP + IMAP settings are stored in the database via the admin UI — you don't
need to put them in `.env`.

### `frontend/.env.local`

```bash
cat > frontend/.env.local <<EOF
NEXT_PUBLIC_API_BASE_URL=https://parisunitedgroup.com/api/v1
NEXT_PUBLIC_SITE_URL=https://parisunitedgroup.com
NEXT_PUBLIC_SENTRY_DSN=
EOF
```

`NEXT_PUBLIC_API_BASE_URL` is baked into the build, so it must be set
**before** `docker compose up --build`. Changing it after means a rebuild.

---

## 7 · First boot

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f backend
```

Watch for:

```
INFO  [alembic.runtime.migration] Running upgrade … -> 20260529_0023, …
[gunicorn] Starting gunicorn 23.0.0
[gunicorn] Listening at: http://0.0.0.0:8000
```

Ctrl+C the log tail when both lines are present. Then verify all five services
are up:

```bash
docker compose -f docker-compose.prod.yml ps
# postgres   healthy
# redis      healthy
# backend    running
# frontend   running
# nginx      running
```

---

## 8 · Smoke test

```bash
# Local — from the EC2 box
curl -I http://localhost/healthz          # 200 OK
curl -ki https://localhost/               # 200 from Next.js, cert may be self-served if DNS not pointed yet

# Public — after DNS propagates (or via curl --resolve)
curl -I https://parisunitedgroup.com/                # 200
curl -I https://parisunitedgroup.com/api/v1/healthz  # 200
```

Open `https://parisunitedgroup.com` in a browser. Sign into admin at `/admin`.
Confirm SMTP, IMAP OAuth2 (M365), and R2 health in the admin configuration
pages.

---

## 9 · Optional — ARQ background worker

The HR digest job and other async tasks are opt-in (Phase B-3):

```bash
docker compose -f docker-compose.prod.yml --profile worker up -d worker
docker compose -f docker-compose.prod.yml logs -f worker
```

---

## 10 · Updating after a code push

```bash
ssh ubuntu@<ec2-public-ip>
cd /opt/pugwebsite

# Snapshot before pulling — backup the Postgres volume.
docker compose -f docker-compose.prod.yml exec postgres \
    pg_dump -U pug_user pug_holding | gzip > /home/ubuntu/pug-$(date +%F).sql.gz

git pull origin main

# --build picks up new requirements / package.json. Existing data
# volumes (postgres_data, uploads_data) survive the recreate.
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f --tail 50
```

---

## 11 · Common operational commands

```bash
# Tail the last hour of logs across all services.
docker compose -f docker-compose.prod.yml logs --since 1h

# Restart just one service (e.g. after editing nginx.conf).
docker compose -f docker-compose.prod.yml restart nginx

# Shell into the backend container.
docker compose -f docker-compose.prod.yml exec backend bash

# Run a one-off Alembic command.
docker compose -f docker-compose.prod.yml exec backend alembic current
docker compose -f docker-compose.prod.yml exec backend alembic history --verbose

# psql into the database.
docker compose -f docker-compose.prod.yml exec postgres \
    psql -U pug_user -d pug_holding

# Stop everything cleanly.
docker compose -f docker-compose.prod.yml down

# Stop AND delete persistent data — DESTRUCTIVE.
docker compose -f docker-compose.prod.yml down -v
```

---

## 12 · Troubleshooting matrix

| Symptom | Likely cause | Fix |
|---|---|---|
| `nginx` container fails to start with `cannot load certificate` | `deploy/docker/tls/origin.crt` or `.key` missing / unreadable | Re-paste from Cloudflare; check `ls -la deploy/docker/tls/` shows both files with `chmod 600` on the key |
| 502 Bad Gateway on every URL | Backend or frontend container crashed before nginx started | `docker compose logs backend frontend --tail 100` — usually an env var missing |
| `pydantic.ValidationError: SECRET_KEY` | `.env` not loaded or value is the dev placeholder | Confirm `backend/.env` exists in the same dir as `docker-compose.prod.yml` and `SECRET_KEY` is set to 32+ chars |
| `psycopg2.OperationalError: password authentication failed` | Postgres volume was created with a different `POSTGRES_PASSWORD` (e.g. from a previous run) | `docker compose down -v` to wipe the volume, then `up -d --build` to recreate with the new password — destructive, only safe before the DB has real data |
| Browser shows "ERR_TOO_MANY_REDIRECTS" | Cloudflare Edge Cert mode = Flexible (HTTP origin) but Nginx is also redirecting to HTTPS | Set Cloudflare SSL mode to **Full (strict)** |
| `Contact-inbox poll: fetched=0` despite incoming mail | UID watermark resumed mid-mailbox (rare) | Reset via `psql` → `UPDATE email_settings SET imap_last_seen_uid = NULL, imap_last_seen_uid_validity = NULL WHERE id = 1;` then next poll backfills via `UNSEEN` |
| IMAP poller silently skipping all mail | Cert mismatch on outbound R2 / Microsoft 365 endpoints | `docker compose exec backend python -c "import httpx; print(httpx.get('https://outlook.office365.com').status_code)"` — should print 302 |

---

## 13 · Tear-down

When the EC2 instance is being retired:

```bash
# 1. Final database backup off-box.
docker compose -f docker-compose.prod.yml exec postgres \
    pg_dump -U pug_user pug_holding | gzip > pug-final.sql.gz
scp ubuntu@<ec2>:/opt/pugwebsite/pug-final.sql.gz ./

# 2. Stop and remove containers + volumes.
docker compose -f docker-compose.prod.yml down -v

# 3. Remove the project directory.
sudo rm -rf /opt/pugwebsite

# 4. Terminate the EC2 instance from the AWS console.
```
