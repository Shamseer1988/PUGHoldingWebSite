"""Integration tests for the Phase 9 HR Job CRUD endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
from app.models.hr_ats import (
    JOB_STATUS_CLOSED,
    JOB_STATUS_ON_HOLD,
    JOB_STATUS_OPEN,
    JobOpening,
)


HR_LOGIN = "/api/v1/hr/auth/login"
ADMIN_LOGIN = "/api/v1/admin/auth/login"
JOBS = "/api/v1/hr/jobs"


def _hr_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _payload(**overrides) -> dict:
    base = {
        "slug": "test-role",
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
# Scope guarding
# ---------------------------------------------------------------------------


def test_jobs_endpoint_requires_hr_scope(client, seed_auth):
    # Website admin token must be rejected.
    admin_login = client.post(
        ADMIN_LOGIN,
        json={"email": "webadmin@pug.example.com", "password": seed_auth["password"]},
    )
    admin_token = admin_login.json()["access_token"]

    for path in [JOBS, f"{JOBS}/1"]:
        response = client.get(
            path, headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 403

    # Write endpoints also reject the wrong scope.
    response = client.post(
        f"{JOBS}/1/close", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 403


def test_jobs_endpoint_requires_authentication(client):
    assert client.get(JOBS).status_code == 401


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_create_list_get_round_trip(client, seed_auth, db_session: Session):
    headers = _hr_auth(client, seed_auth["password"])
    response = client.post(JOBS, json=_payload(), headers=headers)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["slug"] == "test-role"
    assert created["status"] == "open"
    assert created["created_by_id"] is not None

    listing = client.get(JOBS, headers=headers).json()
    assert any(j["slug"] == "test-role" for j in listing)

    single = client.get(f"{JOBS}/{created['id']}", headers=headers).json()
    assert single["title"] == "Test Role"

    audit = [
        row.action
        for row in db_session.execute(select(AuditLog)).scalars()
    ]
    assert "hr.job.create" in audit


def test_create_rejects_duplicate_slug(client, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    assert client.post(JOBS, json=_payload(slug="dup"), headers=headers).status_code == 201
    dup = client.post(JOBS, json=_payload(slug="dup"), headers=headers)
    assert dup.status_code == 409


def test_update_changes_fields_and_audits(client, seed_auth, db_session: Session):
    headers = _hr_auth(client, seed_auth["password"])
    created = client.post(JOBS, json=_payload(), headers=headers).json()

    patch = client.patch(
        f"{JOBS}/{created['id']}",
        json={"title": "Renamed", "salary_min": 5000},
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["title"] == "Renamed"
    assert patch.json()["salary_min"] == 5000

    audit_actions = [
        row.action for row in db_session.execute(select(AuditLog)).scalars()
    ]
    assert "hr.job.update" in audit_actions


# ---------------------------------------------------------------------------
# Transitions: close / reopen / hold
# ---------------------------------------------------------------------------


def test_close_sets_status_and_closed_at(client, seed_auth, db_session: Session):
    headers = _hr_auth(client, seed_auth["password"])
    created = client.post(JOBS, json=_payload(), headers=headers).json()
    job_id = created["id"]

    closed = client.post(f"{JOBS}/{job_id}/close", headers=headers)
    assert closed.status_code == 200
    body = closed.json()
    assert body["status"] == JOB_STATUS_CLOSED
    assert body["closed_at"] is not None

    audit_actions = [
        row.action for row in db_session.execute(select(AuditLog)).scalars()
    ]
    assert "hr.job.close" in audit_actions


def test_reopen_clears_closed_at(client, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    created = client.post(JOBS, json=_payload(), headers=headers).json()
    job_id = created["id"]

    client.post(f"{JOBS}/{job_id}/close", headers=headers)
    reopened = client.post(f"{JOBS}/{job_id}/reopen", headers=headers)
    assert reopened.status_code == 200
    body = reopened.json()
    assert body["status"] == JOB_STATUS_OPEN
    assert body["closed_at"] is None


def test_hold_transitions_to_on_hold(client, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    created = client.post(JOBS, json=_payload(), headers=headers).json()
    job_id = created["id"]

    held = client.post(f"{JOBS}/{job_id}/hold", headers=headers)
    assert held.status_code == 200
    assert held.json()["status"] == JOB_STATUS_ON_HOLD


def test_close_is_idempotent(client, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    created = client.post(JOBS, json=_payload(), headers=headers).json()
    job_id = created["id"]

    first = client.post(f"{JOBS}/{job_id}/close", headers=headers).json()
    second = client.post(f"{JOBS}/{job_id}/close", headers=headers).json()
    assert first["closed_at"] is not None
    assert second["status"] == JOB_STATUS_CLOSED


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_list_filters(client, seed_auth, db_session: Session):
    db_session.add_all(
        [
            JobOpening(
                slug="eng-a", title="Engineer A", department="Engineering",
                company="Paris United Group Holding", location="Doha",
                status=JOB_STATUS_OPEN,
            ),
            JobOpening(
                slug="sales-a", title="Sales A", department="Sales",
                company="Paris Food International", location="Doha",
                status=JOB_STATUS_OPEN,
            ),
            JobOpening(
                slug="eng-closed", title="Engineer Closed", department="Engineering",
                company="Paris United Group Holding", location="Doha",
                status=JOB_STATUS_CLOSED,
            ),
        ]
    )
    db_session.commit()

    headers = _hr_auth(client, seed_auth["password"])

    by_status = client.get(f"{JOBS}?status=open", headers=headers).json()
    assert {j["slug"] for j in by_status} == {"eng-a", "sales-a"}

    by_dept = client.get(f"{JOBS}?department=Engineering", headers=headers).json()
    assert {j["slug"] for j in by_dept} == {"eng-a", "eng-closed"}

    by_search = client.get(f"{JOBS}?q=sales", headers=headers).json()
    assert {j["slug"] for j in by_search} == {"sales-a"}


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_removes_row(client, seed_auth, db_session: Session):
    headers = _hr_auth(client, seed_auth["password"])
    created = client.post(JOBS, json=_payload(), headers=headers).json()

    response = client.delete(f"{JOBS}/{created['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"{JOBS}/{created['id']}", headers=headers).status_code == 404
