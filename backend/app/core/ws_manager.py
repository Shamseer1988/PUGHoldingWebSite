"""WebSocket connection manager (Phase C-2) + cross-worker fan-out (C-2b).

In-process registry of browser WebSocket connections, plus a Redis pub/sub
bridge so a broadcast from ANY gunicorn worker reaches every operator console
— not just the sockets that happen to live on the worker that emitted the
event.

How the pieces fit:

* Each worker holds its own :class:`WebSocketManager` (the ``_rooms``
  registry of live sockets on that process).
* :meth:`WebSocketManager.broadcast` delivers to this worker's local sockets
  AND publishes the event to a Redis channel, tagged with a per-process
  :data:`_ORIGIN` id.
* Every worker runs :func:`run_pubsub_listener` (started from the FastAPI
  lifespan). It consumes the channel and delivers messages that originated on
  *other* workers to its own local sockets. A message tagged with this
  worker's own ``_ORIGIN`` is skipped — the emitting worker already delivered
  it locally, so this avoids a double-send.

Everything is fire-and-forget and fail-soft: a Redis outage degrades to
single-worker delivery (local sockets still get the event) and never raises
into the request path. Disabled entirely via ``WS_PUBSUB_ENABLED=false`` so
the test suite (and single-worker dev) stays purely in-process — mirrors the
``SCHEDULER_ENABLED`` switch.

Connection bookkeeping is keyed by ``(scope, user_id)``:

* ``scope`` is the auth scope from the JWT (``hr`` for the HR console,
  ``website`` for the admin console).
* ``user_id`` is carried so a future per-user channel can target "just the
  candidate's hiring manager"; today every broadcast is scope-wide.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logging_config import get_logger


logger = get_logger(__name__)

# Single channel every worker publishes to / subscribes on.
_PUBSUB_CHANNEL = "pug:ws:broadcast"

# Per-process id so a worker can ignore the echo of its own publishes.
_ORIGIN = uuid.uuid4().hex


def pubsub_enabled() -> bool:
    """Cross-worker fan-out toggle.

    On by default; set ``WS_PUBSUB_ENABLED=false`` to keep delivery purely
    in-process (the test suite does this in ``conftest``). Mirrors the
    ``SCHEDULER_ENABLED`` env switch.
    """
    return os.getenv("WS_PUBSUB_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


class WebSocketManager:
    """Tracks live connections grouped by auth scope.

    Methods are coroutine-safe via a single ``asyncio.Lock``. Sending is
    fire-and-forget — a slow / disconnected client never blocks a broadcast
    for the rest of the room, and failed sends quietly drop the offending
    socket from the room.
    """

    def __init__(self) -> None:
        # ``scope`` → set of (user_id, websocket) tuples. A set of tuples
        # keeps reconnects cheap (re-add is idempotent) and lets one user
        # open the same dashboard in two tabs without confusion.
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

    async def _deliver_local(self, scope: str, message: str) -> int:
        """Send a pre-serialised wire message to every socket of ``scope`` on
        THIS worker. Prunes dead sockets. Never raises. Returns the number of
        sockets the message reached."""
        # Snapshot the room under the lock so the iteration below doesn't
        # fight with concurrent connect/disconnect calls.
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
                    "WS send failed", scope=scope, user_id=user_id
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

    async def broadcast(
        self,
        *,
        scope: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        """Deliver an event to every socket in ``scope`` on this worker, and
        (best-effort) publish it so the other workers deliver to theirs too.

        Returns the number of LOCAL sockets the event reached — the contract
        callers/tests already rely on. Cross-worker delivery happens
        asynchronously via :func:`run_pubsub_listener` on each worker; the
        wire format is a single JSON object ``{"type": ..., "data": ...}``
        that the frontend ``useHrNotifications`` hook routes on ``type``.
        """
        message = json.dumps(
            {"type": event_type, "data": payload},
            default=str,
        )
        sent = await self._deliver_local(scope, message)
        await _publish(scope=scope, event_type=event_type, payload=payload)
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
    """Drop the singleton so the next ``get_ws_manager`` call rebuilds an
    empty manager. Production code never calls this."""
    global _manager
    _manager = None


# ---------------------------------------------------------------------------
# Cross-worker fan-out (Redis pub/sub)
# ---------------------------------------------------------------------------


async def _publish(
    *, scope: str, event_type: str, payload: dict[str, Any]
) -> None:
    """Publish an event onto the cross-worker channel. Best-effort: a Redis
    outage just means the other workers miss this one event (local delivery
    already happened on the emitting worker). Never raises."""
    if not pubsub_enabled():
        return
    try:
        from app.core.redis_client import get_redis_client

        envelope = json.dumps(
            {
                "origin": _ORIGIN,
                "scope": scope,
                "type": event_type,
                "data": payload,
            },
            default=str,
        )
        await get_redis_client().publish(_PUBSUB_CHANNEL, envelope)
    except Exception:  # noqa: BLE001 — fan-out must never break a write
        logger.exception("WS cross-worker publish failed", scope=scope)


async def _handle_pubsub_message(raw: str) -> int:
    """Deliver one channel message to this worker's local sockets, unless it
    originated here (already delivered locally by ``broadcast``). Returns the
    number of local sockets reached. Exposed for unit-testing the de-dupe +
    delivery logic without standing up Redis."""
    try:
        envelope = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("WS pubsub: undecodable message dropped")
        return 0
    if not isinstance(envelope, dict):
        return 0
    if envelope.get("origin") == _ORIGIN:
        return 0  # our own echo — already delivered locally
    scope = envelope.get("scope")
    if not scope:
        return 0
    message = json.dumps(
        {"type": envelope.get("type"), "data": envelope.get("data")},
        default=str,
    )
    return await get_ws_manager()._deliver_local(scope, message)


async def run_pubsub_listener() -> None:
    """Long-lived per-worker consumer of the cross-worker channel.

    Started from the FastAPI lifespan and cancelled on shutdown. Reconnects
    with capped exponential backoff on Redis errors. Returns immediately when
    fan-out is disabled, so the lifespan can call it unconditionally."""
    if not pubsub_enabled():
        return

    from app.core.redis_client import get_redis_client

    backoff = 1.0
    while True:
        pubsub = None
        try:
            pubsub = get_redis_client().pubsub()
            await pubsub.subscribe(_PUBSUB_CHANNEL)
            logger.info(
                "WS cross-worker listener subscribed",
                channel=_PUBSUB_CHANNEL,
                origin=_ORIGIN,
            )
            backoff = 1.0
            async for message in pubsub.listen():
                if not message or message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8", "replace")
                if isinstance(data, str):
                    await _handle_pubsub_message(data)
        except asyncio.CancelledError:
            logger.info("WS cross-worker listener stopping")
            raise
        except Exception:  # noqa: BLE001 — keep the worker's bridge alive
            logger.exception(
                "WS cross-worker listener error; reconnecting", backoff=backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.aclose()
                except Exception:  # noqa: BLE001 — best-effort cleanup
                    pass


__all__ = [
    "WebSocketManager",
    "get_ws_manager",
    "pubsub_enabled",
    "run_pubsub_listener",
]
