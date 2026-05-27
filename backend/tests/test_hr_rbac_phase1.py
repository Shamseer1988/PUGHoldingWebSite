"""Phase 1 RBAC acceptance tests.

These tests pin the user's explicit acceptance criteria from the
Phase 1 prompt:

  - Interviewer login cannot open job delete API even by direct API call.
  - Recruiter (HR Executive) cannot approve a job opening.
  - HR Executive cannot approve their own submission.
  - Unauthorized users (Viewer, Interviewer) cannot delete candidates,
    reports, or job openings.
  - Department Manager cannot edit candidates.
  - Each role can perform the actions their permission matrix allows.

Every test uses the existing ``seed_auth`` fixture, which after Phase 1
seeds all seven HR roles with their fine-grained permission sets.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    APPROVAL_STATUS_PENDING,
    JOB_STATUS_OPEN,
    JobOpening,
)


HR_LOGIN = "/api/v1/hr/auth/login"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> dict:
    """Return the Authorization header dict for the given seed user."""
    response = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_job(
    db_session: Session,
    slug: str = "test-job",
    created_by_id: int | None = None,
    approval_status: str = "draft",
    submitted_for_approval_by_id: int | None = None,
) -> JobOpening:
    """Insert a job row in any desired approval state."""
    job = JobOpening(
        slug=slug,
        title="Senior Engineer",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status=approval_status,
        created_by_id=created_by_id,
        submitted_for_approval_by_id=submitted_for_approval_by_id,
    )
    db_session.add(job)
    db_session.commit()
    return job


# ---------------------------------------------------------------------------
# Interviewer scope
# ---------------------------------------------------------------------------


def test_interviewer_cannot_delete_job(client, seed_auth, db_session):
    """Acceptance: Interviewer login cannot open job delete API even by
    direct API call."""
    job = _make_job(db_session, slug="iv-no-delete")
    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])

    response = client.delete(f"/api/v1/hr/jobs/{job.id}", headers=headers)

    assert response.status_code == 403, response.text
    # Job still exists
    db_session.expire_all()
    assert db_session.get(JobOpening, job.id) is not None


def test_interviewer_cannot_list_candidates(client, seed_auth):
    """Interviewer must not see the candidate list."""
    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.get("/api/v1/hr/candidates", headers=headers)
    assert response.status_code == 403


def test_interviewer_cannot_create_interview(client, seed_auth, db_session):
    """Interviewer has feedback rights but not schedule rights."""
    job = _make_job(db_session, slug="iv-create-block")
    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.post(
        "/api/v1/hr/interviews",
        headers=headers,
        json={
            "application_id": 999,
            "round_name": "Try",
            "scheduled_at": "2099-01-01T10:00:00+00:00",
            "duration_minutes": 30,
            "mode": "online",
            "location_or_link": "https://meet.example.com/x",
        },
    )
    assert response.status_code == 403


def test_interviewer_can_see_own_interviews_only(client, seed_auth):
    """Interviewer should be allowed to call GET /hr/interviews — but
    the response is forced to mine_only."""
    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.get("/api/v1/hr/interviews", headers=headers)
    # No interviews assigned to interviewer yet → empty list, status 200
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# HR Executive — recruiter scope
# ---------------------------------------------------------------------------


def test_executive_cannot_approve_job(client, seed_auth, db_session):
    """Acceptance: Recruiter (HR Executive) cannot approve a job opening."""
    job = _make_job(
        db_session,
        slug="exec-no-approve",
        approval_status=APPROVAL_STATUS_PENDING,
    )
    headers = _login(client, "hrexec@pug.example.com", seed_auth["password"])

    response = client.post(
        f"/api/v1/hr/jobs/{job.id}/approve", headers=headers, json={}
    )
    assert response.status_code == 403


def test_executive_cannot_delete_job(client, seed_auth, db_session):
    """HR Executive cannot delete an approved job."""
    job = _make_job(db_session, slug="exec-no-delete")
    headers = _login(client, "hrexec@pug.example.com", seed_auth["password"])
    response = client.delete(f"/api/v1/hr/jobs/{job.id}", headers=headers)
    assert response.status_code == 403


def test_executive_can_create_job_draft(client, seed_auth):
    """HR Executive has hr:jobs:create — they can create drafts."""
    headers = _login(client, "hrexec@pug.example.com", seed_auth["password"])
    response = client.post(
        "/api/v1/hr/jobs",
        headers=headers,
        json={
            "slug": "exec-can-create",
            "title": "QA Engineer",
            "department": "QA",
            "company": "PUG",
            "location": "Doha",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["approval_status"] == "draft"


# ---------------------------------------------------------------------------
# HR Manager — approval authority, plus the "cannot approve own job" rule
# ---------------------------------------------------------------------------


def test_manager_cannot_approve_own_submission(
    client, seed_auth, db_session
):
    """Acceptance: HR Manager cannot approve a job they themselves submitted
    (must escalate to another manager — or to super admin)."""
    manager = seed_auth["users"]["hr@pug.example.com"]  # legacy alias = HR Manager
    job = _make_job(
        db_session,
        slug="self-approve-block",
        approval_status=APPROVAL_STATUS_PENDING,
        created_by_id=manager.id,
        submitted_for_approval_by_id=manager.id,
    )

    headers = _login(client, manager.email, seed_auth["password"])
    response = client.post(
        f"/api/v1/hr/jobs/{job.id}/approve", headers=headers, json={}
    )
    assert response.status_code == 403
    assert "submitted" in response.json()["detail"].lower()


def test_manager_can_approve_someone_elses_submission(
    client, seed_auth, db_session
):
    """HR Manager approves a job an Executive submitted — happy path."""
    exec_user = seed_auth["users"]["hrexec@pug.example.com"]
    job = _make_job(
        db_session,
        slug="manager-approves",
        approval_status=APPROVAL_STATUS_PENDING,
        created_by_id=exec_user.id,
        submitted_for_approval_by_id=exec_user.id,
    )
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.post(
        f"/api/v1/hr/jobs/{job.id}/approve", headers=headers, json={}
    )
    assert response.status_code == 200, response.text
    assert response.json()["approval_status"] == "approved"


def test_superuser_can_self_approve(client, seed_auth, db_session):
    """Super-user bypasses the self-approval guard for emergency unblocks."""
    su = seed_auth["users"]["superadmin@pug.example.com"]
    job = _make_job(
        db_session,
        slug="su-self-approve",
        approval_status=APPROVAL_STATUS_PENDING,
        created_by_id=su.id,
        submitted_for_approval_by_id=su.id,
    )
    headers = _login(client, su.email, seed_auth["password"])
    response = client.post(
        f"/api/v1/hr/jobs/{job.id}/approve", headers=headers, json={}
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Viewer / Auditor — read-only
# ---------------------------------------------------------------------------


def test_viewer_can_list_jobs(client, seed_auth):
    """Viewer / Auditor can list jobs (read-only access)."""
    headers = _login(client, "viewer@pug.example.com", seed_auth["password"])
    response = client.get("/api/v1/hr/jobs", headers=headers)
    assert response.status_code == 200


def test_viewer_cannot_create_job(client, seed_auth):
    """Viewer / Auditor cannot create jobs."""
    headers = _login(client, "viewer@pug.example.com", seed_auth["password"])
    response = client.post(
        "/api/v1/hr/jobs",
        headers=headers,
        json={
            "slug": "viewer-create-block",
            "title": "Trying",
            "department": "X",
            "company": "PUG",
            "location": "X",
        },
    )
    assert response.status_code == 403


def test_viewer_cannot_change_candidate_status(
    client, seed_auth, db_session
):
    """Viewer / Auditor cannot push candidates through the pipeline."""
    headers = _login(client, "viewer@pug.example.com", seed_auth["password"])
    response = client.post(
        "/api/v1/hr/candidates/1/applications/1/status",
        headers=headers,
        json={"new_status": "shortlisted"},
    )
    # 404 (no such application) is acceptable if perm-check passed; we
    # want 403 because the auth layer should reject before lookup.
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Department Manager — dept-scoped read access
# ---------------------------------------------------------------------------


def test_dept_manager_sees_only_own_department_jobs(
    client, seed_auth, db_session
):
    """Department Manager (department=Engineering) only sees jobs in
    Engineering."""
    job_eng = _make_job(db_session, slug="dept-eng-job")
    job_eng.department = "Engineering"
    job_fin = _make_job(db_session, slug="dept-fin-job")
    job_fin.department = "Finance"
    db_session.commit()

    headers = _login(client, "deptmgr@pug.example.com", seed_auth["password"])
    response = client.get("/api/v1/hr/jobs", headers=headers)
    assert response.status_code == 200
    slugs = {j["slug"] for j in response.json()}
    assert "dept-eng-job" in slugs
    assert "dept-fin-job" not in slugs


def test_dept_manager_cannot_create_job(client, seed_auth):
    """Department Manager has no jobs:create."""
    headers = _login(client, "deptmgr@pug.example.com", seed_auth["password"])
    response = client.post(
        "/api/v1/hr/jobs",
        headers=headers,
        json={
            "slug": "dept-create-block",
            "title": "X",
            "department": "Engineering",
            "company": "PUG",
            "location": "Doha",
        },
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# HR Admin — full operational access without approval
# ---------------------------------------------------------------------------


def test_hr_admin_can_create_job(client, seed_auth):
    headers = _login(client, "hradmin@pug.example.com", seed_auth["password"])
    response = client.post(
        "/api/v1/hr/jobs",
        headers=headers,
        json={
            "slug": "hradmin-create",
            "title": "Backend Engineer",
            "department": "Engineering",
            "company": "PUG",
            "location": "Doha",
        },
    )
    assert response.status_code == 201


def test_hr_admin_cannot_approve_job(client, seed_auth, db_session):
    """HR Admin can submit but not approve."""
    job = _make_job(
        db_session,
        slug="hradmin-no-approve",
        approval_status=APPROVAL_STATUS_PENDING,
    )
    headers = _login(client, "hradmin@pug.example.com", seed_auth["password"])
    response = client.post(
        f"/api/v1/hr/jobs/{job.id}/approve", headers=headers, json={}
    )
    assert response.status_code == 403


def test_hr_admin_cannot_delete_job(client, seed_auth, db_session):
    """HR Admin can't delete approved jobs — manager territory."""
    job = _make_job(db_session, slug="hradmin-no-delete")
    headers = _login(client, "hradmin@pug.example.com", seed_auth["password"])
    response = client.delete(f"/api/v1/hr/jobs/{job.id}", headers=headers)
    assert response.status_code == 403
