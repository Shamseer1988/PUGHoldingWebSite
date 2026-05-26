"""HTTP cache headers for public GET endpoints.

Adds ``Cache-Control`` to successful GET responses under
``/api/v1/public/*``.

Two distinct headers depending on the endpoint:

  * **CMS reads** (site-settings, leadership, companies, hero-slides,
    navigation, news, pages, site-pages, media, trusted-brands,
    featured-companies, homepage sections, …) ship
    ``Cache-Control: no-store, no-cache, must-revalidate, max-age=0``
    so neither Cloudflare nor Next.js's fetch layer ever caches a
    response. The cost is a few extra origin hits; the win is that
    an intermittent / partial backend response can no longer be
    cached and replayed for 60 s, which is what produced the
    "first refresh ok, second refresh fields disappear" flicker on
    the homepage / footer / leadership section.

  * **Static-ish surfaces** that don't move with admin edits
    (currently only the SEO ``robots.txt`` / ``sitemap.xml``
    endpoints if/when they're surfaced under /public/) still get a
    cache-friendly default. None are currently in this group; the
    code is ready for it.

Design choices that keep this conservative:

- Only attaches to **GET** requests. POSTs / PATCHes / DELETEs and the
  RFC-compliant unsafe methods are never cached.
- Only attaches to paths under ``/api/v1/public/``. The admin /
  HR / auth surfaces are excluded — they're personal and authed.
- Only attaches when the upstream did not already set
  ``Cache-Control`` (so a future endpoint can opt out by setting its
  own header).
- Skips ``ai-assistant/ask`` even on GET (defensive — it's a POST
  today but if a search variant lands later we don't want personal
  queries cached).
- Skips any non-2xx response (4xx / 5xx should never be edge-cached).

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


# Path prefixes whose responses move with admin edits — these MUST
# render fresh on every request so the user never sees a 60s-stale
# snapshot of CMS content (the homepage/footer/leadership flicker
# bug). The match is by prefix so ``/public/companies/{slug}``,
# ``/public/site-pages/{key}``, etc. are all covered.
NO_CACHE_PATH_PREFIXES: tuple[str, ...] = (
    "/api/v1/public/site-settings",
    "/api/v1/public/site-pages",
    "/api/v1/public/leadership",
    "/api/v1/public/homepage",
    "/api/v1/public/companies",
    "/api/v1/public/featured-companies",
    "/api/v1/public/hero-slides",
    "/api/v1/public/trusted-brands",
    "/api/v1/public/navigation",
    "/api/v1/public/news",
    "/api/v1/public/pages",
    "/api/v1/public/media",
    "/api/v1/public/jobs",
)


# Headers for CMS / homepage reads — bypass every cache layer.
NO_CACHE_HEADER = "no-store, no-cache, must-revalidate, max-age=0"

# Headers for endpoints that DO benefit from edge caching.
# (Not currently used — kept for future static endpoints.)
DEFAULT_CACHE_CONTROL = (
    "public, max-age=0, s-maxage=60, stale-while-revalidate=3600"
)


def _enabled() -> bool:
    return os.getenv("PUBLIC_CACHE_HEADERS_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
    }


def _is_no_cache_path(path: str) -> bool:
    """True when this CMS-ish endpoint must skip every cache."""
    return any(path.startswith(p) for p in NO_CACHE_PATH_PREFIXES)


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

        if _is_no_cache_path(path):
            # CMS reads — never cache. Add Pragma + Expires for the
            # old HTTP/1.0 clients and the few proxies that still
            # respect them (defense in depth).
            response.headers["Cache-Control"] = NO_CACHE_HEADER
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        else:
            response.headers["Cache-Control"] = DEFAULT_CACHE_CONTROL

        # Hint to downstream caches that the response varies by Origin
        # (CORS) but not by the Authorization header (public).
        response.headers.setdefault("Vary", "Origin, Accept-Encoding")
        return response
