"""Tests for the Super Admin recruitment-settings toggle + the job-approval
bypass it controls.

Covers:

* GET/PUT ``/admin/recruitment-settings`` is Super Admin only (a non-superuser
  admin is forbidden).
* Default (``job_approval_required=True``) keeps new jobs in draft.
* Flipping the global toggle off makes new jobs auto-approve + publish.
* A role granted ``hr:jobs:post_direct`` bypasses approval even while the
  global toggle is on; a superuser does NOT implicitly bypass.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import PERM_HR_JOBS_POST_DIRECT
from app.models.auth import Permission, Role


ADMIN_LOGIN = "/api/v1/admin/auth/login"
HR_LOGIN = "/api/v1/hr/auth/login"
SETTINGS = "/api/v1/admin/recruitment-settings"
JOBS = "/api/v1/hr/jobs"


def _admin_login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(ADMIN_LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _hr_login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _job_payload(slug: str) -> dict:
    return {
        "slug": slug,
        "title": "Role",
        "department": "Engineering",
        "company": "PUG",
        "location": "Doha",
    }


def test_get_settings_superuser_default(client, seed_auth):
    headers = _admin_login(client, "superadmin@pug.example.com", seed_auth["password"])
    resp = client.get(SETTINGS, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["job_approval_required"] is True


def test_settings_denied_for_non_superuser(client, seed_auth):
    headers = _admin_login(client, "webadmin@pug.example.com", seed_auth["password"])
    assert client.get(SETTINGS, headers=headers).status_code == 403
    put = client.put(SETTINGS, headers=headers, json={"job_approval_required": False})
    assert put.status_code == 403


def test_default_keeps_new_jobs_in_draft(client, seed_auth):
    headers = _hr_login(client, "hrexec@pug.example.com", seed_auth["password"])
    resp = client.post(JOBS, headers=headers, json=_job_payload("draft-default"))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["approval_status"] == "draft"
    assert body["publish_status"] == "draft"


def test_disabling_global_auto_publishes(client, seed_auth):
    admin = _admin_login(client, "superadmin@pug.example.com", seed_auth["password"])
    put = client.put(SETTINGS, headers=admin, json={"job_approval_required": False})
    assert put.status_code == 200, put.text
    assert put.json()["job_approval_required"] is False

    headers = _hr_login(client, "hrexec@pug.example.com", seed_auth["password"])
    resp = client.post(JOBS, headers=headers, json=_job_payload("auto-pub"))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["approval_status"] == "approved"
    assert body["publish_status"] == "published"


def test_per_role_post_direct_bypasses(client, seed_auth, db_session: Session):
    # Grant hr:jobs:post_direct to the HR Manager role; global stays ON.
    role = db_session.execute(
        select(Role).where(Role.name == "HR Manager")
    ).scalar_one()
    perm = db_session.execute(
        select(Permission).where(Permission.key == PERM_HR_JOBS_POST_DIRECT)
    ).scalar_one()
    if perm not in role.permissions:
        role.permissions.append(perm)
    db_session.commit()

    headers = _hr_login(client, "hr@pug.example.com", seed_auth["password"])
    resp = client.post(JOBS, headers=headers, json=_job_payload("mgr-direct"))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["approval_status"] == "approved"
    assert body["publish_status"] == "published"
