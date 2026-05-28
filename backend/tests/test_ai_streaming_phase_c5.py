"""Phase C-5 — Streaming AI assistant.

Validates the ``POST /public/ai-assistant/ask-stream`` SSE
endpoint and the underlying ``stream_answer_question`` generator
without standing up an Azure OpenAI deployment in tests:

* Mock / disabled modes emit the same wire format the live path
  would — one or more ``delta`` frames followed by a ``done``.
* The endpoint sets ``text/event-stream`` and the no-buffering
  headers proxies need to actually flush chunks.
* The ``PublicAIQuery`` log row is written once the stream is
  drained — same row schema the blocking endpoint produces, so
  the existing admin "AI Usage" page keeps working.
* An injected exception inside ``_live_answer_stream`` becomes a
  fallback ``delta`` + ``done`` rather than an HTTP 500 — visitors
  always see something.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai import public_assistant
from app.ai.candidate_review import AI_MODE_DISABLED, AI_MODE_MOCK
from app.ai.public_assistant import (
    AskResult,
    stream_answer_question,
)
from app.models.cms import SiteSetting
from app.models.hr_ats import AISetting, PublicAIQuery


URL = "/api/v1/public/ai-assistant/ask-stream"


# ---------------------------------------------------------------------------
# Generator unit tests
# ---------------------------------------------------------------------------


def _ensure_ai_setting_off(db: Session) -> AISetting:
    """Seed the singleton AISetting row with public AI disabled —
    the simplest configuration to force the fallback path."""
    setting = db.get(AISetting, 1)
    if setting is None:
        setting = AISetting(id=1, mode=AI_MODE_DISABLED, public_enabled=False)
        db.add(setting)
    else:
        setting.public_enabled = False
        setting.mode = AI_MODE_DISABLED
    db.commit()
    return setting


def test_stream_yields_done_for_blank_question(db_session: Session):
    events = list(
        stream_answer_question(db_session, question="   ", history=None)
    )
    kinds = [k for k, _ in events]
    assert "done" in kinds
    # Always at least one delta so the frontend can render the
    # placeholder text without special-casing "empty stream".
    assert kinds[0] == "delta"
    done_payload = next(p for k, p in events if k == "done")
    assert isinstance(done_payload, AskResult)
    assert done_payload.was_fallback is True


def test_stream_yields_fallback_when_public_ai_disabled(db_session: Session):
    _ensure_ai_setting_off(db_session)
    db_session.add(
        SiteSetting(
            id=1,
            site_name="PUG Holding",
            contact_phone="+974-1000-0000",
            contact_email="hello@example.com",
        )
    )
    db_session.commit()

    events = list(
        stream_answer_question(
            db_session, question="Tell me about the group.", history=None
        )
    )
    deltas = [p for k, p in events if k == "delta"]
    done = next(p for k, p in events if k == "done")
    assert deltas, "fallback path must emit at least one delta"
    assert done.mode == AI_MODE_DISABLED
    assert done.was_fallback is True
    # The fallback weaves the contact details into the answer so a
    # visitor can still reach the team.
    assert "+974-1000-0000" in done.answer


def test_stream_yields_mock_answer_when_mode_is_mock(
    db_session: Session, monkeypatch
):
    setting = db_session.get(AISetting, 1)
    if setting is None:
        setting = AISetting(id=1)
        db_session.add(setting)
    setting.mode = AI_MODE_MOCK
    setting.public_enabled = True
    db_session.commit()

    db_session.add(SiteSetting(id=1, site_name="PUG Holding"))
    db_session.commit()

    events = list(
        stream_answer_question(
            db_session,
            question="Hello PUG",
            history=None,
        )
    )
    done = next(p for k, p in events if k == "done")
    assert done.mode == AI_MODE_MOCK
    # Mock mode is deterministic — for a greeting it produces the
    # canned "Ask PUG AI" intro. Case-insensitive substring check
    # so future copy tweaks don't break the test.
    assert "ask pug ai" in done.answer.lower()


# ---------------------------------------------------------------------------
# /public/ai-assistant/ask-stream endpoint
# ---------------------------------------------------------------------------


def _parse_sse(body_text: str) -> list[dict]:
    """Decode an SSE response body into a list of parsed JSON events."""
    events: list[dict] = []
    for raw in body_text.split("\n\n"):
        raw = raw.strip()
        if not raw or not raw.startswith("data:"):
            continue
        payload = raw[len("data:") :].strip()
        events.append(json.loads(payload))
    return events


def test_endpoint_returns_event_stream_content_type(
    client: TestClient, db_session: Session
):
    _ensure_ai_setting_off(db_session)
    response = client.post(URL, json={"question": "hi"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    # The proxy-buffer-defeating headers must be present so the
    # frontend actually receives chunks as the backend emits them.
    assert response.headers.get("cache-control", "").startswith("no-cache")
    assert response.headers.get("x-accel-buffering") == "no"


def test_endpoint_streams_delta_frames_then_done(
    client: TestClient, db_session: Session
):
    _ensure_ai_setting_off(db_session)
    db_session.add(
        SiteSetting(id=1, site_name="PUG", contact_email="hi@example.com")
    )
    db_session.commit()

    response = client.post(URL, json={"question": "Where are you based?"})
    events = _parse_sse(response.text)
    # The very last frame is always ``done``; everything before is a
    # ``delta``. With the fallback path that's exactly one delta.
    assert events[-1]["type"] == "done"
    assert any(e["type"] == "delta" for e in events)
    done = events[-1]
    assert done["mode"] in {AI_MODE_DISABLED, "live", AI_MODE_MOCK}
    assert "was_fallback" in done


def test_endpoint_logs_a_public_ai_query_row(
    client: TestClient, db_session: Session
):
    _ensure_ai_setting_off(db_session)
    db_session.add(SiteSetting(id=1, site_name="PUG"))
    db_session.commit()

    before = db_session.query(PublicAIQuery).count()
    response = client.post(
        URL,
        json={"question": "What does PUG do?", "session_id": "sess-xyz"},
    )
    assert response.status_code == 200
    # Drain the body so the StreamingResponse runs to completion (and
    # its ``finally`` writes the log row).
    _ = response.text

    # The endpoint uses a separate session from ``db_session`` —
    # expire and re-query so we see the just-committed row.
    db_session.expire_all()
    rows = (
        db_session.query(PublicAIQuery)
        .filter(PublicAIQuery.session_id == "sess-xyz")
        .all()
    )
    assert len(rows) == 1
    assert rows[0].question == "What does PUG do?"
    assert rows[0].answer  # non-empty — fallback weaves contacts in
    assert db_session.query(PublicAIQuery).count() == before + 1


def test_endpoint_session_id_echoed_in_done_frame(
    client: TestClient, db_session: Session
):
    _ensure_ai_setting_off(db_session)
    db_session.add(SiteSetting(id=1, site_name="PUG"))
    db_session.commit()

    response = client.post(
        URL,
        json={"question": "hello", "session_id": "abc-123"},
    )
    events = _parse_sse(response.text)
    done = events[-1]
    assert done["session_id"] == "abc-123"


def test_endpoint_recovers_from_live_provider_failure(
    client: TestClient, db_session: Session, monkeypatch
):
    """Force ``_live_answer_stream`` to raise — the orchestrator
    must catch it and ship the visitor a fallback answer instead
    of failing the HTTP request."""
    setting = db_session.get(AISetting, 1) or AISetting(id=1)
    setting.mode = "live"
    setting.public_enabled = True
    setting.azure_endpoint = "https://fake.example.com"
    setting.azure_deployment = "fake"
    setting.azure_api_key = "fake"
    db_session.add(setting)
    db_session.add(
        SiteSetting(id=1, site_name="PUG", contact_email="reach@example.com")
    )
    db_session.commit()

    def _boom(**_kw):
        from app.ai.candidate_review import AIProviderError

        raise AIProviderError("simulated provider crash")
        yield  # pragma: no cover - generator marker

    monkeypatch.setattr(
        public_assistant, "_live_answer_stream", _boom
    )

    response = client.post(URL, json={"question": "tell me about PUG"})
    assert response.status_code == 200
    events = _parse_sse(response.text)
    done = events[-1]
    assert done["type"] == "done"
    assert done["was_fallback"] is True
