# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Backend container — Phase A-9
# ---------------------------------------------------------------------------
# Two-stage build:
#
#   builder — installs Python dependencies into a per-user prefix
#             (~/.local). Carries the compilers + headers that some
#             wheels need to build from source.
#   runner  — copies the resulting site-packages tree out of builder
#             and the application source. No compilers, no toolchain;
#             final image stays under 200 MB.
#
# The default CMD runs Alembic migrations then boots uvicorn on a
# single worker. docker-compose overrides the command in dev to add
# --reload + bind-mount the source tree.
# ---------------------------------------------------------------------------

# ----- Builder ------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build deps. Most of our wheels are precompiled for 3.11 linux/amd64
# (Pillow, psycopg2-binary, PyMuPDF, cryptography, …), but a fresh
# build from source still needs a basic compiler chain.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --user -r /tmp/requirements.txt


# ----- Runner -------------------------------------------------------
FROM python:3.11-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:${PATH}" \
    APP_ENV=production

WORKDIR /app

# Runtime packages:
#
#   libpq5              — psycopg2-binary's runtime (always required).
#   postgresql-client-17 — pg_dump / pg_restore for the Admin → Database
#                         Backup feature. Pulled from Debian's own
#                         repo — ``python:3.11-slim`` is on Debian
#                         trixie (13), which ships PostgreSQL 17 as
#                         the default and packages
#                         ``postgresql-client-17`` directly. No PGDG
#                         third-party repo needed.
#
#                         Major-version compat rule for pg_dump is
#                         "client >= server" and the compose stack
#                         uses ``postgres:17-alpine``, so v17 client
#                         matches exactly. If a future base image
#                         rebases onto an older Debian (e.g. bookworm
#                         ships client 15), this line will fail loudly
#                         with "package not found" — at which point
#                         add the PGDG repo back, scoped to the active
#                         codename via ``. /etc/os-release``.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        postgresql-client-17 \
    && rm -rf /var/lib/apt/lists/*

# Copy the per-user Python install from builder.
COPY --from=builder /root/.local /root/.local

# Application source. The root .dockerignore keeps __pycache__,
# tests and the local .env out of the image.
COPY backend/ /app/

EXPOSE 8000

# Production default: run any pending migrations, then boot uvicorn.
# docker-compose overrides this in development to add --reload.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
