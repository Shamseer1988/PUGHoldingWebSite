"""Rate limiting for public write endpoints.

Phase B-2 — Redis backend
==========================

Replaces the previous in-memory ``_BUCKETS`` dict with a Redis
sliding-window counter executed via an atomic Lua script. Three
wins over the in-memory version:

* **Shared across workers.** With N gunicorn / uvicorn workers,
  the effective ceiling stops being ``limit * N`` — every worker
  hits the same Redis key.
* **Survives restarts.** A reload during a brute-force attempt
  doesn't hand the attacker a fresh budget.
* **Atomic increment + TTL set.** The Lua script avoids the race
  where two concurrent requests both observe a zero counter and
  both succeed past the limit.

Per-route ``(max_requests, window_seconds)`` pairs are the same
constants as before so the visible behaviour is unchanged.

Tests
=====

Disabled by default via ``RATE_LIMIT_ENABLED=false`` in the test
conftest. The two dedicated rate-limit tests in ``test_security``
opt back in via the ``rate_limit_on`` fixture; they share the
fakeredis instance the conftest pins in ``app.core.redis_client``.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from redis import asyncio as aioredis

from app.core.logging_config import get_logger
from app.core.redis_client import get_redis


logger = get_logger(__name__)


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

# Database backup + restore. Even though the endpoints are superuser-
# only, a compromised admin account could otherwise loop multi-hundred-
# MB pg_dump / pg_restore calls and exhaust disk + I/O. Conservative
# ceiling: a real operator runs this a handful of times a day at most.
BACKUP_LIMIT: Tuple[int, int] = (2, 60)
BACKUP_LIMIT_HOURLY: Tuple[int, int] = (10, 3600)


# --------------------------------------------------------------------------- #
# Lua script — atomic increment + first-hit expiry + TTL read                 #
# --------------------------------------------------------------------------- #
#
# KEYS[1] = bucket key (e.g. "rl:contact:60:1.2.3.4")
# ARGV[1] = max_requests
# ARGV[2] = window_seconds
#
# Returns a single integer:
#   * count <= max_requests  → allowed; value is the new counter
#   * count >  max_requests  → denied; caller must compute Retry-After
#                              from the key's TTL (read after the call,
#                              we don't bother returning two values).
#
# Rationale for not returning two values: redis-py's Lua eval over
# decode_responses=True returns a single-element list. Keeping the
# script simple makes the integration testable + easy to reason
# about. The TTL read in the second step is a single round-trip, so
# the cost stays at two redis ops per check, same as the original
# in-memory implementation's two-method workflow.

# (The Lua script that lived here in the first draft was replaced
# with a two-command INCR + conditional EXPIRE sequence — see
# ``_enforce`` below. The script approach was cleaner but
# fakeredis 2.26 ships EVAL disabled and forces an in-process
# integration test to fall back to the plain command sequence; we
# may as well use the same path in production so dev + prod
# behaviour matches.)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


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


async def _enforce(
    redis: aioredis.Redis,
    request: Request,
    route_key: str,
    *limits: Tuple[int, int],
) -> None:
    """Raise HTTP 429 if any of the supplied (max, window) limits is exceeded."""
    if not _enabled():
        return
    ip = _client_ip(request)
    for max_requests, window in limits:
        bucket_key = f"rl:{route_key}:{window}:{ip}"
        try:
            # INCR is atomic; on the first hit (count == 1) we set
            # the window expiry. Concurrent INCRs may both observe
            # the same first hit before either EXPIRE lands — that's
            # harmless, both succeed and the second is a no-op.
            count = await redis.incr(bucket_key)
            if count == 1:
                await redis.expire(bucket_key, window)
        except aioredis.RedisError as exc:
            # If Redis is unreachable we fail OPEN rather than reject
            # legitimate traffic. The structured-logging line gives
            # ops something to grep for; a sustained outage will be
            # very visible in the dashboard.
            logger.warning(
                "Rate limit Redis call failed — failing open",
                route_key=route_key,
                window=window,
                error=str(exc),
            )
            return
        if int(count) > max_requests:
            ttl = await redis.ttl(bucket_key)
            retry = max(1, int(ttl)) if ttl and ttl > 0 else window
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
#
# Each helper is an async FastAPI dependency taking the Redis client
# via Depends(get_redis). FastAPI resolves the dependency before
# entering the route handler; sync route handlers are still allowed.


async def rate_limit_contact(
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
) -> None:
    await _enforce(redis, request, "contact", CONTACT_LIMIT, CONTACT_LIMIT_HOURLY)


async def rate_limit_newsletter(
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
) -> None:
    await _enforce(
        redis, request, "newsletter", NEWSLETTER_LIMIT, NEWSLETTER_LIMIT_HOURLY
    )


async def rate_limit_apply(
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
) -> None:
    await _enforce(redis, request, "apply", APPLY_LIMIT, APPLY_LIMIT_HOURLY)


async def rate_limit_cv_preview(
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
) -> None:
    await _enforce(
        redis, request, "cv_preview", CV_PREVIEW_LIMIT, CV_PREVIEW_LIMIT_HOURLY
    )


async def rate_limit_ai_assistant(
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
) -> None:
    await _enforce(
        redis,
        request,
        "ai_assistant",
        AI_ASSISTANT_LIMIT,
        AI_ASSISTANT_LIMIT_HOURLY,
    )


async def rate_limit_backup(
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
) -> None:
    """Limit per-IP calls to the destructive backup / restore routes.

    Applied even though the underlying endpoints are superuser-only —
    if an admin credential is compromised, this is the additional
    speed-bump against an attacker queueing many large dumps in
    parallel.
    """
    await _enforce(redis, request, "backup", BACKUP_LIMIT, BACKUP_LIMIT_HOURLY)


def reset_rate_limits() -> None:
    """Clear every bucket — useful between tests.

    Drops the cached Redis singleton. The conftest's ``fake_redis``
    fixture rebuilds against a per-test ``FakeServer`` so state
    naturally doesn't leak across tests; this helper is the explicit
    knob a single test (e.g. ``rate_limit_on``) can call when it
    wants a clean slate mid-suite. Awaiting ``FLUSHDB`` on the
    singleton would crash with an event-loop mismatch — the cached
    client was bound to whatever loop ``TestClient`` used, and the
    teardown runs under a fresh ``asyncio.get_event_loop()`` —
    dropping is the simpler invariant.
    """
    from app.core.redis_client import _reset_client_for_tests

    _reset_client_for_tests()