"""Request-ID correlator middleware (Phase A-4).

Adds an ``X-Request-ID`` header to every response and stashes the same
value on ``request.state.request_id`` so any service that runs inside
the request can include it in log lines, audit rows or error reports.

If the caller already supplied an ``X-Request-ID`` header (e.g. the
frontend forwarded one from Sentry's trace context, or an upstream
proxy stamped one), we honour it. Otherwise we generate a fresh
uuid4 hex string. The header makes it trivial to correlate a
specific user-visible error in the browser with the exact backend
log line that produced it.

The middleware sits at the OUTER edge of the stack — added after the
CORS middleware in :func:`app.main.create_app` so it wraps CORS and
fires for every request, including CORS preflight ``OPTIONS`` calls
that CORSMiddleware would otherwise short-circuit.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-ID"


def _is_valid_inbound_id(value: str) -> bool:
    """Defensive check on inbound IDs.

    Accept anything that's a sensible-length token (8-128 chars, no
    control characters). Without this, a hostile client could ship a
    log-poisoning payload — newlines, ANSI escapes, megabyte strings
    — that would then propagate into every log line for the request.
    """
    if not value or len(value) > 128 or len(value) < 8:
        return False
    return all(32 <= ord(ch) < 127 for ch in value)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Read or mint an ``X-Request-ID`` and expose it on the response."""

    async def dispatch(self, request: Request, call_next):
        inbound = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = (
            inbound.strip()
            if _is_valid_inbound_id(inbound.strip())
            else uuid.uuid4().hex
        )
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


__all__ = ["REQUEST_ID_HEADER", "RequestIDMiddleware"]
