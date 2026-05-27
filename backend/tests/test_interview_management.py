"""Tests for Phase 15 interview management (service + endpoints)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
from app.models.hr_ats import (
    INTERVIEW_CANCELLED,
    INTERVIEW_COMPLETED,
    INTERVIEW_MODE_IN_PERSON,
    INTERVIEW_MODE_ONLINE,
    INTERVIEW_MODE_PHONE,
    INTERVIEW_NO_SHOW,
    INTERVIEW_SCHEDULED,
    JOB_STATUS_OPEN,
    Candidate,
    CandidateJobApplication,
    Interview,
    JobOpening,
)
from app.services.interview_management import (
    FeedbackPermissionError,
    InvalidInterviewError,
    InvalidInterviewTransitionError,
    can_submit_feedback,
    change_interview_status,
    create_interview,
    submit_feedback,
)


HR_LOGIN = "/api/v1/hr/auth/login"
ADMIN_LOGIN = "/api/v1/admin/auth/login"
INTERVIEWS = "/api/v1/hr/interviews"


def _hr_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _admin_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        ADMIN_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_application(db_session: Session) -> CandidateJobApplication:
    job = JobOpening(
        slug="iv-flow",
        title="Project Manager",
        department="Construction",
        company="Core Engineering",
        location="Doha, Qatar",
        status=JOB_STATUS_OPEN,
    )
    candidate = Candidate(full_name="Ahmed Hassan", source="manual_upload")
    db_session.add_all([job, candidate])
    db_session.flush()
    app = CandidateJobApplication(
        candidate=candidate, job_opening=job, status="cv_received"
    )
    db_session.add(app)
    db_session.commit()
    return app


def _future(hours: int = 24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------


def test_create_interview_requires_future_time(db_session: Session, seed_auth):
    app = _make_application(db_session)
    superadmin = seed_auth["users"]["superadmin@pug.example.com"]
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    with pytest.raises(InvalidInterviewError):
        create_interview(
            db_session,
            application=app,
            round_name="First",
            round_number=1,
            scheduled_at=past,
            duration_minutes=60,
            mode=INTERVIEW_MODE_ONLINE,
            location_or_link="https://meet.example.com/x",
            interviewer_id=None,
            actor=superadmin,
        )


def test_create_interview_requires_link_for_online(db_session: Session, seed_auth):
    app = _make_application(db_session)
    superadmin = seed_auth["users"]["superadmin@pug.example.com"]
    with pytest.raises(InvalidInterviewError):
        create_interview(
            db_session,
            application=app,
            round_name="First",
            round_number=1,
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2),
            duration_minutes=60,
            mode=INTERVIEW_MODE_ONLINE,
            location_or_link=None,
            interviewer_id=None,
            actor=superadmin,
        )


def test_phone_mode_does_not_require_link(db_session: Session, seed_auth):
    app = _make_application(db_session)
    superadmin = seed_auth["users"]["superadmin@pug.example.com"]
    interview = create_interview(
        db_session,
        application=app,
        round_name="Phone screen",
        round_number=1,
        scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2),
        duration_minutes=30,
        mode=INTERVIEW_MODE_PHONE,
        location_or_link=None,
        interviewer_id=None,
        actor=superadmin,
    )
    assert interview.status == INTERVIEW_SCHEDULED


def test_status_transitions(db_session: Session, seed_auth):
    app = _make_application(db_session)
    superadmin = seed_auth["users"]["superadmin@pug.example.com"]
    interview = create_interview(
        db_session,
        application=app,
        round_name="First",
        round_number=1,
        scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2),
        duration_minutes=60,
        mode=INTERVIEW_MODE_IN_PERSON,
        location_or_link="HQ Boardroom",
        interviewer_id=None,
        actor=superadmin,
    )
    # scheduled → completed: allowed
    change_interview_status(db_session, interview=interview, new_status=INTERVIEW_COMPLETED)
    # completed → no_show: not allowed
    with pytest.raises(InvalidInterviewTransitionError):
        change_interview_status(db_session, interview=interview, new_status=INTERVIEW_NO_SHOW)


def test_can_submit_feedback_rules(db_session: Session, seed_auth):
    app = _make_application(db_session)
    superadmin = seed_auth["users"]["superadmin@pug.example.com"]
    hr_user = seed_auth["users"]["hr@pug.example.com"]
    other_user = seed_auth["users"]["webadmin@pug.example.com"]  # website scope only

    interview = create_interview(
        db_session,
        application=app,
        round_name="First",
        round_number=1,
        scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2),
        duration_minutes=60,
        mode=INTERVIEW_MODE_ONLINE,
        location_or_link="https://meet.example.com/x",
        interviewer_id=other_user.id,
        actor=superadmin,
    )
    # Superuser: always allowed
    assert can_submit_feedback(interview=interview, actor=superadmin) is True
    # Assigned interviewer (website-only user): allowed because they're assigned
    assert can_submit_feedback(interview=interview, actor=other_user) is True
    # HR scope user (not assigned): still allowed
    assert can_submit_feedback(interview=interview, actor=hr_user) is True

    # Replace the interview to remove assignment
    interview.interviewer_id = None
    assert can_submit_feedback(interview=interview, actor=other_user) is False


def test_submit_feedback_rating_bounds(db_session: Session, seed_auth):
    app = _make_application(db_session)
    superadmin = seed_auth["users"]["superadmin@pug.example.com"]
    interview = create_interview(
        db_session,
        application=app,
        round_name="First",
        round_number=1,
        scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2),
        duration_minutes=60,
        mode=INTERVIEW_MODE_PHONE,
        location_or_link=None,
        interviewer_id=None,
        actor=superadmin,
    )
    with pytest.raises(InvalidInterviewError):
        submit_feedback(
            db_session,
            interview=interview,
            actor=superadmin,
            rating=10,  # out of range
            recommendation="hire",
            feedback="ok",
            technical_score=None,
            communication_score=None,
            cultural_fit_score=None,
        )


# ---------------------------------------------------------------------------
# Endpoint integration tests
# ---------------------------------------------------------------------------


def test_create_interview_via_api(client, db_session: Session, seed_auth):
    app = _make_application(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    payload = {
        "application_id": app.id,
        "round_name": "First interview",
        "round_number": 1,
        "scheduled_at": _future(48),
        "duration_minutes": 45,
        "mode": "online",
        "location_or_link": "https://meet.example.com/abc",
    }
    response = client.post(INTERVIEWS, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["round_name"] == "First interview"
    assert body["status"] == INTERVIEW_SCHEDULED
    assert body["status_label"] == "Scheduled"
    assert body["mode_label"] == "Online"


def test_create_interview_rejects_past_time(client, db_session: Session, seed_auth):
    app = _make_application(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    response = client.post(
        INTERVIEWS,
        headers=headers,
        json={
            "application_id": app.id,
            "round_name": "Past",
            "round_number": 1,
            "scheduled_at": past,
            "duration_minutes": 60,
            "mode": "online",
            "location_or_link": "https://meet.example.com/x",
        },
    )
    assert response.status_code == 422, response.text
    assert "future" in response.json()["detail"].lower()


def test_list_interviews_with_filters(client, db_session: Session, seed_auth):
    app = _make_application(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    # Two interviews on different days, one cancelled
    for offset, mode in ((24, "online"), (48, "phone")):
        client.post(
            INTERVIEWS,
            headers=headers,
            json={
                "application_id": app.id,
                "round_name": f"R{offset}",
                "round_number": 1 if offset == 24 else 2,
                "scheduled_at": _future(offset),
                "duration_minutes": 60,
                "mode": mode,
                "location_or_link": "https://link" if mode == "online" else None,
            },
        )

    response = client.get(INTERVIEWS, headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2

    response = client.get(
        INTERVIEWS, headers=headers, params={"application_id": app.id}
    )
    assert len(response.json()) == 2

    response = client.get(
        INTERVIEWS, headers=headers, params={"upcoming_days": 1}
    )
    # Only the 24-hour one falls inside 1 day window
    assert len(response.json()) == 1


def test_status_change_endpoint(client, db_session: Session, seed_auth):
    app = _make_application(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    created = client.post(
        INTERVIEWS,
        headers=headers,
        json={
            "application_id": app.id,
            "round_name": "First",
            "round_number": 1,
            "scheduled_at": _future(),
            "duration_minutes": 60,
            "mode": "phone",
        },
    ).json()

    response = client.post(
        f"{INTERVIEWS}/{created['id']}/status",
        headers=headers,
        json={"new_status": "completed"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == INTERVIEW_COMPLETED

    # Completed → cancelled is forbidden
    response = client.post(
        f"{INTERVIEWS}/{created['id']}/status",
        headers=headers,
        json={"new_status": "cancelled"},
    )
    assert response.status_code == 409


def test_submit_feedback_assigned_interviewer_can_submit(
    client, db_session: Session, seed_auth
):
    app = _make_application(db_session)
    hr_user = seed_auth["users"]["hr@pug.example.com"]
    web_user = seed_auth["users"]["webadmin@pug.example.com"]
    headers = _hr_auth(client, seed_auth["password"])

    created = client.post(
        INTERVIEWS,
        headers=headers,
        json={
            "application_id": app.id,
            "round_name": "First",
            "round_number": 1,
            "scheduled_at": _future(),
            "duration_minutes": 60,
            "mode": "phone",
            "interviewer_id": web_user.id,
        },
    ).json()

    # Sign in as the (website-scope) assigned interviewer
    web_login = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "webadmin@pug.example.com", "password": seed_auth["password"]},
    )
    web_token = web_login.json()["access_token"]
    web_headers = {"Authorization": f"Bearer {web_token}"}

    response = client.post(
        f"{INTERVIEWS}/{created['id']}/feedback",
        headers=web_headers,
        json={
            "rating": 4,
            "recommendation": "hire",
            "feedback": "Strong communicator.",
            "technical_score": 7,
            "communication_score": 8,
            "cultural_fit_score": 9,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["rating"] == 4
    assert body["recommendation"] == "hire"
    assert body["submitted_by_email"] == web_user.email


def test_unassigned_user_cannot_submit_feedback(
    client, db_session: Session, seed_auth
):
    app = _make_application(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    web_user = seed_auth["users"]["webadmin@pug.example.com"]

    created = client.post(
        INTERVIEWS,
        headers=headers,
        json={
            "application_id": app.id,
            "round_name": "First",
            "round_number": 1,
            "scheduled_at": _future(),
            "duration_minutes": 60,
            "mode": "phone",
            # NOT assigning web_user
        },
    ).json()

    web_login = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "webadmin@pug.example.com", "password": seed_auth["password"]},
    )
    web_headers = {"Authorization": f"Bearer {web_login.json()['access_token']}"}

    response = client.post(
        f"{INTERVIEWS}/{created['id']}/feedback",
        headers=web_headers,
        json={"rating": 3, "recommendation": "maybe"},
    )
    assert response.status_code == 403, response.text


def test_feedback_auto_completes_interview(client, db_session: Session, seed_auth):
    """When feedback is submitted on a still-scheduled interview, the
    interview is auto-marked completed."""
    app = _make_application(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    created = client.post(
        INTERVIEWS,
        headers=headers,
        json={
            "application_id": app.id,
            "round_name": "First",
            "round_number": 1,
            "scheduled_at": _future(),
            "duration_minutes": 60,
            "mode": "phone",
        },
    ).json()
    assert created["status"] == INTERVIEW_SCHEDULED

    client.post(
        f"{INTERVIEWS}/{created['id']}/feedback",
        headers=headers,
        json={"rating": 4, "recommendation": "hire"},
    )
    # Re-fetch
    response = client.get(f"{INTERVIEWS}/{created['id']}", headers=headers)
    body = response.json()
    assert body["status"] == INTERVIEW_COMPLETED
    assert len(body["feedback"]) == 1


def test_candidate_detail_includes_interviews(client, db_session: Session, seed_auth):
    app = _make_application(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    client.post(
        INTERVIEWS,
        headers=headers,
        json={
            "application_id": app.id,
            "round_name": "First",
            "round_number": 1,
            "scheduled_at": _future(),
            "duration_minutes": 60,
            "mode": "phone",
        },
    )

    detail = client.get(
        f"/api/v1/hr/candidates/{app.candidate_id}", headers=headers
    ).json()
    assert detail["applications"][0]["interview_count"] == 1
    iv = detail["applications"][0]["interviews"][0]
    assert iv["round_name"] == "First"
    assert iv["status_label"] == "Scheduled"
    assert detail["applications"][0]["next_interview_at"] is not None


def test_audit_log_on_create_status_and_feedback(
    client, db_session: Session, seed_auth
):
    app = _make_application(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    created = client.post(
        INTERVIEWS,
        headers=headers,
        json={
            "application_id": app.id,
            "round_name": "First",
            "round_number": 1,
            "scheduled_at": _future(),
            "duration_minutes": 60,
            "mode": "phone",
        },
    ).json()
    client.post(
        f"{INTERVIEWS}/{created['id']}/feedback",
        headers=headers,
        json={"rating": 5, "recommendation": "hire"},
    )

    actions = {
        row.action
        for row in db_session.query(AuditLog)
        .filter(AuditLog.action.like("hr.interview.%"))
        .all()
    }
    assert "hr.interview.create" in actions
    assert "hr.interview.feedback.submit" in actions


def test_mine_endpoint_restricts_to_assigned(client, db_session: Session, seed_auth):
    app = _make_application(db_session)
    hr_user = seed_auth["users"]["hr@pug.example.com"]
    headers = _hr_auth(client, seed_auth["password"])

    # One interview assigned to hr_user, one unassigned
    for kwargs in (
        {"interviewer_id": hr_user.id},
        {},
    ):
        client.post(
            INTERVIEWS,
            headers=headers,
            json={
                "application_id": app.id,
                "round_name": "Round",
                "round_number": 1,
                "scheduled_at": _future(),
                "duration_minutes": 30,
                "mode": "phone",
                **kwargs,
            },
        )

    response = client.get(f"{INTERVIEWS}/mine", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["interviewer_id"] == hr_user.id


def test_external_user_without_assignment_gets_empty_list(
    client, db_session: Session, seed_auth
):
    app = _make_application(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    client.post(
        INTERVIEWS,
        headers=headers,
        json={
            "application_id": app.id,
            "round_name": "Round",
            "round_number": 1,
            "scheduled_at": _future(),
            "duration_minutes": 30,
            "mode": "phone",
        },
    )

    # Website-scope user (no HR permissions at all) — after the Phase 1
    # RBAC overhaul this is rejected with 403, not given an empty list.
    # The old behavior leaked the existence of /hr/interviews to any
    # logged-in admin; the new behavior keeps HR data strictly scoped.
    web_login = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "webadmin@pug.example.com", "password": seed_auth["password"]},
    )
    web_headers = {"Authorization": f"Bearer {web_login.json()['access_token']}"}
    response = client.get(INTERVIEWS, headers=web_headers)
    assert response.status_code == 403
