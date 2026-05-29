"""FastAPI dependency for the ARQ connection pool (Phase B-3).

The pool itself is opened from the FastAPI lifespan and parked on
``app.state.arq_pool``. This module exposes the small dependency
endpoints use to access it. Kept in its own module so the
``contact_inbound`` poller, the HR notification dispatcher and
other services don't have to import the FastAPI app to enqueue a
job in some future Phase.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from fastapi import Request


if TYPE_CHECKING:
    # ArqRedis is the connection-pool class; avoid the import at
    # module load so envs without arq installed (test runners
    # mocking the pool) don't pay the import cost.
    from arq.connections import ArqRedis


def get_arq_pool(request: Request) -> Optional["ArqRedis"]:
    """Return the process-wide ARQ pool, or ``None`` when the
    feature flag is off or the lifespan failed to open it.

    Callers must handle the ``None`` case — that's how the
    feature-flag fallback lands at the call site: when the pool is
    missing the endpoint runs its work inline instead of enqueuing.
    """
    return getattr(request.app.state, "arq_pool", None)


__all__ = ["get_arq_pool"]
