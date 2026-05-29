"""Phase 2 — Job Opening Approval Workflow tests.

Covers the new behavior layered on top of Phase 1's RBAC:

  * Denormalised audit columns populated:
      - request_revision  sets changes_requested_by_id / _at / _notes
      - publish           sets published_by_id / published_at
      - submit_for_approval clears changes_requested_*
  * Explicit revision approve / reject endpoints respect the
    hr:jobs:approve permission and the self-approval guard.
  * Revision approve applies the payload and clears active_revision_id.
  * Revision reject leaves the live job untouched.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_REVISION_REQUIRED,
    JobOpening,
    JobRevision,
    REVISION_STATUS_APPROVED,
    REVISION_STATUS_REJECTED,
)


HR_LOGIN = "/api/v1/hr/auth/login"
JOBS = "/api/v1/hr/jobs"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_published_job(client: TestClient, headers: dict, slug: str) -> dict:
    """Walk a job through draft -> submitted -> approved -> published."""
    created = client.post(
        JOBS,
        headers=headers,
        json={
            "slug": slug,
            "title": "Backend Engineer",
            "department": "Engineering",
            "company": "PUG",
            "location": "Doha",
        },
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]

    submit = client.post(f"{JOBS}/{job_id}/submit-approval", headers=headers)
    assert submit.status_code == 200, submit.text

    approve = client.post(f"{JOBS}/{job_id}/approve", json={}, headers=headers)
    assert approve.status_code == 200, approve.text
    return approve.json()


# ---------------------------------------------------------------------------
# Denormalised audit columns
# ---------------------------------------------------------------------------


def test_request_revision_populates_changes_requested_columns(
    client, seed_auth, db_session: Session
):
    """The denormalised audit columns are written when HR Manager hits
    request-revision so list views can sort/filter without joining."""
    superadmin_headers = _login(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    # Create + submit as super admin (avoids self-approval block when we
    # later request revision from a different account).
    created = client.post(
        JOBS,
        headers=superadmin_headers,
        json={
            "slug": "needs-changes",
            "title": "QA Engineer",
            "department": "QA",
            "company": "PUG",
            "location": "Doha",
        },
    )
    job_id = created.json()["id"]
    client.post(f"{JOBS}/{job_id}/submit-approval", headers=superadmin_headers)

    # Request revision as the HR Manager seed user.
    manager_headers = _login(
        client, "hr@pug.example.com", seed_auth["password"]
    )
    response = client.post(
        f"{JOBS}/{job_id}/request-revision",
        json={"remarks": "Tighten the JD."},
        headers=manager_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["approval_status"] == APPROVAL_STATUS_REVISION_REQUIRED
    assert body["changes_requested_by_id"] is not None
    assert body["changes_requested_at"] is not None
    assert body["changes_requested_notes"] == "Tighten the JD."


def test_publish_populates_published_columns(
    client, seed_auth, db_session: Session
):
    """publish endpoint records who published and when."""
    headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    job = _create_published_job(client, headers, "pub-audit")
    assert job["publish_status"] == "published"
    assert job["published_by_id"] is not None
    assert job["published_at"] is not None


def test_resubmitting_clears_changes_requested(
    client, seed_auth, db_session: Session
):
    """When an HR Executive addresses the changes and re-submits, the
    'changes_requested' note should be cleared so the next approval
    cycle starts fresh."""
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    created = client.post(
        JOBS,
        headers=su_headers,
        json={
            "slug": "resub-clear",
            "title": "QA Engineer",
            "department": "QA",
            "company": "PUG",
            "location": "Doha",
        },
    )
    job_id = created.json()["id"]
    client.post(f"{JOBS}/{job_id}/submit-approval", headers=su_headers)

    manager_headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    client.post(
        f"{JOBS}/{job_id}/request-revision",
        json={"remarks": "Add a salary band."},
        headers=manager_headers,
    )

    # Now re-submit. The changes_requested_* should be cleared.
    resubmit = client.post(
        f"{JOBS}/{job_id}/submit-approval", headers=su_headers
    )
    assert resubmit.status_code == 200
    body = resubmit.json()
    assert body["approval_status"] == "pending_approval"
    assert body["changes_requested_by_id"] is None
    assert body["changes_requested_at"] is None
    assert body["changes_requested_notes"] is None


# ---------------------------------------------------------------------------
# Explicit revision endpoints
# ---------------------------------------------------------------------------


def test_revision_approve_endpoint_applies_payload(
    client, seed_auth, db_session: Session
):
    """Phase 2 adds explicit POST /hr/jobs/{id}/revisions/{rev}/approve.
    Approving a revision applies its payload to the live job and marks
    the revision as approved."""
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    job = _create_published_job(client, su_headers, "rev-approve")
    job_id = job["id"]

    # Edit an approved job — creates a pending revision.
    client.patch(
        f"{JOBS}/{job_id}",
        headers=su_headers,
        json={"title": "Senior Backend Engineer"},
    )

    # Find the pending revision id via the GET endpoint.
    pending = client.get(
        f"{JOBS}/{job_id}/pending-revision", headers=su_headers
    )
    assert pending.status_code == 200
    rev_id = pending.json()["id"]

    # Approve the revision via the new explicit endpoint as HR Manager
    # (different user than the submitter to satisfy self-approval guard).
    manager_headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.post(
        f"{JOBS}/{job_id}/revisions/{rev_id}/approve",
        json={"remarks": "Looks fine."},
        headers=manager_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Senior Backend Engineer"
    assert body["has_pending_revision"] is False

    rev = db_session.get(JobRevision, rev_id)
    assert rev is not None
    assert rev.status == REVISION_STATUS_APPROVED


def test_revision_reject_endpoint_leaves_job_unchanged(
    client, seed_auth, db_session: Session
):
    """Rejecting a revision discards the payload — the public job stays
    on its original title."""
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    job = _create_published_job(client, su_headers, "rev-reject")
    job_id = job["id"]
    original_title = job["title"]

    client.patch(
        f"{JOBS}/{job_id}",
        headers=su_headers,
        json={"title": "NEW TITLE THAT SHOULD NEVER GO LIVE"},
    )
    rev_id = client.get(
        f"{JOBS}/{job_id}/pending-revision", headers=su_headers
    ).json()["id"]

    manager_headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.post(
        f"{JOBS}/{job_id}/revisions/{rev_id}/reject",
        json={"remarks": "Title change doesn't reflect the actual role."},
        headers=manager_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Live job kept the original title.
    assert body["title"] == original_title

    rev = db_session.get(JobRevision, rev_id)
    assert rev is not None
    assert rev.status == REVISION_STATUS_REJECTED


def test_revision_approve_blocks_self_approval(
    client, seed_auth, db_session: Session
):
    """A manager cannot approve a revision they themselves submitted."""
    manager_headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])

    # Create job as manager, get it published via super-admin so we can
    # then make a revision and have the manager try to self-approve.
    created = client.post(
        JOBS,
        headers=manager_headers,
        json={
            "slug": "self-revision",
            "title": "DevOps Engineer",
            "department": "Platform",
            "company": "PUG",
            "location": "Doha",
        },
    )
    job_id = created.json()["id"]
    client.post(f"{JOBS}/{job_id}/submit-approval", headers=manager_headers)
    # Approve as super-admin (super can self-approve, but here it's
    # a different account — manager is the submitter, super is approver).
    client.post(f"{JOBS}/{job_id}/approve", json={}, headers=su_headers)

    # Manager edits the now-approved job (creates a revision).
    client.patch(
        f"{JOBS}/{job_id}",
        headers=manager_headers,
        json={"title": "Senior DevOps Engineer"},
    )
    rev_id = client.get(
        f"{JOBS}/{job_id}/pending-revision", headers=manager_headers
    ).json()["id"]

    # Manager tries to approve their own revision → 403.
    response = client.post(
        f"{JOBS}/{job_id}/revisions/{rev_id}/approve",
        json={},
        headers=manager_headers,
    )
    assert response.status_code == 403


def test_revision_endpoints_require_approve_permission(
    client, seed_auth, db_session: Session
):
    """HR Executive (no jobs:approve) cannot use the revision endpoints."""
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    job = _create_published_job(client, su_headers, "rev-perm")
    job_id = job["id"]

    client.patch(
        f"{JOBS}/{job_id}", headers=su_headers, json={"title": "Edited"}
    )
    rev_id = client.get(
        f"{JOBS}/{job_id}/pending-revision", headers=su_headers
    ).json()["id"]

    exec_headers = _login(client, "hrexec@pug.example.com", seed_auth["password"])
    approve = client.post(
        f"{JOBS}/{job_id}/revisions/{rev_id}/approve",
        json={},
        headers=exec_headers,
    )
    assert approve.status_code == 403

    reject = client.post(
        f"{JOBS}/{job_id}/revisions/{rev_id}/reject",
        json={"remarks": "would block but no perm"},
        headers=exec_headers,
    )
    assert reject.status_code == 403
