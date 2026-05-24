"""Tests for the Phase 14 candidate workflow / status pipeline."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    STATUS_BLACKLISTED,
    STATUS_CV_RECEIVED,
    STATUS_FIRST_INTERVIEW,
    STATUS_HR_REVIEW_PENDING,
    STATUS_JOINED,
    STATUS_OFFER_SENT,
    STATUS_REJECTED,
    STATUS_SELECTED,
    STATUS_SHORTLISTED,
    Candidate,
    CandidateJobApplication,
    JobOpening,
)
from app.services.candidate_workflow import (
    InvalidTransitionError,
    MissingReasonError,
    PermissionDeniedError,
    allowed_next_statuses,
    change_status,
)


HR_LOGIN = "/api/v1/hr/auth/login"
HR_UPLOAD = "/api/v1/hr/candidates/upload"
ADMIN_LOGIN = "/api/v1/admin/auth/login"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hr_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _superuser_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        ADMIN_LOGIN, json={"email": "superadmin@pug.example.com", "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _docx_bytes(text: str) -> bytes:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def _make_job(db_session: Session) -> JobOpening:
    job = JobOpening(
        slug="pm-flow",
        title="Project Manager",
        department="Construction",
        company="Core Engineering",
        location="Doha, Qatar",
        min_experience=8,
        max_experience=15,
        status=JOB_STATUS_OPEN,
    )
    db_session.add(job)
    db_session.commit()
    return job


def _upload(client: TestClient, headers: dict, slug: str) -> dict:
    response = client.post(
        HR_UPLOAD,
        headers=headers,
        files={
            "file": (
                "x.docx",
                io.BytesIO(_docx_bytes("Sample CV content")),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"full_name": "Ahmed Test", "job_slug": slug},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Unit tests on the service
# ---------------------------------------------------------------------------


def test_allowed_next_statuses_from_cv_received_includes_terminal():
    targets = allowed_next_statuses(STATUS_CV_RECEIVED)
    assert STATUS_REJECTED in targets
    assert STATUS_BLACKLISTED in targets
    assert STATUS_HR_REVIEW_PENDING in targets


def test_allowed_next_statuses_terminal_has_none_for_hr():
    assert allowed_next_statuses(STATUS_JOINED) == set()
    assert allowed_next_statuses(STATUS_REJECTED) == set()
    assert allowed_next_statuses(STATUS_BLACKLISTED) == set()


def test_allowed_next_statuses_terminal_has_reopen_for_superuser():
    targets = allowed_next_statuses(STATUS_BLACKLISTED, actor_is_superuser=True)
    assert STATUS_HR_REVIEW_PENDING in targets


def test_change_status_requires_rejection_reason(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={"new_status": STATUS_REJECTED, "remarks": "thanks"},
    )
    assert response.status_code == 422, response.text
    assert "rejection reason" in response.json()["detail"].lower()


def test_change_status_with_rejection_reason_succeeds(
    client, db_session: Session, seed_auth
):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={
            "new_status": STATUS_REJECTED,
            "rejection_reason": "Position filled internally.",
        },
    )
    assert response.status_code == 200, response.text
    body2 = response.json()
    app = body2["applications"][0]
    assert app["status"] == STATUS_REJECTED
    assert app["last_rejection_reason"] == "Position filled internally."
    assert app["allowed_next_statuses"] == []  # final state for HR


def test_blacklist_requires_superuser(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={
            "new_status": STATUS_BLACKLISTED,
            "blacklist_approval": "MD approved on call.",
        },
    )
    assert response.status_code == 403, response.text


def test_blacklist_requires_approval(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    headers = _superuser_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={"new_status": STATUS_BLACKLISTED},
    )
    assert response.status_code == 422, response.text
    assert "blacklist approval" in response.json()["detail"].lower()


def test_blacklist_succeeds_with_superuser_and_approval(
    client, db_session: Session, seed_auth
):
    job = _make_job(db_session)
    headers = _superuser_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={
            "new_status": STATUS_BLACKLISTED,
            "blacklist_approval": "MD approved on call 2026-05-24.",
        },
    )
    assert response.status_code == 200
    body2 = response.json()
    assert body2["is_blacklisted"] is True
    app = body2["applications"][0]
    assert app["status"] == STATUS_BLACKLISTED


def test_invalid_transition_returns_409(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    # cv_received → joined is not allowed
    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={"new_status": STATUS_JOINED},
    )
    assert response.status_code == 409


def test_status_history_records_every_change(
    client, db_session: Session, seed_auth
):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    # Walk through three transitions.
    for target in (STATUS_HR_REVIEW_PENDING, STATUS_SHORTLISTED, STATUS_FIRST_INTERVIEW):
        response = client.post(
            f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
            headers=headers,
            json={"new_status": target, "remarks": f"Moved to {target}"},
        )
        assert response.status_code == 200, response.text

    response = client.get(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status-history",
        headers=headers,
    )
    assert response.status_code == 200
    history = response.json()
    assert len(history) == 3
    # Oldest first
    assert history[0]["old_status"] == STATUS_CV_RECEIVED
    assert history[0]["new_status"] == STATUS_HR_REVIEW_PENDING
    assert history[0]["changed_by_email"] == "hr@pug.example.com"
    assert history[-1]["new_status"] == STATUS_FIRST_INTERVIEW


def test_audit_log_written_on_status_change(
    client, db_session: Session, seed_auth
):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={"new_status": STATUS_HR_REVIEW_PENDING, "remarks": "Routing"},
    )
    assert response.status_code == 200

    entries = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "hr.candidate.status.change")
        .all()
    )
    assert len(entries) == 1
    details = entries[0].details
    assert details["previous_status"] == STATUS_CV_RECEIVED
    assert details["new_status"] == STATUS_HR_REVIEW_PENDING
    assert details["remarks"] == "Routing"


def test_double_transition_to_same_status_returns_409(
    client, db_session: Session, seed_auth
):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={"new_status": STATUS_CV_RECEIVED},
    )
    assert response.status_code == 409


def test_workflow_meta_lists_all_statuses(client, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get("/api/v1/hr/candidates/workflow/meta", headers=headers)
    assert response.status_code == 200
    body = response.json()
    values = [s["value"] for s in body["statuses"]]
    assert values[0] == STATUS_CV_RECEIVED
    assert STATUS_REJECTED in values
    assert STATUS_BLACKLISTED in values
    # The final flag is correctly set on terminal statuses
    for s in body["statuses"]:
        if s["value"] in (STATUS_JOINED, STATUS_REJECTED, STATUS_BLACKLISTED):
            assert s["is_final"] is True
    # Transitions map is keyed by every current status
    assert STATUS_CV_RECEIVED in body["transitions"]
    assert STATUS_OFFER_SENT in body["transitions"]


def test_application_summary_includes_workflow_metadata(
    client, db_session: Session, seed_auth
):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid = body["candidate_id"]

    detail = client.get(f"/api/v1/hr/candidates/{cid}", headers=headers).json()
    app = detail["applications"][0]
    assert app["status"] == STATUS_CV_RECEIVED
    assert app["status_label"] == "CV Received"
    # Allowed next statuses present for HR (not superuser).
    assert STATUS_HR_REVIEW_PENDING in app["allowed_next_statuses"]
    assert STATUS_REJECTED in app["allowed_next_statuses"]
    # The candidate has at least the initial application but no history yet.
    assert app["history_count"] == 0


def test_superuser_can_reopen_rejected(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    headers = _superuser_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    # Reject first
    client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={
            "new_status": STATUS_REJECTED,
            "rejection_reason": "Initial screening miss.",
        },
    )
    # Now reopen
    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={"new_status": STATUS_HR_REVIEW_PENDING, "remarks": "Reopening."},
    )
    assert response.status_code == 200, response.text
    body2 = response.json()
    assert body2["applications"][0]["status"] == STATUS_HR_REVIEW_PENDING


def test_superuser_reopening_blacklist_clears_candidate_flag(
    client, db_session: Session, seed_auth
):
    job = _make_job(db_session)
    headers = _superuser_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={
            "new_status": STATUS_BLACKLISTED,
            "blacklist_approval": "Approved.",
        },
    )
    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/status",
        headers=headers,
        json={"new_status": STATUS_HR_REVIEW_PENDING, "remarks": "Reopen."},
    )
    assert response.status_code == 200
    body2 = response.json()
    assert body2["is_blacklisted"] is False


def test_change_status_service_unit(db_session: Session, seed_auth):
    """Service-level test bypassing the API, exercising the FSM directly."""
    superadmin = seed_auth["users"]["superadmin@pug.example.com"]
    job = _make_job(db_session)
    candidate = Candidate(full_name="X", source="manual_upload")
    db_session.add(candidate)
    db_session.flush()
    app = CandidateJobApplication(candidate=candidate, job_opening=job, status=STATUS_CV_RECEIVED)
    db_session.add(app)
    db_session.flush()

    # Direct forward transition
    result = change_status(
        db_session,
        application=app,
        new_status=STATUS_HR_REVIEW_PENDING,
        actor=superadmin,
        remarks="routing",
    )
    assert result.new_status == STATUS_HR_REVIEW_PENDING
    assert result.previous_status == STATUS_CV_RECEIVED
    assert result.history.remarks == "routing"

    # Invalid transition
    with pytest.raises(InvalidTransitionError):
        change_status(
            db_session,
            application=app,
            new_status=STATUS_JOINED,
            actor=superadmin,
        )

    # Missing rejection reason
    with pytest.raises(MissingReasonError):
        change_status(
            db_session,
            application=app,
            new_status=STATUS_REJECTED,
            actor=superadmin,
        )

    # Blacklist without approval
    with pytest.raises(MissingReasonError):
        change_status(
            db_session,
            application=app,
            new_status=STATUS_BLACKLISTED,
            actor=superadmin,
        )

    # Non-superuser blacklist attempt
    hr_user = seed_auth["users"]["hr@pug.example.com"]
    with pytest.raises(PermissionDeniedError):
        change_status(
            db_session,
            application=app,
            new_status=STATUS_BLACKLISTED,
            actor=hr_user,
            blacklist_approval="MD approved",
        )
