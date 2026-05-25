"""HTTP cache headers for public GET endpoints.

Adds ``Cache-Control`` to successful GET responses under
``/api/v1/public/*`` so Cloudflare (and any other downstream cache)
can serve repeat visits from the edge. Massive win for the public
site, where the same site-settings / navigation / company-list / job
list / hero-slide payloads are fetched on every page render.

Design choices that keep this conservative:

- Only attaches to **GET** requests. POSTs / PATCHes / DELETEs and the
  RFC-compliant unsafe methods are never cached.
- Only attaches to paths under ``/api/v1/public/``. The admin /
  HR / auth surfaces are excluded — they're personal and authed.
- Only attaches when the upstream did not already set
  ``Cache-Control`` (so a future endpoint can opt out by setting its
  own header).
- Skips ``ai-assistant/ask`` even on GET (defensive — it's a POST today
  but if a search variant lands later we don't want personal queries
  cached).
- Skips any non-2xx response (4xx / 5xx should never be edge-cached).

TTL: ``s-maxage=60`` (shared cache 1 min) + ``stale-while-revalidate=3600``
(visitors get the stale copy while the edge refetches in the
background — best UX). Browsers get ``max-age=0`` so the user always
sees the latest data after a hard refresh.

Toggle off via ``PUBLIC_CACHE_HEADERS_ENABLED=false`` in the env.
"""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


PUBLIC_PATH_PREFIX = "/api/v1/public/"

# Endpoints under /public/* that must NEVER be cached, even on GET.
# Keep the list tight — adding entries here is a deliberate choice.
CACHE_BLOCKLIST: frozenset = frozenset(
    {
        # No public GET on the AI assistant today, but reserve the path
        # so a future read-shape can't accidentally inherit caching.
        "/api/v1/public/ai-assistant/ask",
    }
)


# Default TTL — tuned so an admin edit propagates within ~60s while
# repeat visitors hit the edge cache.
DEFAULT_CACHE_CONTROL = (
    "public, max-age=0, s-maxage=60, stale-while-revalidate=3600"
)


def _enabled() -> bool:
    return os.getenv("PUBLIC_CACHE_HEADERS_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
    }


class PublicCacheHeadersMiddleware(BaseHTTPMiddleware):
    """Attach Cache-Control to safe public GET responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if not _enabled():
            return response
        if request.method != "GET":
            return response
        path = request.url.path
        if not path.startswith(PUBLIC_PATH_PREFIX):
            return response
        if path in CACHE_BLOCKLIST:
            return response
        if response.status_code < 200 or response.status_code >= 300:
            return response
        # Don't override an upstream Cache-Control if it set one.
        existing = response.headers.get("cache-control")
        if existing:
            return response
        response.headers["Cache-Control"] = DEFAULT_CACHE_CONTROL
        # Hint to downstream caches that the response varies by Origin
        # (CORS) but not by the Authorization header (public).
        response.headers.setdefault("Vary", "Origin, Accept-Encoding")
        return response
