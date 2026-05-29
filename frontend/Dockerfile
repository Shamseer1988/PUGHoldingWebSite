# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Frontend container — Phase A-9
# ---------------------------------------------------------------------------
# Three named build targets:
#
#   deps    — installs the full dependency tree (incl. devDependencies)
#             once, so both ``dev`` and ``builder`` reuse the layer.
#   dev     — what docker-compose builds for local development.
#             Boots ``next dev`` against bind-mounted source.
#   runner  — production runtime. Copies the prebuilt ``.next`` tree
#             out of the ``builder`` stage and runs ``next start``.
#
# Build a specific target with ``docker build --target dev`` /
# ``--target runner`` (Compose's ``target:`` field does this for us).
# ---------------------------------------------------------------------------

# ----- Stage: deps -------------------------------------------------
FROM node:20-alpine AS deps

WORKDIR /app

# Copy the manifest pair first so the ``npm ci`` layer caches well —
# changing app source doesn't bust this layer.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci


# ----- Stage: dev --------------------------------------------------
FROM deps AS dev

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# docker-compose mounts the host's ./frontend over /app so the
# COPY here is intentionally minimal — it just ensures the image
# is bootable on its own (``docker run`` without compose).
COPY frontend/ /app/

EXPOSE 3000
CMD ["npm", "run", "dev"]


# ----- Stage: builder ----------------------------------------------
FROM deps AS builder

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

# ``NEXT_PUBLIC_*`` env vars are baked into the JS bundle (and the
# CSP header in next.config.mjs) at ``npm run build`` time, not at
# runtime. The root .dockerignore correctly excludes .env files for
# safety, so we wire these in via Docker build args instead — pass
# them through docker-compose.prod.yml's ``build.args`` block.
#
# Missing values fall back to the dev default in next.config.mjs
# (``http://localhost:8000/api/v1``), which would break admin login
# on a public domain because the browser tries to fetch
# ``http://localhost:8000/...`` from the user's own machine.
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_SITE_URL
ARG NEXT_PUBLIC_SENTRY_DSN
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN

COPY frontend/ /app/
RUN npm run build


# ----- Stage: runner -----------------------------------------------
FROM node:20-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Production runtime needs only the build output + a runtime node
# tree. We could shrink further with the Next.js standalone output
# mode, but that requires a config flag we don't currently set.
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.mjs ./next.config.mjs

EXPOSE 3000
CMD ["npm", "start"]
