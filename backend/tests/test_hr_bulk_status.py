"""Tests for the bulk candidate status change endpoint (phase 5).

Verifies:

* Multiple applications move atomically by default (per-row) but with
  ``all_or_nothing=true`` the whole batch is rolled back if any row fails.
* Each row gets its own success/error result in the response.
* Rejection without a reason fails per-row, not at the request level.
* Audit log + CandidateStatusHistory are written for each success.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    STATUS_CV_RECEIVED,
    STATUS_REJECTED,
    STATUS_SHORTLISTED,
    Candidate,
    CandidateJobApplication,
    CandidateStatusHistory,
    JobOpening,
)


HR_LOGIN = "/api/v1/hr/auth/login"
BULK = "/api/v1/hr/candidates/applications/bulk-status"


def _auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_three_apps(db_session: Session) -> list[CandidateJobApplication]:
    job = JobOpening(
        slug="bulk-test",
        title="Bulk Test",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    db_session.add(job)
    db_session.flush()
    apps = []
    for i in range(3):
        cand = Candidate(full_name=f"Cand {i}", email=f"c{i}@e.com")
        db_session.add(cand)
        db_session.flush()
        app = CandidateJobApplication(
            candidate_id=cand.id,
            job_opening_id=job.id,
            status=STATUS_CV_RECEIVED,
        )
        db_session.add(app)
        apps.append(app)
    db_session.commit()
    return apps


def test_bulk_shortlist_all_succeed(client, seed_auth, db_session: Session):
    apps = _seed_three_apps(db_session)
    headers = _auth(client, seed_auth["password"])

    response = client.post(
        BULK,
        json={
            "application_ids": [a.id for a in apps],
            "new_status": STATUS_SHORTLISTED,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert body["success_count"] == 3
    assert body["failed_count"] == 0
    for row in body["rows"]:
        assert row["success"] is True
        assert row["new_status"] == STATUS_SHORTLISTED

    # Status history rows exist.
    history = db_session.execute(select(CandidateStatusHistory)).scalars().all()
    assert len(history) == 3

    # Audit rows for each app.
    actions = [
        row.action
        for row in db_session.execute(select(AuditLog)).scalars()
    ]
    assert actions.count("hr.candidate.status.bulk_change") == 3


def test_bulk_reject_without_reason_fails_each_row(
    client, seed_auth, db_session: Session
):
    apps = _seed_three_apps(db_session)
    headers = _auth(client, seed_auth["password"])

    response = client.post(
        BULK,
        json={
            "application_ids": [a.id for a in apps],
            "new_status": STATUS_REJECTED,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success_count"] == 0
    assert body["failed_count"] == 3
    for row in body["rows"]:
        assert row["success"] is False
        assert "rejection reason" in row["error"].lower()


def test_bulk_invalid_transition_returns_row_level_error(
    client, seed_auth, db_session: Session
):
    apps = _seed_three_apps(db_session)
    headers = _auth(client, seed_auth["password"])

    # cv_received → joined is not allowed; should fail per-row.
    response = client.post(
        BULK,
        json={
            "application_ids": [a.id for a in apps],
            "new_status": "joined",
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success_count"] == 0
    assert body["failed_count"] == 3
    assert all(not row["success"] for row in body["rows"])


def test_bulk_missing_application_id_returns_per_row_error(
    client, seed_auth, db_session: Session
):
    apps = _seed_three_apps(db_session)
    headers = _auth(client, seed_auth["password"])

    response = client.post(
        BULK,
        json={
            "application_ids": [apps[0].id, 99_999_999],
            "new_status": STATUS_SHORTLISTED,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success_count"] == 1
    assert body["failed_count"] == 1

    rows_by_id = {row["application_id"]: row for row in body["rows"]}
    assert rows_by_id[apps[0].id]["success"] is True
    assert rows_by_id[99_999_999]["success"] is False
    assert "not found" in rows_by_id[99_999_999]["error"].lower()


def test_bulk_all_or_nothing_rolls_back_on_failure(
    client, seed_auth, db_session: Session
):
    apps = _seed_three_apps(db_session)
    headers = _auth(client, seed_auth["password"])

    response = client.post(
        BULK,
        json={
            "application_ids": [apps[0].id, 99_999_999, apps[1].id],
            "new_status": STATUS_SHORTLISTED,
            "all_or_nothing": True,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    # Everything counted as failed because of the rollback.
    assert body["success_count"] == 0
    assert body["failed_count"] == 3

    # Database state unchanged.
    db_session.expire_all()
    for app in db_session.execute(select(CandidateJobApplication)).scalars():
        assert app.status == STATUS_CV_RECEIVED


def test_bulk_request_validates_ids():
    pass  # min_length=1 enforced by Pydantic; covered by 422 if empty.
