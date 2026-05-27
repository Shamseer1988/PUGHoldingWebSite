"""Phase 8 — Soft delete / archive + audit reason capture.

Pins:
  * POST /hr/jobs/{id}/archive sets is_archived + archive_reason +
    archived_by/at; gated on hr:jobs:delete; rejects 409 if already
    archived.
  * Archived jobs hidden from default list, surfaced with
    ?include_archived=true.
  * POST /hr/jobs/{id}/unarchive clears the audit cluster.
  * Same shape for /hr/candidates/{id}/archive + unarchive (gated on
    hr:candidates:delete).
  * Hard DELETE /hr/jobs/{id} accepts an optional reason that lands in
    the audit log details.
  * HR Executive / Interviewer cannot archive (no delete-class perm).
  * Audit log captures the reason on every transition.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    Candidate,
    CandidateJobApplication,
    JobOpening,
)


HR_LOGIN = "/api/v1/hr/auth/login"


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_job(db_session: Session, slug: str = "p8-job") -> JobOpening:
    job = JobOpening(
        slug=slug,
        title="Phase 8 Engineer",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
    )
    db_session.add(job)
    db_session.commit()
    return job


def _make_candidate(db_session: Session, name: str = "P8 Candidate") -> Candidate:
    cand = Candidate(full_name=name, email=f"{name.replace(' ', '').lower()}@example.com")
    db_session.add(cand)
    db_session.commit()
    return cand


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


def test_archive_job_sets_audit_cluster(client, seed_auth, db_session: Session):
    job = _make_job(db_session, "p8-arch-job")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    response = client.post(
        f"/api/v1/hr/jobs/{job.id}/archive",
        headers=headers,
        json={"reason": "Headcount frozen for FY27."},
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    refreshed = db_session.get(JobOpening, job.id)
    assert refreshed.is_archived is True
    assert refreshed.archive_reason == "Headcount frozen for FY27."
    assert refreshed.archived_by_id is not None
    assert refreshed.archived_at is not None


def test_archive_job_double_archive_409(
    client, seed_auth, db_session: Session
):
    job = _make_job(db_session, "p8-double-arch")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    client.post(
        f"/api/v1/hr/jobs/{job.id}/archive",
        headers=headers,
        json={"reason": "First time."},
    )
    second = client.post(
        f"/api/v1/hr/jobs/{job.id}/archive",
        headers=headers,
        json={"reason": "Trying again."},
    )
    assert second.status_code == 409


def test_archive_reason_required(client, seed_auth, db_session: Session):
    job = _make_job(db_session, "p8-reason-required")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.post(
        f"/api/v1/hr/jobs/{job.id}/archive", headers=headers, json={}
    )
    # Pydantic rejects the missing required `reason` -> 422.
    assert response.status_code == 422


def test_archived_jobs_hidden_from_default_list(
    client, seed_auth, db_session: Session
):
    j1 = _make_job(db_session, "p8-visible")
    j2 = _make_job(db_session, "p8-hidden")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    client.post(
        f"/api/v1/hr/jobs/{j2.id}/archive",
        headers=headers,
        json={"reason": "Done with this one."},
    )

    listing = client.get("/api/v1/hr/jobs", headers=headers).json()
    slugs = {row["slug"] for row in listing}
    assert "p8-visible" in slugs
    assert "p8-hidden" not in slugs


def test_archived_jobs_surface_with_include_archived(
    client, seed_auth, db_session: Session
):
    j1 = _make_job(db_session, "p8-incl-v")
    j2 = _make_job(db_session, "p8-incl-h")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    client.post(
        f"/api/v1/hr/jobs/{j2.id}/archive",
        headers=headers,
        json={"reason": "Need this hidden."},
    )

    listing = client.get(
        "/api/v1/hr/jobs?include_archived=true", headers=headers
    ).json()
    slugs = {row["slug"] for row in listing}
    assert "p8-incl-v" in slugs
    assert "p8-incl-h" in slugs


def test_unarchive_job_clears_audit_cluster(
    client, seed_auth, db_session: Session
):
    job = _make_job(db_session, "p8-unarchive")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    client.post(
        f"/api/v1/hr/jobs/{job.id}/archive",
        headers=headers,
        json={"reason": "Will be back."},
    )
    response = client.post(
        f"/api/v1/hr/jobs/{job.id}/unarchive", headers=headers
    )
    assert response.status_code == 200
    db_session.expire_all()
    refreshed = db_session.get(JobOpening, job.id)
    assert refreshed.is_archived is False
    assert refreshed.archive_reason is None
    assert refreshed.archived_by_id is None
    assert refreshed.archived_at is None


def test_hr_executive_cannot_archive_job(
    client, seed_auth, db_session: Session
):
    job = _make_job(db_session, "p8-exec-blocked")
    headers = _login(client, "hrexec@pug.example.com", seed_auth["password"])
    response = client.post(
        f"/api/v1/hr/jobs/{job.id}/archive",
        headers=headers,
        json={"reason": "Trying to archive."},
    )
    assert response.status_code == 403


def test_interviewer_cannot_archive_job(client, seed_auth, db_session: Session):
    job = _make_job(db_session, "p8-iv-blocked")
    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.post(
        f"/api/v1/hr/jobs/{job.id}/archive",
        headers=headers,
        json={"reason": "x"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


def test_archive_candidate_sets_audit_cluster(
    client, seed_auth, db_session: Session
):
    cand = _make_candidate(db_session, "P8 ArchCand")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    response = client.post(
        f"/api/v1/hr/candidates/{cand.id}/archive",
        headers=headers,
        json={"reason": "Candidate joined a competitor."},
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    refreshed = db_session.get(Candidate, cand.id)
    assert refreshed.is_archived is True
    assert refreshed.archive_reason == "Candidate joined a competitor."
    assert refreshed.archived_by_id is not None


def test_candidate_archive_double_409(client, seed_auth, db_session: Session):
    cand = _make_candidate(db_session, "P8 Double")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    client.post(
        f"/api/v1/hr/candidates/{cand.id}/archive",
        headers=headers,
        json={"reason": "First."},
    )
    second = client.post(
        f"/api/v1/hr/candidates/{cand.id}/archive",
        headers=headers,
        json={"reason": "Again."},
    )
    assert second.status_code == 409


def test_candidate_unarchive(client, seed_auth, db_session: Session):
    cand = _make_candidate(db_session, "P8 Unarc")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    client.post(
        f"/api/v1/hr/candidates/{cand.id}/archive",
        headers=headers,
        json={"reason": "Initial."},
    )
    response = client.post(
        f"/api/v1/hr/candidates/{cand.id}/unarchive", headers=headers
    )
    assert response.status_code == 200
    db_session.expire_all()
    refreshed = db_session.get(Candidate, cand.id)
    assert refreshed.is_archived is False
    assert refreshed.archive_reason is None


def test_hr_executive_cannot_archive_candidate(
    client, seed_auth, db_session: Session
):
    cand = _make_candidate(db_session, "P8 ExecBlock")
    headers = _login(client, "hrexec@pug.example.com", seed_auth["password"])
    response = client.post(
        f"/api/v1/hr/candidates/{cand.id}/archive",
        headers=headers,
        json={"reason": "Trying."},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# DELETE accepts reason + records it in audit
# ---------------------------------------------------------------------------


def test_delete_job_records_reason_in_audit(
    client, seed_auth, db_session: Session
):
    job = _make_job(db_session, "p8-del-with-reason")
    job_id = job.id
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    # FastAPI's DELETE supports a JSON body when the endpoint declares
    # one. We use the standard client.delete and pass the body via
    # the request() escape hatch.
    response = client.request(
        "DELETE",
        f"/api/v1/hr/jobs/{job_id}",
        headers=headers,
        json={"reason": "Approved-but-cancelled HR Director decision."},
    )
    assert response.status_code == 204

    audit = db_session.execute(
        select(AuditLog).where(
            AuditLog.target_id == str(job_id),
            AuditLog.action == "hr.job.delete",
        )
    ).scalar_one()
    assert (
        audit.details.get("reason")
        == "Approved-but-cancelled HR Director decision."
    )
