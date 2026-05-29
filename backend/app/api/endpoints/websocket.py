"""WebSocket endpoints (Phase C-2).

Operator consoles open a single long-lived WebSocket per session so
the backend can push events (new candidate application, contact
submission, etc.) without the browser polling.

Auth: the bearer JWT lives in ``localStorage`` per scope (see
``frontend/lib/auth.ts``); the browser's WebSocket constructor can't
attach an ``Authorization`` header, so the token rides in the
``?token=`` query string instead. We validate it the same way the
HTTP routes do — same secret, same algorithm, same scope check.

Currently exposes ``/ws/hr`` (HR ATS console). Adding ``/ws/admin``
later is a one-liner — same pattern, different required scope.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError

from app.auth.security import TOKEN_TYPE_ACCESS, decode_token
from app.core.logging_config import get_logger
from app.core.ws_manager import get_ws_manager
from app.models.auth import SCOPE_HR


logger = get_logger(__name__)

router = APIRouter()


WS_SCOPE_HR = SCOPE_HR


async def _authenticate(
    websocket: WebSocket, token: str | None, required_scope: str
) -> int | None:
    """Validate the query-string token; close the socket on failure.

    Returns the subject ``user_id`` on success, ``None`` after
    closing with ``1008 (policy violation)`` on any auth problem.
    The caller bails out when ``None`` is returned.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    try:
        payload = decode_token(token)
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    scopes = payload.get("scopes") or []
    if required_scope not in scopes:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    raw_sub = payload.get("sub")
    try:
        return int(raw_sub) if raw_sub is not None else None
    except (TypeError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None


@router.websocket("/ws/hr")
async def hr_notifications(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """HR-console event stream.

    Wire format is a single JSON object per message ``{"type": ...,
    "data": {...}}``. The first message after connect is always
    ``{"type": "system.hello", "data": {"scope": "hr"}}`` so the
    client can confirm the upgrade succeeded; everything after is a
    real event. Inbound text frames are accepted but ignored (room
    for future ``ping`` / ``ack`` traffic without breaking the
    protocol).
    """
    await websocket.accept()
    user_id = await _authenticate(websocket, token, WS_SCOPE_HR)
    if user_id is None:
        return

    manager = get_ws_manager()
    await manager.connect(scope=WS_SCOPE_HR, user_id=user_id, websocket=websocket)
    try:
        await websocket.send_json(
            {"type": "system.hello", "data": {"scope": WS_SCOPE_HR}}
        )
        while True:
            # Keep the connection alive. We don't care about the
            # contents — the receive_text() coroutine returns when
            # the client disconnects, which is what triggers cleanup
            # in the ``finally`` below.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 — never let the worker die
        logger.exception("WS handler crashed", user_id=user_id)
    finally:
        await manager.disconnect(
            scope=WS_SCOPE_HR, user_id=user_id, websocket=websocket
        )
