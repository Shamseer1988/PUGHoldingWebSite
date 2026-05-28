"""Redis read-through cache for public CMS endpoints (Phase B-2).

Two pieces:

* :func:`cache_response` — decorator for FastAPI route functions
  that JSON-serialises the return value, parks it in Redis under a
  fixed key with a TTL, and returns the cached value on the next
  call until it expires. Works on both sync and async endpoints.

* :func:`clear_cache_prefix` — async helper called from admin write
  endpoints (via ``BackgroundTasks``) to invalidate every key under
  a prefix after a successful CMS edit. So an admin saving the
  Companies list invalidates ``public:companies*``, and the next
  visitor request rebuilds the cache instead of seeing the stale
  copy for up to 5 minutes.

Cache failures (Redis unreachable, serialisation error) never break
the endpoint — they fall through to a fresh call and a logged
warning. The visitor experience degrades to "uncached" rather than
"500".
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import json
import typing
from typing import Any, Awaitable, Callable, TypeVar

from fastapi.encoders import jsonable_encoder

from app.core.logging_config import get_logger
from app.core.redis_client import get_redis_client


logger = get_logger(__name__)


T = TypeVar("T")


def cache_response(
    key: str,
    ttl_seconds: int,
    *,
    vary_by: tuple[str, ...] = (),
) -> Callable[[Callable[..., Any]], Callable[..., Awaitable[Any]]]:
    """Wrap a FastAPI route so its return value is cached in Redis.

    Parameters
    ----------
    key
        Base Redis key the response is parked under. Use a stable
        namespace per endpoint (``"public:companies"`` etc.) — the
        prefix matters for :func:`clear_cache_prefix`.
    ttl_seconds
        How long Redis keeps the cached value. After this the next
        request rebuilds the cache.
    vary_by
        Names of route parameters whose values should be appended
        to the cache key so each distinct combination caches
        separately. E.g. ``vary_by=("category",)`` makes
        ``GET /companies`` and ``GET /companies?category=retail``
        use different keys. Leave empty for endpoints with no
        relevant query parameters (``/site-settings``).

    The wrapper is always ``async`` so FastAPI's signature
    introspection (and dependency injection) still works on the
    wrapped route, regardless of whether the underlying function is
    sync or async. ``functools.wraps`` preserves the inner
    signature so ``Depends(...)`` parameters keep getting injected
    correctly.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
        is_async = asyncio.iscoroutinefunction(func)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            redis = get_redis_client()

            # Build the actual cache key by appending the vary-by
            # parameter values. ``None`` is preserved so a missing
            # query param hashes distinctly from an empty one.
            if vary_by:
                suffix = ":".join(
                    f"{name}={kwargs.get(name)!r}" for name in vary_by
                )
                cache_key = f"{key}:{suffix}"
            else:
                cache_key = key

            # ----- Read attempt -----
            try:
                cached = await redis.get(cache_key)
            except Exception as exc:  # noqa: BLE001 — degrade, never 500
                logger.warning(
                    "cache_response: Redis GET failed — bypassing cache",
                    key=cache_key,
                    error=str(exc),
                )
                cached = None
            if cached is not None:
                try:
                    return json.loads(cached)
                except (TypeError, ValueError) as exc:
                    logger.warning(
                        "cache_response: cached payload is not valid JSON — "
                        "treating as a miss",
                        key=cache_key,
                        error=str(exc),
                    )

            # ----- Cache miss → call the underlying route -----
            if is_async:
                result = await func(*args, **kwargs)
            else:
                # Run the sync handler on a worker thread so the
                # event loop stays responsive. The existing public
                # endpoints all spend most of their time inside
                # SQLAlchemy / requests-blocking work; offloading
                # them keeps the rest of the loop interactive.
                result = await asyncio.to_thread(func, *args, **kwargs)

            # ----- Cache write (best-effort) -----
            try:
                payload = json.dumps(jsonable_encoder(result))
                await redis.set(cache_key, payload, ex=ttl_seconds)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "cache_response: Redis SET failed — returning fresh result",
                    key=cache_key,
                    error=str(exc),
                )
            return result

        # FastAPI introspects ``wrapper`` via ``inspect.signature``,
        # which resolves forward-reference annotations (``Optional``,
        # ``List[…]``) against the function's ``__globals__``.
        # ``functools.wraps`` copies the annotations onto ``wrapper``
        # but ``wrapper.__globals__`` belongs to *this* module — and
        # this module doesn't import ``Optional`` etc. from the
        # endpoint file's namespace. Pre-resolve the hints against
        # the inner function's namespace and pin them on
        # ``wrapper.__signature__`` so FastAPI sees concrete types.
        try:
            hints = typing.get_type_hints(func, include_extras=True)
            sig = inspect.signature(func)
            wrapper.__signature__ = sig.replace(
                parameters=[
                    p.replace(annotation=hints.get(name, p.annotation))
                    for name, p in sig.parameters.items()
                ],
                return_annotation=hints.get(
                    "return", sig.return_annotation
                ),
            )
        except Exception as exc:  # noqa: BLE001
            # Best-effort. If a hint can't be resolved (e.g. a
            # ForwardRef into a module that's mid-import) FastAPI
            # gets the un-resolved signature and may raise its own,
            # more helpful, diagnostic.
            logger.debug(
                "cache_response: could not resolve hints",
                func=func.__name__,
                error=str(exc),
            )

        return wrapper

    return decorator


async def clear_cache_prefix(prefix: str) -> int:
    """Delete every Redis key matching ``{prefix}*``. Returns the count.

    Called from admin write endpoints via ``BackgroundTasks.add_task``
    so the response returns immediately and the invalidation happens
    after the client has its 200. Failures are logged but never
    raised — a stale-for-a-few-minutes cache is far better than a
    failed write.
    """
    if not prefix:
        return 0
    redis = get_redis_client()
    deleted = 0
    try:
        # ``scan_iter`` is async-aware and chunks under the hood, so
        # this is safe even when the prefix matches thousands of keys.
        async for raw_key in redis.scan_iter(match=f"{prefix}*"):
            await redis.delete(raw_key)
            deleted += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "clear_cache_prefix failed mid-scan",
            prefix=prefix,
            deleted_so_far=deleted,
            error=str(exc),
        )
    if deleted:
        logger.info(
            "Cache prefix invalidated", prefix=prefix, keys=deleted
        )
    return deleted


__all__ = ["cache_response", "clear_cache_prefix"]
