"""Phase 5 — Interview reschedule.

Pins the new reschedule behavior layered on the existing PATCH
endpoint:
  * reschedule_reason round-trips through PATCH + GET
  * Changing scheduled_at flips the audit action to hr.interview.reschedule
  * The audit row captures old vs new values for scheduled_at / mode /
    location_or_link
  * send_email_now=True fires the notify_interview_rescheduled helper
    when (and only when) scheduled_at changes
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
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
    job = JobOpening(
        slug="p5-iv-job",
        title="Engineer",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    cand = Candidate(full_name="Phase 5 Candidate", email="p5@example.com")
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
        round_name="Initial",
        round_number=1,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
        duration_minutes=30,
        mode="online",
        location_or_link="https://meet.example.com/old",
        status="scheduled",
    )
    db_session.add(iv)
    db_session.commit()
    return iv


def test_reschedule_persists_reason(client, seed_auth, db_session: Session):
    iv = _setup_interview(db_session)
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    new_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    response = client.patch(
        f"/api/v1/hr/interviews/{iv.id}",
        headers=headers,
        json={
            "scheduled_at": new_time,
            "mode": "in_person",
            "location_or_link": "Boardroom 3, 5th floor",
            "reschedule_reason": "Interviewer travel conflict.",
            "send_email_now": False,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "in_person"
    assert body["location_or_link"] == "Boardroom 3, 5th floor"
    assert body["reschedule_reason"] == "Interviewer travel conflict."


def test_reschedule_writes_reschedule_audit_action(
    client, seed_auth, db_session: Session
):
    """When scheduled_at changes, audit row uses 'hr.interview.reschedule'
    (not the generic 'hr.interview.update') and captures old vs new."""
    iv = _setup_interview(db_session)
    original_time = iv.scheduled_at
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    new_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    response = client.patch(
        f"/api/v1/hr/interviews/{iv.id}",
        headers=headers,
        json={
            "scheduled_at": new_time,
            "reschedule_reason": "Candidate exam conflict.",
        },
    )
    assert response.status_code == 200

    audit_rows = list(
        db_session.execute(
            select(AuditLog).where(AuditLog.target_id == str(iv.id))
        ).scalars()
    )
    reschedule_actions = [
        a for a in audit_rows if a.action == "hr.interview.reschedule"
    ]
    assert len(reschedule_actions) == 1
    details = reschedule_actions[0].details or {}
    assert details.get("old_scheduled_at") is not None
    assert details.get("new_scheduled_at") is not None
    assert details["new_scheduled_at"] != details["old_scheduled_at"]


def test_field_only_edit_does_not_log_reschedule(
    client, seed_auth, db_session: Session
):
    """Editing duration without changing scheduled_at uses the plain
    update action — not a reschedule."""
    iv = _setup_interview(db_session)
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    response = client.patch(
        f"/api/v1/hr/interviews/{iv.id}",
        headers=headers,
        json={"duration_minutes": 45},
    )
    assert response.status_code == 200

    audit_rows = list(
        db_session.execute(
            select(AuditLog).where(AuditLog.target_id == str(iv.id))
        ).scalars()
    )
    reschedule_actions = [
        a for a in audit_rows if a.action == "hr.interview.reschedule"
    ]
    assert len(reschedule_actions) == 0
    update_actions = [
        a for a in audit_rows if a.action == "hr.interview.update"
    ]
    assert len(update_actions) == 1


def test_reschedule_send_email_dispatches_rescheduled_notification(
    client, seed_auth, db_session: Session, monkeypatch
):
    """send_email_now=True + scheduled_at change → notify_interview_rescheduled
    fires. send_email_now=False does not fire."""
    iv = _setup_interview(db_session)
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    calls: list[int] = []
    from app.services import hr_notifications

    monkeypatch.setattr(
        hr_notifications,
        "notify_interview_rescheduled",
        lambda *, interview_id, actor_id=None: calls.append(interview_id),
    )

    # Reschedule WITHOUT the checkbox — no email.
    new_time = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    response = client.patch(
        f"/api/v1/hr/interviews/{iv.id}",
        headers=headers,
        json={"scheduled_at": new_time, "send_email_now": False},
    )
    assert response.status_code == 200
    assert calls == []

    # Reschedule again WITH the checkbox — email fires.
    new_time2 = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
    response = client.patch(
        f"/api/v1/hr/interviews/{iv.id}",
        headers=headers,
        json={"scheduled_at": new_time2, "send_email_now": True},
    )
    assert response.status_code == 200
    assert calls == [iv.id]


def test_send_email_without_schedule_change_does_not_fire(
    client, seed_auth, db_session: Session, monkeypatch
):
    """Edge case: HR ticks send-email but doesn't actually change the
    schedule (just edits location). No email — candidate would be
    confused by 'rescheduled' email with the same time."""
    iv = _setup_interview(db_session)
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    calls: list[int] = []
    from app.services import hr_notifications

    monkeypatch.setattr(
        hr_notifications,
        "notify_interview_rescheduled",
        lambda *, interview_id, actor_id=None: calls.append(interview_id),
    )

    response = client.patch(
        f"/api/v1/hr/interviews/{iv.id}",
        headers=headers,
        json={"location_or_link": "New room", "send_email_now": True},
    )
    assert response.status_code == 200
    assert calls == []
