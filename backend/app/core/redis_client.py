"""Async Redis client + FastAPI dependency (Phase B-2).

Singleton ``redis.asyncio.Redis`` lazily built on first use, shared
across the rate limiter, the public-CMS cache, and any future
consumer (Phase B-3 ARQ queue talks to the same Redis). One client
per process; closed cleanly from the FastAPI lifespan shutdown hook.

Tests swap the singleton for a ``fakeredis.aioredis.FakeRedis``
instance via the ``fake_redis`` autouse fixture in conftest so the
suite runs without a real broker.
"""
from __future__ import annotations

from typing import AsyncGenerator, Optional

from redis import asyncio as aioredis

from app.core.config import get_settings
from app.core.logging_config import get_logger


logger = get_logger(__name__)


_client: Optional[aioredis.Redis] = None


def _build_client() -> aioredis.Redis:
    """Construct a fresh client from ``settings.redis_url``.

    Separate from ``get_redis_client`` so the test conftest can
    monkey-patch this to return a fake. ``decode_responses=True``
    so callers get strings back from ``GET`` / ``HGET`` instead of
    raw bytes — the rate limiter and cache both want strings.
    """
    settings = get_settings()
    client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    logger.info("Redis client constructed", url=settings.redis_url)
    return client


def get_redis_client() -> aioredis.Redis:
    """Return (and lazily build) the process-wide Redis client.

    Synchronous because ``redis.asyncio.from_url`` doesn't open a
    socket until the first awaited command — building the wrapper
    object is free. Callers awaiting commands on the result handle
    the actual I/O.
    """
    global _client
    if _client is None:
        _client = _build_client()
    return _client


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency yielding the shared Redis client.

    Same lifecycle pattern as ``get_db`` / ``get_async_db``: yield,
    let the framework run the route, return. The client is shared
    across the process so there's no per-request setup/teardown.
    """
    yield get_redis_client()


async def close_redis() -> None:
    """Tear the singleton down (called from the FastAPI lifespan)."""
    global _client
    if _client is None:
        return
    try:
        await _client.aclose()
    except Exception:  # noqa: BLE001 — best-effort cleanup
        logger.exception("Redis client close failed")
    finally:
        _client = None


def _reset_client_for_tests() -> None:
    """Drop the singleton without awaiting close. The test conftest
    calls this between tests so each test sees the fresh fakeredis
    fixture it set up. Production code never needs this."""
    global _client
    _client = None


__all__ = [
    "close_redis",
    "get_redis",
    "get_redis_client",
]
