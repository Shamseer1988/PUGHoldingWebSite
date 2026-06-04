"""Cross-worker WebSocket fan-out (Phase C-2b).

Unit-tests the Redis pub/sub bridge's consume side without standing up Redis:
a message from another worker is delivered to this worker's local sockets, a
message echoing this worker's own origin is skipped (no double-send), and the
toggle honours ``WS_PUBSUB_ENABLED``.
"""
from __future__ import annotations

import json

import pytest
from starlette.websockets import WebSocketState

from app.core import ws_manager
from app.core.ws_manager import (
    _ORIGIN,
    _handle_pubsub_message,
    _publish,
    get_ws_manager,
    pubsub_enabled,
)


class _FakeWS:
    """Minimal connected-WebSocket stand-in capturing send_text payloads."""

    def __init__(self) -> None:
        self.client_state = WebSocketState.CONNECTED
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)


@pytest.fixture(autouse=True)
def _fresh_manager():
    ws_manager._reset_manager_for_tests()
    yield
    ws_manager._reset_manager_for_tests()


@pytest.mark.asyncio
async def test_message_from_other_worker_is_delivered_locally():
    manager = get_ws_manager()
    ws = _FakeWS()
    await manager.connect(scope="hr", user_id=7, websocket=ws)

    envelope = json.dumps(
        {
            "origin": "another-worker",
            "scope": "hr",
            "type": "candidate.application.new",
            "data": {"candidate_id": 42},
        }
    )
    sent = await _handle_pubsub_message(envelope)

    assert sent == 1
    assert json.loads(ws.sent[0]) == {
        "type": "candidate.application.new",
        "data": {"candidate_id": 42},
    }


@pytest.mark.asyncio
async def test_own_origin_is_skipped_to_avoid_double_send():
    manager = get_ws_manager()
    ws = _FakeWS()
    await manager.connect(scope="hr", user_id=7, websocket=ws)

    envelope = json.dumps(
        {"origin": _ORIGIN, "scope": "hr", "type": "x", "data": {}}
    )
    sent = await _handle_pubsub_message(envelope)

    assert sent == 0
    assert ws.sent == []


@pytest.mark.asyncio
async def test_other_scope_is_not_delivered():
    manager = get_ws_manager()
    ws = _FakeWS()
    await manager.connect(scope="website", user_id=7, websocket=ws)

    envelope = json.dumps({"origin": "x", "scope": "hr", "type": "y", "data": {}})
    sent = await _handle_pubsub_message(envelope)

    assert sent == 0
    assert ws.sent == []


@pytest.mark.asyncio
async def test_undecodable_message_is_dropped_quietly():
    assert await _handle_pubsub_message("} not json {") == 0
    assert await _handle_pubsub_message(json.dumps(["a", "list"])) == 0


@pytest.mark.asyncio
async def test_publish_is_noop_when_disabled():
    # The default test env has WS_PUBSUB_ENABLED=false — _publish must return
    # without raising (and without needing a live Redis).
    assert pubsub_enabled() is False
    await _publish(scope="hr", event_type="x", payload={})


def test_pubsub_enabled_reads_env(monkeypatch):
    monkeypatch.setenv("WS_PUBSUB_ENABLED", "true")
    assert pubsub_enabled() is True
    monkeypatch.setenv("WS_PUBSUB_ENABLED", "off")
    assert pubsub_enabled() is False
    monkeypatch.setenv("WS_PUBSUB_ENABLED", "false")
    assert pubsub_enabled() is False
