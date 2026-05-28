"""Phase C-2 — WebSocket real-time notifications.

Covers three contracts:

* ``WebSocketManager`` correctly tracks connect / disconnect and
  drops sockets that error out during a broadcast.
* The ``/ws/hr`` endpoint rejects missing / invalid / wrong-scope
  tokens with a 1008 close before any handler logic runs, and
  accepts a valid HR token + delivers the hello message.
* The ``broadcast_candidate_application_new`` helper is the one the
  public apply + HR upload endpoints call — wiring it up should
  push a JSON event to every live HR socket.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from starlette.websockets import WebSocketDisconnect

from app.auth.security import create_access_token
from app.core.ws_manager import (
    WebSocketManager,
    _reset_manager_for_tests,
    get_ws_manager,
)
from app.models.auth import SCOPE_HR, SCOPE_WEBSITE
from app.services.hr_realtime import (
    EVENT_CANDIDATE_APPLICATION_NEW,
    broadcast_candidate_application_new,
)


@pytest.fixture(autouse=True)
def _reset_ws_manager():
    """Drop the process-wide singleton between tests so per-test
    connect/disconnect state doesn't leak."""
    _reset_manager_for_tests()
    yield
    _reset_manager_for_tests()


# ---------------------------------------------------------------------------
# WebSocketManager unit tests
# ---------------------------------------------------------------------------


class _FakeConnectedWebSocket:
    """Minimal stand-in for ``starlette.websockets.WebSocket``.

    Mirrors the ``client_state`` + ``send_text`` interface the
    manager touches; records every payload it received so the test
    can assert on it.
    """

    def __init__(self) -> None:
        from starlette.websockets import WebSocketState

        self.client_state = WebSocketState.CONNECTED
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)


class _DeadWebSocket(_FakeConnectedWebSocket):
    """Same shape, but every send raises — exercises the manager's
    error-drop branch."""

    async def send_text(self, text: str) -> None:
        raise RuntimeError("socket gone")


class TestWebSocketManager:
    @pytest.mark.asyncio
    async def test_connect_then_broadcast_delivers_payload(self):
        manager = WebSocketManager()
        ws = _FakeConnectedWebSocket()
        await manager.connect(scope="hr", user_id=1, websocket=ws)

        sent = await manager.broadcast(
            scope="hr",
            event_type="ping",
            payload={"value": 42},
        )
        assert sent == 1
        assert len(ws.sent) == 1
        assert '"type": "ping"' in ws.sent[0]
        assert '"value": 42' in ws.sent[0]

    @pytest.mark.asyncio
    async def test_broadcast_no_subscribers_returns_zero(self):
        manager = WebSocketManager()
        sent = await manager.broadcast(
            scope="hr", event_type="x", payload={}
        )
        assert sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_drops_dead_sockets_from_room(self):
        manager = WebSocketManager()
        good = _FakeConnectedWebSocket()
        bad = _DeadWebSocket()
        await manager.connect(scope="hr", user_id=1, websocket=good)
        await manager.connect(scope="hr", user_id=2, websocket=bad)

        sent = await manager.broadcast(
            scope="hr", event_type="x", payload={}
        )
        # Only ``good`` accepted the message.
        assert sent == 1
        # ``bad`` got pulled from the room — next broadcast hits one.
        assert manager.room_size("hr") == 1
        sent_again = await manager.broadcast(
            scope="hr", event_type="x", payload={}
        )
        assert sent_again == 1

    @pytest.mark.asyncio
    async def test_disconnect_idempotent_for_unknown_socket(self):
        manager = WebSocketManager()
        await manager.disconnect(scope="hr", user_id=999, websocket=_FakeConnectedWebSocket())
        # No raise; room never created.
        assert manager.room_size("hr") == 0

    @pytest.mark.asyncio
    async def test_disconnect_cleans_empty_room(self):
        manager = WebSocketManager()
        ws = _FakeConnectedWebSocket()
        await manager.connect(scope="hr", user_id=1, websocket=ws)
        await manager.disconnect(scope="hr", user_id=1, websocket=ws)
        assert manager.room_size("hr") == 0

    def test_get_ws_manager_returns_singleton(self):
        a = get_ws_manager()
        b = get_ws_manager()
        assert a is b


# ---------------------------------------------------------------------------
# /ws/hr endpoint integration tests (via TestClient.websocket_connect)
# ---------------------------------------------------------------------------


class TestHrWebSocketEndpoint:
    def test_rejects_request_without_token(self, client):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/api/v1/ws/hr") as ws:
                ws.receive_text()
        assert exc.value.code == 1008

    def test_rejects_invalid_token(self, client):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                "/api/v1/ws/hr?token=not-a-jwt"
            ) as ws:
                ws.receive_text()
        assert exc.value.code == 1008

    def test_rejects_wrong_scope_token(self, client):
        # A token scoped to ``website`` (the admin console) should be
        # locked out of the HR socket.
        token = create_access_token(
            subject=42,
            scopes=[SCOPE_WEBSITE],
            expires_delta=timedelta(minutes=5),
        )
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/api/v1/ws/hr?token={token}"
            ) as ws:
                ws.receive_text()
        assert exc.value.code == 1008

    def test_accepts_valid_hr_token_and_sends_hello(self, client):
        token = create_access_token(
            subject=123,
            scopes=[SCOPE_HR],
            expires_delta=timedelta(minutes=5),
        )
        with client.websocket_connect(
            f"/api/v1/ws/hr?token={token}"
        ) as ws:
            message = ws.receive_json()
            assert message == {
                "type": "system.hello",
                "data": {"scope": "hr"},
            }


# ---------------------------------------------------------------------------
# Broadcast helper — the function the apply endpoints call
# ---------------------------------------------------------------------------


class TestBroadcastCandidateApplicationNew:
    @pytest.mark.asyncio
    async def test_pushes_event_to_every_hr_socket(self):
        manager = get_ws_manager()
        ws1 = _FakeConnectedWebSocket()
        ws2 = _FakeConnectedWebSocket()
        await manager.connect(scope=SCOPE_HR, user_id=1, websocket=ws1)
        await manager.connect(scope=SCOPE_HR, user_id=2, websocket=ws2)

        sent = await broadcast_candidate_application_new(
            candidate_id=10,
            candidate_name="Alex Example",
            application_id=100,
            job_title="Sales Lead",
            job_slug="sales-lead",
            source="public_form",
        )

        assert sent == 2
        # Both sockets received the same wire format. Decode one to
        # confirm the payload made it through verbatim.
        import json

        decoded = json.loads(ws1.sent[0])
        assert decoded["type"] == EVENT_CANDIDATE_APPLICATION_NEW
        assert decoded["data"] == {
            "candidate_id": 10,
            "candidate_name": "Alex Example",
            "application_id": 100,
            "job_title": "Sales Lead",
            "job_slug": "sales-lead",
            "source": "public_form",
        }

    @pytest.mark.asyncio
    async def test_swallows_broadcast_failures(self, monkeypatch):
        # Even if the manager misbehaves, the helper must not raise
        # — apply endpoints depend on this guarantee.
        def explode(*_a, **_kw):
            raise RuntimeError("simulated")

        mock_manager = MagicMock()
        mock_manager.broadcast.side_effect = explode
        monkeypatch.setattr(
            "app.services.hr_realtime.get_ws_manager",
            lambda: mock_manager,
        )

        sent = await broadcast_candidate_application_new(
            candidate_id=1,
            candidate_name="x",
            application_id=1,
            job_title=None,
            job_slug=None,
            source="manual_upload",
        )
        assert sent == 0
