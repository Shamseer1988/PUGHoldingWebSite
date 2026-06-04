"""Universal HR realtime "bump" middleware (recruitment overhaul).

The HR console refetches *everything* on a data-sync pulse — query
cardinality is low, so a refetch-everything signal is cheap (see
``frontend/lib/hr/data-sync``). Rather than wire a WebSocket broadcast into
every one of the dozens of HR mutation endpoints (jobs alone has ~18), this
single layer fires one best-effort ``hr.data.changed`` pulse after any
successful HR write, so every open console refreshes live.

Endpoints that also emit a *specific* event (candidate / offer / interview,
which carry richer payloads and drive toasts) keep doing so — the extra
generic pulse is harmless, just an idempotent refetch.

Two guarantees, mirroring the per-endpoint broadcasts:
  * **Fire-and-forget** — scheduled as a background task so a slow/back-
    pressured socket can never delay the HTTP response.
  * **Best-effort** — fully guarded; a broadcast failure never affects the
    write that already committed.
"""
from __future__ import annotations

import asyncio
from typing import Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# HR data lives under /api/v1/hr/<resource>; the auth sub-tree (login /
# refresh / logout) is not a data change and must not pulse the consoles.
_HR_PREFIX = "/api/v1/hr/"
_HR_AUTH_PREFIX = "/api/v1/hr/auth"
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Strong refs to in-flight fire-and-forget tasks so the loop can't GC them
# mid-send (asyncio only holds weak references to bare tasks).
_pending: Set["asyncio.Task[int]"] = set()


def should_bump(method: str, path: str, status_code: int) -> bool:
    """True when a request is a successful, mutating write to an HR data
    route — the trigger for an ``hr.data.changed`` pulse.

    Pure function (no I/O) so the routing rule is unit-testable on its own.
    """
    if method.upper() not in _MUTATING_METHODS:
        return False
    if not 200 <= status_code < 300:
        return False
    if not path.startswith(_HR_PREFIX):
        return False
    if path == _HR_AUTH_PREFIX or path.startswith(_HR_AUTH_PREFIX + "/"):
        return False
    return True


class HrDataBumpMiddleware(BaseHTTPMiddleware):
    """Pulse every HR console after any successful HR write."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        try:
            if should_bump(request.method, request.url.path, response.status_code):
                # Deferred import keeps this core module free of an
                # import-time dependency on the services layer.
                from app.services.hr_realtime import broadcast_hr_data_changed

                task = asyncio.create_task(
                    broadcast_hr_data_changed(
                        path=request.url.path, method=request.method
                    )
                )
                _pending.add(task)
                task.add_done_callback(_pending.discard)
        except Exception:  # noqa: BLE001 - a bump must never break the response
            logger.exception("HR data bump scheduling failed")
        return response


__all__ = ["HrDataBumpMiddleware", "should_bump"]
