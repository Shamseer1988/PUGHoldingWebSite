"""Rate limiting for public write endpoints.

Phase 19 hardening. Adds per-IP throttles to the four endpoints anyone
on the Internet can call:

- ``POST /api/v1/contact``               (contact form)
- ``POST /api/v1/newsletter``            (newsletter subscribe)
- ``POST /api/v1/candidate-applications``(public Apply Now)
- ``POST /api/v1/ai-assistant/ask``      (public AI chat — also expensive)

Implementation is intentionally tiny: a sliding-window in-memory counter
exposed as a FastAPI dependency. We avoid slowapi's ``@limiter.limit``
decorator because its wrapper interacts badly with Pydantic's forward
references under ``from __future__ import annotations`` and that's the
style used throughout this codebase.

Storage is per-process. With a single gunicorn worker the limits are
exact; with N workers the effective ceiling is ``limit * N``. That's
acceptable for a small site behind Cloudflare — for a busy multi-worker
deployment, swap the ``_BUCKETS`` dict for a shared Redis backend.

Tests can disable rate limiting by setting ``RATE_LIMIT_ENABLED=false``
in the environment before the app is imported, or by calling
``reset_rate_limits()`` between requests.
"""
from __future__ import annotations

import os
import time
from collections import deque
from threading import Lock
from typing import Deque, Dict, Tuple

from fastapi import HTTPException, Request, status


# --------------------------------------------------------------------------- #
# Named limits — tune here, not at each route.                                #
#   (max_requests, window_seconds)                                            #
# --------------------------------------------------------------------------- #

# Cheap CMS write — generous enough that a legitimate user can correct
# a typo and resubmit but tight enough to discourage form-spam loops.
CONTACT_LIMIT: Tuple[int, int] = (5, 60)        # 5 / minute / IP
CONTACT_LIMIT_HOURLY: Tuple[int, int] = (30, 3600)

# Newsletter is idempotent (resubmit re-activates) — keep tighter so we
# don't fill the table with garbage email addresses.
NEWSLETTER_LIMIT: Tuple[int, int] = (3, 60)
NEWSLETTER_LIMIT_HOURLY: Tuple[int, int] = (20, 3600)

# Candidate apply: a real applicant submits once or twice; bots that
# brute-force file uploads get cut off quickly.
APPLY_LIMIT: Tuple[int, int] = (3, 60)
APPLY_LIMIT_HOURLY: Tuple[int, int] = (15, 3600)

# CV preview parse — the candidate may upload, tweak, re-upload, but
# we want to stop scrape-loops of the parser. Slightly more generous
# than the apply limit because a real user can iterate.
CV_PREVIEW_LIMIT: Tuple[int, int] = (5, 60)
CV_PREVIEW_LIMIT_HOURLY: Tuple[int, int] = (30, 3600)

# AI chat is the most expensive (Azure OpenAI tokens cost money). Give
# a real visitor enough headroom for a conversation, but stop loops.
AI_ASSISTANT_LIMIT: Tuple[int, int] = (10, 60)
AI_ASSISTANT_LIMIT_HOURLY: Tuple[int, int] = (60, 3600)


# --------------------------------------------------------------------------- #
# In-memory sliding-window store.                                             #
# --------------------------------------------------------------------------- #

# Keyed by (route_key, client_ip) → deque of unix-second timestamps.
_BUCKETS: Dict[Tuple[str, str], Deque[float]] = {}
_LOCK = Lock()


def _enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").lower() not in {"0", "false", "no"}


def _client_ip(request: Request) -> str:
    """Resolve the originating client IP.

    Behind Cloudflare + Nginx, ``request.client.host`` is the upstream
    proxy. The Nginx config in ``deploy/nginx/pug-holding.conf`` sets
    ``X-Forwarded-For``, so prefer the first IP from that header and
    fall back to the socket peer.
    """
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        first = fwd.split(",")[0].strip()
        if first:
            return first
    if request.client is None:
        return "unknown"
    return request.client.host or "unknown"


def _check(route_key: str, ip: str, max_requests: int, window: int, now: float) -> bool:
    """Return True if the request is within the limit, else False.

    Side effect: appends ``now`` to the bucket on success. Old entries
    outside the window are popped from the left.
    """
    bucket_key = (route_key, ip)
    with _LOCK:
        bucket = _BUCKETS.setdefault(bucket_key, deque())
        cutoff = now - window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_requests:
            return False
        bucket.append(now)
        return True


def _retry_after(route_key: str, ip: str, window: int, now: float) -> int:
    """How many seconds until the oldest entry in the window expires."""
    bucket = _BUCKETS.get((route_key, ip))
    if not bucket:
        return window
    return max(1, int(bucket[0] + window - now))


def _enforce(request: Request, route_key: str, *limits: Tuple[int, int]) -> None:
    """Raise HTTP 429 if any of the supplied (max, window) limits is exceeded."""
    if not _enabled():
        return
    ip = _client_ip(request)
    now = time.time()
    for max_requests, window in limits:
        sub_key = f"{route_key}:{window}"
        if not _check(sub_key, ip, max_requests, window, now):
            retry = _retry_after(sub_key, ip, window, now)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Too many requests. Please wait a moment and try again."
                ),
                headers={"Retry-After": str(retry)},
            )


# --------------------------------------------------------------------------- #
# Public dependencies — drop into ``Depends(...)`` on a route.                #
# --------------------------------------------------------------------------- #


def rate_limit_contact(request: Request) -> None:
    _enforce(request, "contact", CONTACT_LIMIT, CONTACT_LIMIT_HOURLY)


def rate_limit_newsletter(request: Request) -> None:
    _enforce(request, "newsletter", NEWSLETTER_LIMIT, NEWSLETTER_LIMIT_HOURLY)


def rate_limit_apply(request: Request) -> None:
    _enforce(request, "apply", APPLY_LIMIT, APPLY_LIMIT_HOURLY)


def rate_limit_cv_preview(request: Request) -> None:
    _enforce(request, "cv_preview", CV_PREVIEW_LIMIT, CV_PREVIEW_LIMIT_HOURLY)


def rate_limit_ai_assistant(request: Request) -> None:
    _enforce(request, "ai_assistant", AI_ASSISTANT_LIMIT, AI_ASSISTANT_LIMIT_HOURLY)


def reset_rate_limits() -> None:
    """Clear every bucket — useful between tests."""
    with _LOCK:
        _BUCKETS.clear()
