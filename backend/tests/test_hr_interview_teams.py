"""Tests for the Microsoft Teams interview workflow (phase 6 — Teams replacement).

Covers:

* Teams integration uses the stub backend in tests — no Graph calls.
* When Teams is configured, online interview can create a meeting link
  and the join URL + meeting id are persisted on the Interview row.
* When Teams is NOT configured, interview create still succeeds; the
  meeting link stays as the manually-entered one (or null).
* create-meet endpoint adds a link to an existing online interview.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    STATUS_CV_RECEIVED,
    Candidate,
    CandidateJobApplication,
    JobOpening,
)
from app.services import teams_meeting_service


HR_LOGIN = "/api/v1/hr/auth/login"
INTERVIEWS = "/api/v1/hr/interviews"


@pytest.fixture
def stub_teams(monkeypatch):
    stub = teams_meeting_service.StubTeamsBackend(configured=True)
    teams_meeting_service.set_backend(stub)
    yield stub
    teams_meeting_service.set_backend(None)


@pytest.fixture
def stub_teams_disabled(monkeypatch):
    stub = teams_meeting_service.StubTeamsBackend(configured=False)
    teams_meeting_service.set_backend(stub)
    yield stub
    teams_meeting_service.set_backend(None)


def _auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_application(db_session: Session) -> CandidateJobApplication:
    job = JobOpening(
        slug="iv-meet",
        title="Senior Engineer",
        department="Eng",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    cand = Candidate(
        full_name="Test Candidate",
        email="cand@example.com",
    )
    db_session.add_all([job, cand])
    db_session.flush()
    app = CandidateJobApplication(
        candidate_id=cand.id,
        job_opening_id=job.id,
        status=STATUS_CV_RECEIVED,
    )
    db_session.add(app)
    db_session.commit()
    return app


def _future_dt(hours: int = 24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def test_create_online_interview_with_teams_link(
    client, seed_auth, db_session: Session, stub_teams
):
    app = _seed_application(db_session)
    headers = _auth(client, seed_auth["password"])

    response = client.post(
        INTERVIEWS,
        json={
            "application_id": app.id,
            "round_name": "Technical Round",
            "round_number": 1,
            "scheduled_at": _future_dt(48),
            "duration_minutes": 60,
            "mode": "online",
            "create_teams_meeting": True,
            "send_email_now": False,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["meeting_link"]
    assert body["calendar_event_id"]
    assert body["calendar_provider"] == "teams"
    assert "teams.microsoft.com" in body["meeting_link"]

    # Stub backend captured the event.
    assert len(stub_teams.events) == 1


def test_create_online_interview_without_teams_config(
    client, seed_auth, db_session: Session, stub_teams_disabled
):
    app = _seed_application(db_session)
    headers = _auth(client, seed_auth["password"])

    response = client.post(
        INTERVIEWS,
        json={
            "application_id": app.id,
            "round_name": "Technical Round",
            "round_number": 1,
            "scheduled_at": _future_dt(48),
            "duration_minutes": 60,
            "mode": "online",
            "location_or_link": "https://zoom.us/j/123",
            "create_teams_meeting": True,  # asked, but Teams not configured
            "send_email_now": False,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["meeting_link"] is None
    assert body["location_or_link"] == "https://zoom.us/j/123"
    assert body["calendar_event_id"] is None


def test_create_meet_endpoint_adds_teams_link(
    client, seed_auth, db_session: Session, stub_teams
):
    app = _seed_application(db_session)
    headers = _auth(client, seed_auth["password"])

    create = client.post(
        INTERVIEWS,
        json={
            "application_id": app.id,
            "round_name": "Initial Round",
            "scheduled_at": _future_dt(48),
            "duration_minutes": 30,
            "mode": "online",
            "location_or_link": "TBD",
            "create_teams_meeting": False,
            "send_email_now": False,
        },
        headers=headers,
    )
    assert create.status_code == 201
    interview_id = create.json()["id"]

    add_meet = client.post(
        f"{INTERVIEWS}/{interview_id}/create-meet", headers=headers
    )
    assert add_meet.status_code == 200
    body = add_meet.json()
    assert body["meeting_link"]
    assert body["calendar_event_id"]
    assert body["calendar_provider"] == "teams"


def test_create_meet_endpoint_rejects_for_in_person(
    client, seed_auth, db_session: Session, stub_teams
):
    app = _seed_application(db_session)
    headers = _auth(client, seed_auth["password"])
    create = client.post(
        INTERVIEWS,
        json={
            "application_id": app.id,
            "round_name": "In Person",
            "scheduled_at": _future_dt(48),
            "duration_minutes": 60,
            "mode": "in_person",
            "location_or_link": "PUG HQ, Doha",
            "send_email_now": False,
        },
        headers=headers,
    )
    interview_id = create.json()["id"]
    add_meet = client.post(
        f"{INTERVIEWS}/{interview_id}/create-meet", headers=headers
    )
    assert add_meet.status_code == 409


def test_send_email_endpoint_stamps_metadata(
    client, seed_auth, db_session: Session, stub_teams_disabled
):
    app = _seed_application(db_session)
    headers = _auth(client, seed_auth["password"])

    create = client.post(
        INTERVIEWS,
        json={
            "application_id": app.id,
            "round_name": "Round",
            "scheduled_at": _future_dt(48),
            "duration_minutes": 60,
            "mode": "online",
            "location_or_link": "https://example.com",
            "send_email_now": False,
        },
        headers=headers,
    )
    interview_id = create.json()["id"]

    send = client.post(
        f"{INTERVIEWS}/{interview_id}/send-email", headers=headers
    )
    assert send.status_code == 200
    body = send.json()
    assert body["email_sent_at"] is not None
    assert body["email_delivery_status"] == "sent"
