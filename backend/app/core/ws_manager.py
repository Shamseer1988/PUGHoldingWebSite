"""WebSocket connection manager (Phase C-2).

In-memory pub/sub for browser WebSocket connections. Lets the API
push real-time events to operator consoles (admin / HR) the moment
something happens in the backend instead of waiting for them to
refresh.

Lives in-process per worker. A multi-worker deployment behind
gunicorn would naturally see "an event landed on the worker that
opened the connection — the other workers don't know" semantics;
that's fine for the initial slice because each browser keeps a
single WebSocket open and that connection lives in one worker.
Phase C-2b (if we need cross-worker fan-out) would put a Redis
pub/sub between workers; the API surface here stays the same.

Connection bookkeeping is keyed by ``(scope, user_id)``:

* ``scope`` is the auth scope from the JWT (``hr`` for the HR
  console, ``website`` for the admin console). A user-specific
  channel lets us target an event to "just the candidate's hiring
  manager" later; a scope-wide broadcast covers the "every HR
  operator should see this" cases the initial slice exercises.

* ``user_id`` is ``None`` when the broadcast is scope-wide. The
  per-user keying is the obvious extension point.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logging_config import get_logger


logger = get_logger(__name__)


class WebSocketManager:
    """Tracks live connections grouped by auth scope.

    Methods are coroutine-safe via a single ``asyncio.Lock``.
    Sending is fire-and-forget — a slow / disconnected client never
    blocks a broadcast for the rest of the room. Failed sends
    quietly drop the offending socket from the room.
    """

    def __init__(self) -> None:
        # ``scope`` → set of (user_id, websocket) tuples. Using a set
        # of tuples instead of a dict-of-lists keeps reconnects
        # cheap (re-add is idempotent) and lets a single user open
        # the same dashboard in two tabs without confusion.
        self._rooms: dict[str, set[tuple[int, WebSocket]]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self, *, scope: str, user_id: int, websocket: WebSocket
    ) -> None:
        async with self._lock:
            room = self._rooms.setdefault(scope, set())
            room.add((user_id, websocket))
        logger.info(
            "WS connect",
            scope=scope,
            user_id=user_id,
            room_size=len(self._rooms.get(scope, set())),
        )

    async def disconnect(
        self, *, scope: str, user_id: int, websocket: WebSocket
    ) -> None:
        async with self._lock:
            room = self._rooms.get(scope)
            if room is None:
                return
            room.discard((user_id, websocket))
            if not room:
                self._rooms.pop(scope, None)
        logger.info(
            "WS disconnect",
            scope=scope,
            user_id=user_id,
            room_size=len(self._rooms.get(scope, set())),
        )

    async def broadcast(
        self,
        *,
        scope: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        """Send an event to every socket in ``scope``.

        Returns the number of sockets the event was sent to (after
        dropping any that errored). The wire format is a single JSON
        object — ``{"type": "...", "data": {...}}`` — which the
        frontend ``useHrNotifications`` hook routes on ``type``.
        """
        message = json.dumps(
            {"type": event_type, "data": payload},
            default=str,
        )

        # Snapshot the room under the lock so the iteration below
        # doesn't fight with concurrent connect/disconnect calls.
        async with self._lock:
            targets = list(self._rooms.get(scope, set()))

        dead: list[tuple[int, WebSocket]] = []
        sent = 0
        for user_id, ws in targets:
            if ws.client_state != WebSocketState.CONNECTED:
                dead.append((user_id, ws))
                continue
            try:
                await ws.send_text(message)
                sent += 1
            except Exception:  # noqa: BLE001 — broadcasts must not raise
                logger.exception(
                    "WS broadcast send failed",
                    scope=scope,
                    user_id=user_id,
                )
                dead.append((user_id, ws))

        if dead:
            async with self._lock:
                room = self._rooms.get(scope)
                if room is not None:
                    for entry in dead:
                        room.discard(entry)
                    if not room:
                        self._rooms.pop(scope, None)

        return sent

    def room_size(self, scope: str) -> int:
        """Cheap, sync, no-lock count — used by tests + ops dashboards."""
        return len(self._rooms.get(scope, set()))


_manager: Optional[WebSocketManager] = None


def get_ws_manager() -> WebSocketManager:
    """Process-wide singleton. Built lazily so tests can reset it."""
    global _manager
    if _manager is None:
        _manager = WebSocketManager()
    return _manager


def _reset_manager_for_tests() -> None:
    """Drop the singleton so the next ``get_ws_manager`` call rebuilds
    an empty manager. Production code never calls this."""
    global _manager
    _manager = None


__all__ = [
    "WebSocketManager",
    "get_ws_manager",
]
