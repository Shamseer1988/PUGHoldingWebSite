"""Phase 4 — Interview quick-update feedback fields.

Pins the three new free-text columns on hr_interview_feedback
(strengths, weaknesses, next_action) round-trip through:
  * POST /hr/interviews/{id}/feedback
  * GET  /hr/interviews/{id}/feedback
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


HR_LOGIN = "/api/v1/hr/auth/login"


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _setup_interview(db_session: Session) -> Interview:
    """Insert a candidate + scheduled interview, return the interview."""
    job = JobOpening(
        slug="p4-iv-job",
        title="Engineer",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    cand = Candidate(full_name="Phase 4 Candidate", email="p4@example.com")
    db_session.add_all([job, cand])
    db_session.flush()
    app = CandidateJobApplication(
        candidate_id=cand.id,
        job_opening_id=job.id,
        status=STATUS_CV_RECEIVED,
    )
    db_session.add(app)
    db_session.flush()
    iv = Interview(
        application_id=app.id,
        round_name="Technical",
        round_number=1,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
        duration_minutes=45,
        mode="online",
        location_or_link="https://example.com/meet",
        status="scheduled",
    )
    db_session.add(iv)
    db_session.commit()
    return iv


def test_feedback_endpoint_persists_phase4_fields(
    client, seed_auth, db_session: Session
):
    """strengths / weaknesses / next_action round-trip through the
    feedback endpoint."""
    iv = _setup_interview(db_session)
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    response = client.post(
        f"/api/v1/hr/interviews/{iv.id}/feedback",
        headers=headers,
        json={
            "rating": 4,
            "recommendation": "hire",
            "feedback": "Solid candidate.",
            "technical_score": 8,
            "communication_score": 7,
            "cultural_fit_score": 9,
            "strengths": "Strong system-design instincts.",
            "weaknesses": "Limited prior cloud exposure.",
            "next_action": "Schedule final round with the head of engineering.",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["strengths"] == "Strong system-design instincts."
    assert body["weaknesses"] == "Limited prior cloud exposure."
    assert (
        body["next_action"]
        == "Schedule final round with the head of engineering."
    )

    # GET returns the same values.
    listing = client.get(
        f"/api/v1/hr/interviews/{iv.id}/feedback", headers=headers
    )
    assert listing.status_code == 200
    rows = listing.json()
    assert len(rows) == 1
    assert rows[0]["strengths"] == "Strong system-design instincts."


def test_feedback_phase4_fields_optional(client, seed_auth, db_session: Session):
    """Submitting feedback without the new fields keeps them NULL —
    proves backward compat with the older form payload."""
    iv = _setup_interview(db_session)
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    response = client.post(
        f"/api/v1/hr/interviews/{iv.id}/feedback",
        headers=headers,
        json={"rating": 3, "recommendation": "maybe"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["strengths"] is None
    assert body["weaknesses"] is None
    assert body["next_action"] is None
