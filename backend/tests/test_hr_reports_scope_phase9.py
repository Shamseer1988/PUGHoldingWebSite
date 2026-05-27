"""Phase 9 — Role-scoped reports.

Pins:
  * /hr/reports/types filtered by the user's effective scope.
    - HR Manager (view_all) -> sees every report.
    - Interviewer (view_mine) -> sees ONLY the mine-scoped reports.
    - Viewer (view_all per the role matrix) -> sees every report.
  * /hr/reports/{type} rejects a 403 when the report needs more
    scope than the user holds (URL-typing protection).
  * Mine-scoped reports run with actor_id filtering — interviewer
    sees only their own interviews, not the whole table.
  * Empty datasets return an empty rows list (not a 5xx).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
TYPES = "/api/v1/hr/reports/types"


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _setup_two_interviewers(db_session: Session) -> tuple[int, int]:
    """Insert two candidates and assign one interview to each of the
    seeded HR Manager and Interviewer users."""
    job = JobOpening(
        slug="p9-job",
        title="Senior Engineer",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    db_session.add(job)
    db_session.flush()

    # Two candidates / applications.
    rows = []
    for label in ("hr-mgr-iv", "interviewer-iv"):
        cand = Candidate(
            full_name=f"P9 {label}", email=f"{label}@example.com"
        )
        db_session.add(cand)
        db_session.flush()
        app = CandidateJobApplication(
            candidate_id=cand.id,
            job_opening_id=job.id,
            status=STATUS_CV_RECEIVED,
        )
        db_session.add(app)
        db_session.flush()
        rows.append(app.id)
    db_session.commit()
    return rows[0], rows[1]


def _make_interview(
    db_session: Session, application_id: int, interviewer_id: int
) -> Interview:
    iv = Interview(
        application_id=application_id,
        round_name="Technical screen",
        round_number=1,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
        duration_minutes=30,
        mode="online",
        location_or_link="https://example.com/meet",
        status="scheduled",
        interviewer_id=interviewer_id,
    )
    db_session.add(iv)
    db_session.commit()
    return iv


# ---------------------------------------------------------------------------
# /types filtered by scope
# ---------------------------------------------------------------------------


def test_hr_manager_sees_every_report_in_types(client, seed_auth):
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.get(TYPES, headers=headers)
    assert response.status_code == 200
    types = response.json()
    # HR Manager has view_all → at least the two mine-scoped reports
    # plus the broader catalog. Sanity check both ends.
    keys = {t["key"] for t in types}
    assert "candidate_full_export" in keys
    assert "my_assigned_interviews" in keys
    assert "my_feedback_submitted" in keys


def test_interviewer_sees_only_mine_reports_in_types(client, seed_auth):
    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.get(TYPES, headers=headers)
    assert response.status_code == 200
    types = response.json()
    keys = {t["key"] for t in types}
    # Mine-only: exactly the two.
    assert keys == {"my_assigned_interviews", "my_feedback_submitted"}


def test_viewer_sees_full_catalog_in_types(client, seed_auth):
    """Viewer / Auditor has view_all per the Phase-1 role matrix."""
    headers = _login(client, "viewer@pug.example.com", seed_auth["password"])
    response = client.get(TYPES, headers=headers)
    types = response.json()
    keys = {t["key"] for t in types}
    assert len(keys) >= 25  # the 25 base reports + 2 mine
    assert "candidate_full_export" in keys


# ---------------------------------------------------------------------------
# URL-typing protection
# ---------------------------------------------------------------------------


def test_interviewer_403s_on_all_scope_report(client, seed_auth):
    """Even by typing the URL, an Interviewer can't fetch a report
    that needs view_all (e.g. candidate_full_export)."""
    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/candidate_full_export", headers=headers
    )
    assert response.status_code == 403


def test_interviewer_can_call_mine_report(
    client, seed_auth, db_session: Session
):
    """Interviewer running their own report — happy path."""
    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/my_assigned_interviews", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "my_assigned_interviews"
    assert "When" in body["columns"]


# ---------------------------------------------------------------------------
# Actor-scoped data filtering
# ---------------------------------------------------------------------------


def test_my_assigned_interviews_filters_by_caller(
    client, seed_auth, db_session: Session
):
    """Two interviews are inserted, each owned by a different user.
    The Interviewer should see only the one assigned to them."""
    hr_app_id, iv_app_id = _setup_two_interviewers(db_session)
    hr_user = seed_auth["users"]["hr@pug.example.com"]
    interviewer = seed_auth["users"]["interviewer@pug.example.com"]
    _make_interview(db_session, hr_app_id, hr_user.id)
    _make_interview(db_session, iv_app_id, interviewer.id)

    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/my_assigned_interviews", headers=headers
    )
    assert response.status_code == 200
    rows = response.json()["rows"]
    # Exactly one row — the interviewer's own.
    assert len(rows) == 1
    # Column index 1 = candidate name
    assert rows[0][1] == "P9 interviewer-iv"


def test_my_feedback_submitted_buckets_pending_vs_submitted(
    client, seed_auth, db_session: Session
):
    """Feedback report tags each row as 'Submitted' or 'Pending'."""
    hr_app_id, iv_app_id = _setup_two_interviewers(db_session)
    interviewer = seed_auth["users"]["interviewer@pug.example.com"]
    iv = _make_interview(db_session, iv_app_id, interviewer.id)

    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/my_feedback_submitted", headers=headers
    )
    rows = response.json()["rows"]
    assert len(rows) == 1
    # Column index 4 = "Feedback" bucket — should be Pending since no
    # InterviewFeedback row was inserted.
    assert rows[0][4] == "Pending"

    # Submit feedback then re-run.
    response_submit = client.post(
        f"/api/v1/hr/interviews/{iv.id}/feedback",
        headers=headers,
        json={"rating": 4, "recommendation": "hire"},
    )
    assert response_submit.status_code == 201, response_submit.text

    response2 = client.get(
        "/api/v1/hr/reports/my_feedback_submitted", headers=headers
    )
    rows2 = response2.json()["rows"]
    assert rows2[0][4] == "Submitted"


def test_my_report_empty_when_interviewer_has_no_assignments(
    client, seed_auth
):
    """No interviews → empty rows list, NOT a 5xx."""
    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/my_assigned_interviews", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["rows"] == []
