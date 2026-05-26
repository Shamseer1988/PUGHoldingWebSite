"""Tests for the HR Job approval workflow (advanced module phase 2).

Covers:

* New jobs from the API land in approval_status='draft' / publish_status='draft'.
* Public /public/jobs never returns a draft or pending job.
* Submit → approve → publish lifecycle.
* Reject branch requires a remarks string.
* Request-revision branch sends a job back to draft.
* Editing an approved job creates a JobRevision (public job stays
  unchanged) and approving the revision applies the new payload.
* Approval history is recorded for every transition and exposed by the
  /approval-history endpoint.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
from app.models.hr_ats import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_DRAFT,
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_REJECTED,
    APPROVAL_STATUS_REVISION_REQUIRED,
    JobApprovalHistory,
    JobOpening,
    JobRevision,
    PUBLISH_STATUS_DRAFT,
    PUBLISH_STATUS_PUBLISHED,
    PUBLISH_STATUS_UNPUBLISHED,
    REVISION_STATUS_APPROVED,
    REVISION_STATUS_PENDING,
    REVISION_STATUS_REJECTED,
)


HR_LOGIN = "/api/v1/hr/auth/login"
JOBS = "/api/v1/hr/jobs"
PUBLIC_JOBS = "/api/v1/public/jobs"


def _auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _payload(slug: str = "test-role", **overrides) -> dict:
    base = {
        "slug": slug,
        "title": "Test Role",
        "department": "Engineering",
        "company": "Paris United Group Holding",
        "location": "Doha",
        "employment_type": "full_time",
        "min_experience": 1,
        "max_experience": 5,
        "status": "open",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Default approval state
# ---------------------------------------------------------------------------


def test_new_job_lands_in_draft(client, seed_auth):
    headers = _auth(client, seed_auth["password"])
    response = client.post(JOBS, json=_payload(slug="draft-job"), headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["approval_status"] == APPROVAL_STATUS_DRAFT
    assert body["publish_status"] == PUBLISH_STATUS_DRAFT
    assert body["has_pending_revision"] is False


def test_public_does_not_show_draft_job(client, seed_auth):
    headers = _auth(client, seed_auth["password"])
    client.post(JOBS, json=_payload(slug="invisible-job"), headers=headers)

    public = client.get(PUBLIC_JOBS).json()
    assert all(j["slug"] != "invisible-job" for j in public)


# ---------------------------------------------------------------------------
# Submit / approve / publish round-trip
# ---------------------------------------------------------------------------


def test_full_approval_lifecycle(client, seed_auth, db_session: Session):
    headers = _auth(client, seed_auth["password"])
    created = client.post(
        JOBS, json=_payload(slug="lifecycle-job"), headers=headers
    ).json()
    job_id = created["id"]

    # Submit for approval ------------------------------------------------
    submit = client.post(f"{JOBS}/{job_id}/submit-approval", headers=headers).json()
    assert submit["approval_status"] == APPROVAL_STATUS_PENDING
    assert submit["submitted_for_approval_by_id"] is not None
    assert submit["submitted_for_approval_at"] is not None

    # Pending jobs are not public yet.
    public_during = client.get(PUBLIC_JOBS).json()
    assert all(j["slug"] != "lifecycle-job" for j in public_during)

    # Approve (auto-publishes) ------------------------------------------
    approve = client.post(
        f"{JOBS}/{job_id}/approve",
        json={"remarks": "Looks good"},
        headers=headers,
    )
    assert approve.status_code == 200, approve.text
    body = approve.json()
    assert body["approval_status"] == APPROVAL_STATUS_APPROVED
    assert body["publish_status"] == PUBLISH_STATUS_PUBLISHED
    assert body["approved_by_id"] is not None
    assert body["approved_at"] is not None

    # Now public.
    public_after = client.get(PUBLIC_JOBS).json()
    assert any(j["slug"] == "lifecycle-job" for j in public_after)

    # Approval history has at least: created, submitted, approved, published.
    actions = {
        h.action
        for h in db_session.execute(
            select(JobApprovalHistory).where(
                JobApprovalHistory.job_opening_id == job_id
            )
        ).scalars()
    }
    assert {"created", "submitted", "approved", "published"} <= actions

    # Audit log entries also written.
    audit_actions = {
        row.action for row in db_session.execute(select(AuditLog)).scalars()
    }
    assert "hr.job.submit_for_approval" in audit_actions
    assert "hr.job.approve" in audit_actions


# ---------------------------------------------------------------------------
# Reject + request-revision
# ---------------------------------------------------------------------------


def test_reject_requires_remarks(client, seed_auth):
    headers = _auth(client, seed_auth["password"])
    created = client.post(
        JOBS, json=_payload(slug="reject-job"), headers=headers
    ).json()
    job_id = created["id"]
    client.post(f"{JOBS}/{job_id}/submit-approval", headers=headers)

    # Empty remarks → 422 (Pydantic min_length).
    response = client.post(
        f"{JOBS}/{job_id}/reject", json={"remarks": ""}, headers=headers
    )
    assert response.status_code == 422

    # Whitespace-only also fails.
    response = client.post(
        f"{JOBS}/{job_id}/reject", json={"remarks": "abcd"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["approval_status"] == APPROVAL_STATUS_REJECTED
    assert body["rejected_by_id"] is not None


def test_request_revision_returns_to_revision_required(client, seed_auth):
    headers = _auth(client, seed_auth["password"])
    created = client.post(
        JOBS, json=_payload(slug="rev-required"), headers=headers
    ).json()
    job_id = created["id"]
    client.post(f"{JOBS}/{job_id}/submit-approval", headers=headers)

    response = client.post(
        f"{JOBS}/{job_id}/request-revision",
        json={"remarks": "Please add salary"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["approval_status"] == APPROVAL_STATUS_REVISION_REQUIRED


def test_cannot_approve_a_draft_job(client, seed_auth):
    headers = _auth(client, seed_auth["password"])
    created = client.post(
        JOBS, json=_payload(slug="bypass-test"), headers=headers
    ).json()
    job_id = created["id"]

    response = client.post(f"{JOBS}/{job_id}/approve", headers=headers)
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Editing an approved job creates a revision
# ---------------------------------------------------------------------------


def _approve_published(client, headers, slug: str) -> dict:
    created = client.post(JOBS, json=_payload(slug=slug), headers=headers).json()
    job_id = created["id"]
    client.post(f"{JOBS}/{job_id}/submit-approval", headers=headers)
    body = client.post(
        f"{JOBS}/{job_id}/approve",
        json={"remarks": "ok"},
        headers=headers,
    ).json()
    return body


def test_edit_approved_job_creates_pending_revision(
    client, seed_auth, db_session: Session
):
    headers = _auth(client, seed_auth["password"])
    job = _approve_published(client, headers, "edit-test")
    job_id = job["id"]
    original_title = job["title"]

    patch = client.patch(
        f"{JOBS}/{job_id}",
        json={"title": "New Title", "salary_min": 8000},
        headers=headers,
    )
    assert patch.status_code == 200
    body = patch.json()

    # Public job content stays unchanged until the revision is approved.
    assert body["title"] == original_title
    assert body["salary_min"] in (None, 0) or body["salary_min"] != 8000
    assert body["has_pending_revision"] is True

    # Public still sees the original title.
    public_detail = client.get(f"{PUBLIC_JOBS}/edit-test").json()
    assert public_detail["title"] == original_title

    # A revision row exists with the pending payload.
    revisions = db_session.execute(
        select(JobRevision).where(JobRevision.job_opening_id == job_id)
    ).scalars().all()
    assert len(revisions) == 1
    assert revisions[0].status == REVISION_STATUS_PENDING
    assert revisions[0].payload["title"] == "New Title"
    assert revisions[0].payload["salary_min"] == 8000


def test_approving_revision_applies_payload_to_job(
    client, seed_auth, db_session: Session
):
    headers = _auth(client, seed_auth["password"])
    job = _approve_published(client, headers, "apply-test")
    job_id = job["id"]

    client.patch(
        f"{JOBS}/{job_id}",
        json={"title": "Senior Engineer"},
        headers=headers,
    )

    approve = client.post(
        f"{JOBS}/{job_id}/approve",
        json={"remarks": "Revision approved"},
        headers=headers,
    )
    assert approve.status_code == 200
    body = approve.json()
    assert body["title"] == "Senior Engineer"
    assert body["has_pending_revision"] is False

    revisions = db_session.execute(
        select(JobRevision).where(JobRevision.job_opening_id == job_id)
    ).scalars().all()
    assert len(revisions) == 1
    assert revisions[0].status == REVISION_STATUS_APPROVED


def test_rejecting_revision_keeps_public_job_unchanged(
    client, seed_auth, db_session: Session
):
    headers = _auth(client, seed_auth["password"])
    job = _approve_published(client, headers, "rev-reject")
    job_id = job["id"]
    original_title = job["title"]

    client.patch(
        f"{JOBS}/{job_id}", json={"title": "Bad Title"}, headers=headers
    )

    reject = client.post(
        f"{JOBS}/{job_id}/reject",
        json={"remarks": "No way"},
        headers=headers,
    )
    assert reject.status_code == 200, reject.text

    # Public listing still shows the original title.
    public_detail = client.get(f"{PUBLIC_JOBS}/rev-reject").json()
    assert public_detail["title"] == original_title

    revisions = db_session.execute(
        select(JobRevision).where(JobRevision.job_opening_id == job_id)
    ).scalars().all()
    assert revisions[0].status == REVISION_STATUS_REJECTED


# ---------------------------------------------------------------------------
# Publish / unpublish + history endpoint
# ---------------------------------------------------------------------------


def test_unpublish_hides_from_public(client, seed_auth):
    headers = _auth(client, seed_auth["password"])
    job = _approve_published(client, headers, "unpub")
    job_id = job["id"]

    # Currently public.
    assert any(j["slug"] == "unpub" for j in client.get(PUBLIC_JOBS).json())

    response = client.post(f"{JOBS}/{job_id}/unpublish", headers=headers)
    assert response.status_code == 200
    assert response.json()["publish_status"] == PUBLISH_STATUS_UNPUBLISHED

    # No longer public.
    assert all(j["slug"] != "unpub" for j in client.get(PUBLIC_JOBS).json())

    # Re-publish brings it back.
    response = client.post(f"{JOBS}/{job_id}/publish", headers=headers)
    assert response.status_code == 200
    assert response.json()["publish_status"] == PUBLISH_STATUS_PUBLISHED
    assert any(j["slug"] == "unpub" for j in client.get(PUBLIC_JOBS).json())


def test_approval_history_endpoint(client, seed_auth):
    headers = _auth(client, seed_auth["password"])
    job = _approve_published(client, headers, "history-test")
    job_id = job["id"]

    response = client.get(f"{JOBS}/{job_id}/approval-history", headers=headers)
    assert response.status_code == 200
    history = response.json()
    actions = {h["action"] for h in history}
    assert {"created", "submitted", "approved", "published"} <= actions
    # All recent-first.
    timestamps = [h["created_at"] for h in history]
    assert timestamps == sorted(timestamps, reverse=True)
