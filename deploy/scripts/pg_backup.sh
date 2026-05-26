#!/usr/bin/env bash
# ============================================================
#  Paris United Group — daily PostgreSQL backup
#
#  Cron entry (root):
#    30 2 * * * /usr/local/bin/pugweb-pg-backup >> /var/log/pugweb/backup.log 2>&1
#
#  Reads the DB credentials from the backend .env so there's one
#  source of truth and no copy-paste drift.
# ============================================================
set -euo pipefail

ENV_FILE=/home/parisgroup/PugWebSite/backend/.env
BACKUP_DIR=/var/backups/pug
RETENTION_DAYS=14

# Optional S3 destination — fill in to enable offsite backup.
# Requires `aws` CLI configured (IAM role on EC2 is the cleanest way).
S3_BUCKET=""                 # e.g. s3://pug-prod-backups
S3_PREFIX="postgres"

# ---------------------------------------------------------------
# Pull values from the backend .env without sourcing it (the file
# contains shell-unfriendly characters in some passwords).
# ---------------------------------------------------------------
read_env() {
    local key="$1"
    grep -E "^${key}=" "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '"' | tr -d "'"
}

PGUSER=$(read_env POSTGRES_USER)
PGPASSWORD=$(read_env POSTGRES_PASSWORD)
PGHOST=$(read_env POSTGRES_HOST)
PGPORT=$(read_env POSTGRES_PORT)
PGDB=$(read_env POSTGRES_DB)

export PGPASSWORD

mkdir -p "$BACKUP_DIR"

DATE=$(date -u +%F)
OUT="${BACKUP_DIR}/${PGDB}-${DATE}.sql.gz"

echo "[$(date -u +%FT%TZ)] starting backup → ${OUT}"

# --format=plain compresses well and is human-inspectable. Switch to
# --format=custom if you want parallel restore via pg_restore -j.
pg_dump \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --no-owner \
    --no-privileges \
    --clean --if-exists \
    "$PGDB" \
  | gzip --best > "$OUT"

SIZE=$(du -h "$OUT" | cut -f1)
echo "[$(date -u +%FT%TZ)] wrote ${OUT} (${SIZE})"

# ---------------------------------------------------------------
# Retention — keep the last $RETENTION_DAYS dumps locally.
# ---------------------------------------------------------------
find "$BACKUP_DIR" -maxdepth 1 -name "${PGDB}-*.sql.gz" -mtime "+${RETENTION_DAYS}" -print -delete

# ---------------------------------------------------------------
# Optional: push to S3.
# Uncomment + set S3_BUCKET above to enable.
# ---------------------------------------------------------------
# if [[ -n "$S3_BUCKET" ]]; then
#     aws s3 cp "$OUT" "${S3_BUCKET}/${S3_PREFIX}/$(basename "$OUT")" \
#         --storage-class STANDARD_IA \
#         --only-show-errors
#     echo "[$(date -u +%FT%TZ)] uploaded to ${S3_BUCKET}/${S3_PREFIX}/"
# fi

echo "[$(date -u +%FT%TZ)] backup complete"
