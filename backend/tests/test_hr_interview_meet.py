"""Tests for the advanced interview workflow (phase 6).

Covers:

* Google Meet integration uses the stub backend in tests.
* When Google is configured, online interview can create a Meet link
  and the link + event id are persisted on the Interview row.
* When Google is NOT configured, interview create still succeeds; the
  meeting link stays as the manually-entered one (or null).
* send-email endpoint stamps email_sent_at + status.
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
    Interview,
    JobOpening,
)
from app.services import google_calendar_service


HR_LOGIN = "/api/v1/hr/auth/login"
INTERVIEWS = "/api/v1/hr/interviews"


@pytest.fixture
def stub_calendar(monkeypatch):
    stub = google_calendar_service.StubGoogleCalendarBackend(configured=True)
    google_calendar_service.set_backend(stub)
    yield stub
    google_calendar_service.set_backend(None)


@pytest.fixture
def stub_calendar_disabled(monkeypatch):
    stub = google_calendar_service.StubGoogleCalendarBackend(configured=False)
    google_calendar_service.set_backend(stub)
    yield stub
    google_calendar_service.set_backend(None)


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


def test_create_online_interview_with_meet_link(
    client, seed_auth, db_session: Session, stub_calendar
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
            "create_google_meet": True,
            "send_email_now": False,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["meeting_link"]
    assert body["calendar_event_id"]
    assert body["calendar_provider"] == "google"
    assert "meet.google.com" in body["meeting_link"]

    # Stub backend captured the event.
    assert len(stub_calendar.events) == 1


def test_create_online_interview_without_google_config(
    client, seed_auth, db_session: Session, stub_calendar_disabled
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
            "create_google_meet": True,  # asked, but Google not configured
            "send_email_now": False,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["meeting_link"] is None
    assert body["location_or_link"] == "https://zoom.us/j/123"
    assert body["calendar_event_id"] is None


def test_create_meet_endpoint_adds_link(
    client, seed_auth, db_session: Session, stub_calendar
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
            "create_google_meet": False,
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


def test_create_meet_endpoint_rejects_for_in_person(
    client, seed_auth, db_session: Session, stub_calendar
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
    client, seed_auth, db_session: Session, stub_calendar_disabled
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
