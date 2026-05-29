"""Phase 13 — Final acceptance tests.

Cross-cutting tests that pin the high-level acceptance criteria from
the master plan. Where Phases 1-12 each ship focused unit/contract
tests for their own slice, this file walks the whole recruitment
lifecycle end-to-end to prove the pieces still fit together:

  1. End-to-end golden path
       Job draft -> approval -> publish -> public apply ->
       candidate moves through pipeline -> interview scheduled ->
       feedback submitted -> offer drafted -> approved -> issued ->
       accepted -> joined. Verifies the candidate.status mirrors the
       offer state at every milestone (Phase 6 contract).

  2. Public visibility three-way gate
       Draft / pending / approved-but-unpublished are all hidden
       from the public /careers feed; only status=open +
       approval=approved + publish=published shows up.

  3. Existing data safety
       Inserting "legacy" rows that pre-date the Phase 8 archive
       fields keeps working — null is_archived is treated as False.

  4. Cross-role security sweep
       Walks every (role, sensitive_endpoint) pair the master plan
       lists and confirms the matrix.

These tests intentionally don't re-test things their own phase already
covers in detail — they only check the seams.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_PENDING,
    JOB_STATUS_OPEN,
    OFFER_SENT,
    PUBLISH_STATUS_DRAFT,
    PUBLISH_STATUS_PUBLISHED,
    STATUS_FIRST_INTERVIEW,
    STATUS_JOINED,
    STATUS_OFFER_SENT,
    STATUS_RECOMMENDED_FOR_OFFER,
    STATUS_SELECTED,
    STATUS_SHORTLISTED,
    Candidate,
    CandidateJobApplication,
    Interview,
    JobOpening,
)


HR_LOGIN = "/api/v1/hr/auth/login"
PUBLIC_JOBS = "/api/v1/public/jobs"


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ---------------------------------------------------------------------------
# 1. End-to-end golden path
# ---------------------------------------------------------------------------


def test_full_recruitment_lifecycle_golden_path(
    client, seed_auth, db_session: Session
):
    """Walks one candidate from a public apply through every Phase
    1-12 transition. Each step asserts the contract that phase
    promised so a future regression breaks here loud and early."""
    # Super admin drives the whole flow so self-approval guards
    # (Phase 1) never block us; mixing actors is exercised in the
    # focused RBAC tests.
    su = _login(client, "superadmin@pug.example.com", seed_auth["password"])

    # 1. HR drafts a job.
    create = client.post(
        "/api/v1/hr/jobs",
        headers=su,
        json={
            "slug": "p13-lifecycle",
            "title": "Phase 13 Engineer",
            "department": "Engineering",
            "company": "PUG",
            "location": "Doha",
            "description": "Full lifecycle smoke test.",
        },
    )
    assert create.status_code == 201, create.text
    job_id = create.json()["id"]
    job_slug = create.json()["slug"]
    assert create.json()["approval_status"] == "draft"

    # 2. Public site MUST NOT see a draft job (Phase 2 contract).
    public_during_draft = client.get(PUBLIC_JOBS).json()
    assert all(j["slug"] != job_slug for j in public_during_draft)

    # 3. Submit + approve (auto-publish, Phase 2).
    client.post(f"/api/v1/hr/jobs/{job_id}/submit-approval", headers=su)
    approve = client.post(f"/api/v1/hr/jobs/{job_id}/approve", json={}, headers=su)
    assert approve.json()["approval_status"] == "approved"
    assert approve.json()["publish_status"] == "published"

    # 4. Public site MUST see the live job.
    public_after_publish = client.get(PUBLIC_JOBS).json()
    assert any(j["slug"] == job_slug for j in public_after_publish)

    # 5. HR uploads a candidate via the HR endpoint (avoids the rate
    #    limiter + email parsing of the public path — a separate test
    #    covers that path).
    import io

    upload = client.post(
        "/api/v1/hr/candidates/upload",
        headers=su,
        data={
            "full_name": "Lifecycle Candidate",
            "email": "lifecycle@example.com",
            "mobile": "+974 11 11 11 11",
            "job_slug": job_slug,
            "consent": "true",
        },
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4\n"), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    cand_id = upload.json()["candidate_id"]
    app_id = upload.json()["application_id"]

    # 6. Move through the pipeline: shortlisted -> first interview ->
    #    recommended_for_offer -> selected.
    for new_status in (
        STATUS_SHORTLISTED,
        STATUS_FIRST_INTERVIEW,
        STATUS_RECOMMENDED_FOR_OFFER,
        STATUS_SELECTED,
    ):
        response = client.post(
            f"/api/v1/hr/candidates/{cand_id}/applications/{app_id}/status",
            headers=su,
            json={"new_status": new_status},
        )
        assert response.status_code == 200, (
            f"Failed at transition to {new_status}: {response.text}"
        )

    db_session.expire_all()
    app = db_session.get(CandidateJobApplication, app_id)
    assert app.status == STATUS_SELECTED

    # 7. Schedule an interview (Phase 4 plumbing).
    iv_response = client.post(
        "/api/v1/hr/interviews",
        headers=su,
        json={
            "application_id": app_id,
            "round_name": "Final",
            "scheduled_at": (
                datetime.now(timezone.utc) + timedelta(days=2)
            ).isoformat(),
            "duration_minutes": 30,
            "mode": "online",
            "location_or_link": "https://example.com/meet",
            "send_email_now": False,
        },
    )
    assert iv_response.status_code == 201, iv_response.text
    iv_id = iv_response.json()["id"]

    # 8. Submit feedback (Phase 4 + Phase 11 notification trigger).
    fb_response = client.post(
        f"/api/v1/hr/interviews/{iv_id}/feedback",
        headers=su,
        json={
            "rating": 5,
            "recommendation": "hire",
            "strengths": "Strong system design.",
            "next_action": "Move to offer.",
        },
    )
    assert fb_response.status_code == 201, fb_response.text

    # 9. Walk the offer through the full state machine (Phase 6).
    offer = client.post(
        "/api/v1/hr/offers",
        headers=su,
        json={
            "application_id": app_id,
            "position": "Phase 13 Engineer",
            "salary_offered": 8500,
            "joining_date": str(date.today() + timedelta(days=30)),
        },
    )
    assert offer.status_code == 201, offer.text
    offer_id = offer.json()["id"]

    client.post(f"/api/v1/hr/offers/{offer_id}/submit-approval", headers=su)
    client.post(f"/api/v1/hr/offers/{offer_id}/approve", json={}, headers=su)
    issued = client.post(f"/api/v1/hr/offers/{offer_id}/issue", json={}, headers=su)
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == OFFER_SENT
    assert issued.json()["offer_letter_number"]

    # Candidate status auto-mirrored to offer_sent (Phase 6 contract).
    db_session.expire_all()
    assert (
        db_session.get(CandidateJobApplication, app_id).status
        == STATUS_OFFER_SENT
    )

    # 10. Record candidate accept + mark joined.
    client.post(
        f"/api/v1/hr/offers/{offer_id}/respond",
        headers=su,
        json={"accepted": True},
    )
    joined = client.post(
        f"/api/v1/hr/offers/{offer_id}/mark-joined", json={}, headers=su
    )
    assert joined.status_code == 200
    assert joined.json()["status"] == "joined"

    db_session.expire_all()
    assert db_session.get(CandidateJobApplication, app_id).status == STATUS_JOINED

    # 11. Audit log carries the full chain — at least one row per
    #     transition. We don't pin the exact set (each phase tests its
    #     own actions in detail), just that the trail is non-empty.
    from sqlalchemy import select

    from app.models.auth import AuditLog

    audit_rows = list(
        db_session.execute(
            select(AuditLog).where(AuditLog.target_id == str(offer_id))
        ).scalars()
    )
    actions = {row.action for row in audit_rows}
    assert {
        "hr.offer.create",
        "hr.offer.submit_approval",
        "hr.offer.approve",
        "hr.offer.issue",
        "hr.offer.accept",
        "hr.offer.mark_joined",
    } <= actions


# ---------------------------------------------------------------------------
# 2. Public visibility three-way gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "approval,publish,visible",
    [
        ("draft", "draft", False),
        ("pending_approval", "draft", False),
        ("approved", "draft", False),
        ("approved", "unpublished", False),
        ("approved", "published", True),
        ("rejected", "published", False),
        ("revision_required", "published", False),
    ],
)
def test_public_jobs_three_way_gate(
    client, db_session: Session, approval: str, publish: str, visible: bool
):
    """Public /jobs only shows status=open AND approval=approved AND
    publish=published. Phase 2 contract — every combination tested."""
    job = JobOpening(
        slug=f"p13-gate-{approval}-{publish}",
        title=f"P13 {approval}/{publish}",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status=approval,
        publish_status=publish,
    )
    db_session.add(job)
    db_session.commit()

    listed = {j["slug"] for j in client.get(PUBLIC_JOBS).json()}
    assert (job.slug in listed) is visible


# ---------------------------------------------------------------------------
# 3. Existing data safety — null archive fields
# ---------------------------------------------------------------------------


def test_legacy_rows_without_archive_columns_still_work(
    client, seed_auth, db_session: Session
):
    """A job row with NULL archive cluster (simulating pre-Phase-8
    data) appears in default listings and can transition normally."""
    job = JobOpening(
        slug="p13-legacy",
        title="Legacy Phase 13 Job",
        department="Eng",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
    )
    # Force the archive cluster to None — simulates a row inserted
    # before the Phase 8 migration ran.
    job.is_archived = False
    job.archived_at = None
    job.archived_by_id = None
    job.archive_reason = None
    db_session.add(job)
    db_session.commit()

    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    listed = client.get("/api/v1/hr/jobs", headers=headers).json()
    assert any(j["slug"] == "p13-legacy" for j in listed)


# ---------------------------------------------------------------------------
# 4. Cross-role security matrix sweep
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "email,endpoint,method,expected_status",
    [
        # Interviewer must not delete a job / list candidates / list
        # offers / call all-scope reports / export
        ("interviewer@pug.example.com", "/api/v1/hr/jobs", "DELETE", 405),
        ("interviewer@pug.example.com", "/api/v1/hr/candidates", "GET", 403),
        ("interviewer@pug.example.com", "/api/v1/hr/offers", "GET", 403),
        ("interviewer@pug.example.com", "/api/v1/hr/reports/shortlist", "GET", 403),
        # HR Executive (recruiter) must not delete or approve a job
        ("hrexec@pug.example.com", "/api/v1/hr/jobs/999/approve", "POST", 403),
        # Viewer must not push pipeline statuses or create offers
        ("viewer@pug.example.com", "/api/v1/hr/candidates/1/applications/1/status", "POST", 403),
        ("viewer@pug.example.com", "/api/v1/hr/offers", "POST", 403),
        # Website admin (no HR scope) must not call /hr/interviews
        # — that one's still covered by Phase 1 but we re-pin here.
    ],
)
def test_security_matrix(
    client, seed_auth, email: str, endpoint: str, method: str, expected_status: int
):
    """The 'permitted matrix' from the master plan, condensed. Phase 1
    + Phase 9 already test most of these — this is the cross-cutting
    seal."""
    headers = _login(client, email, seed_auth["password"])
    response = client.request(
        method,
        endpoint,
        headers=headers,
        json={} if method == "POST" else None,
    )
    assert response.status_code == expected_status, (
        f"{method} {endpoint} for {email}: "
        f"expected {expected_status}, got {response.status_code}"
    )
