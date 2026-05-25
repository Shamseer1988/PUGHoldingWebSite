"""Integration tests for the Phase 8 HR dashboard endpoint."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    AI_RECOMMENDED,
    INTERVIEW_MODE_ONLINE,
    INTERVIEW_SCHEDULED,
    JOB_STATUS_OPEN,
    OFFER_SENT,
    STATUS_CV_RECEIVED,
    STATUS_HR_REVIEW_PENDING,
    STATUS_REJECTED,
    STATUS_SHORTLISTED,
    Candidate,
    CandidateAIReview,
    CandidateJobApplication,
    Interview,
    JobOpening,
    OfferTracking,
)


HR_LOGIN = "/api/v1/hr/auth/login"
ADMIN_LOGIN = "/api/v1/admin/auth/login"
DASHBOARD = "/api/v1/hr/dashboard"
AUDIT = "/api/v1/hr/audit-logs"


def _hr_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Scope guarding
# ---------------------------------------------------------------------------


def test_dashboard_requires_hr_scope(client, seed_auth):
    # Website-admin token must be rejected.
    response = client.post(
        ADMIN_LOGIN,
        json={"email": "webadmin@pug.example.com", "password": seed_auth["password"]},
    )
    admin_token = response.json()["access_token"]

    rejected = client.get(
        DASHBOARD, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert rejected.status_code == 403


def test_dashboard_requires_authentication(client, seed_auth):
    assert client.get(DASHBOARD).status_code == 401


# ---------------------------------------------------------------------------
# Empty database — every count is 0 and lists are empty.
# ---------------------------------------------------------------------------


def test_dashboard_empty_state(client, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(DASHBOARD, headers=headers)
    assert response.status_code == 200, response.text

    body = response.json()
    assert all(stat["value"] == 0 for stat in body["stats"])
    assert all(stage["count"] == 0 for stage in body["pipeline_funnel"])
    assert body["applications_per_month"] == []
    assert body["candidates_by_job"] == []
    assert body["candidates_by_department"] == []
    assert body["pending_interviews"] == []
    assert body["pending_offers"] == []

    funnel_statuses = [s["status"] for s in body["pipeline_funnel"]]
    # The funnel returns the canonical stages even when empty so the
    # UI can render the chart shape.
    assert "cv_received" in funnel_statuses
    assert "joined" in funnel_statuses


# ---------------------------------------------------------------------------
# Seeded data — stats, funnel, pending lists.
# ---------------------------------------------------------------------------


def test_dashboard_aggregates_seeded_data(client, seed_auth, db_session: Session):
    now = datetime.now(timezone.utc)

    # 1 open job
    job = JobOpening(
        slug="store-mgr",
        title="Store Manager",
        department="Retail Operations",
        company="Paris Hyper Market",
        location="Doha",
        status=JOB_STATUS_OPEN,
    )

    # 3 candidates → 3 applications across 3 statuses
    candidates = [
        Candidate(full_name=f"Candidate {i}", email=f"c{i}@example.com")
        for i in range(3)
    ]
    db_session.add(job)
    db_session.add_all(candidates)
    db_session.flush()

    apps = [
        CandidateJobApplication(
            candidate_id=candidates[0].id,
            job_opening_id=job.id,
            status=STATUS_CV_RECEIVED,
            applied_at=now - timedelta(days=2),
        ),
        CandidateJobApplication(
            candidate_id=candidates[1].id,
            job_opening_id=job.id,
            status=STATUS_HR_REVIEW_PENDING,
            applied_at=now - timedelta(days=10),
        ),
        CandidateJobApplication(
            candidate_id=candidates[2].id,
            job_opening_id=job.id,
            status=STATUS_SHORTLISTED,
            applied_at=now,
        ),
    ]
    db_session.add_all(apps)
    db_session.flush()

    # AI review for the shortlisted candidate
    db_session.add(
        CandidateAIReview(
            application_id=apps[2].id,
            recommendation=AI_RECOMMENDED,
            summary="Strong fit.",
        )
    )

    # 1 rejected candidate (separate)
    rejected_candidate = Candidate(full_name="Rejected", email="r@example.com")
    db_session.add(rejected_candidate)
    db_session.flush()
    db_session.add(
        CandidateJobApplication(
            candidate_id=rejected_candidate.id,
            job_opening_id=job.id,
            status=STATUS_REJECTED,
            last_rejection_reason="Insufficient experience",
        )
    )

    # 1 scheduled interview in the future
    db_session.add(
        Interview(
            application_id=apps[2].id,
            round_name="First Interview",
            scheduled_at=now + timedelta(days=3),
            mode=INTERVIEW_MODE_ONLINE,
            status=INTERVIEW_SCHEDULED,
        )
    )

    # 1 pending offer
    db_session.add(
        OfferTracking(
            application_id=apps[2].id,
            salary_offered=12000,
            status=OFFER_SENT,
            sent_at=now,
        )
    )
    db_session.commit()

    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(DASHBOARD, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    stats = {s["key"]: s["value"] for s in body["stats"]}
    assert stats["open_jobs"] == 1
    assert stats["total_candidates"] == 4
    assert stats["applications_total"] == 4
    assert stats["ai_reviewed"] == 1
    assert stats["highly_recommended"] == 1  # AI_RECOMMENDED counts too
    assert stats["hr_review_pending"] == 1
    assert stats["shortlisted"] == 1
    assert stats["rejected"] == 1
    assert stats["pending_interviews"] == 1
    assert stats["pending_offers"] == 1

    funnel = {s["status"]: s["count"] for s in body["pipeline_funnel"]}
    assert funnel["cv_received"] == 1
    assert funnel["hr_review_pending"] == 1
    assert funnel["shortlisted"] == 1
    # Rejected isn't in the funnel stages list — it's a terminal state.

    # Monthly bucketing produces at least one row.
    assert len(body["applications_per_month"]) >= 1

    # Pending interviews list
    interviews = body["pending_interviews"]
    assert len(interviews) == 1
    assert interviews[0]["candidate_name"] == "Candidate 2"
    assert interviews[0]["job_title"] == "Store Manager"
    assert interviews[0]["round_name"] == "First Interview"
    assert interviews[0]["mode"] == "online"

    # Pending offers list
    offers = body["pending_offers"]
    assert len(offers) == 1
    assert offers[0]["candidate_name"] == "Candidate 2"
    assert offers[0]["salary_offered"] == 12000
    assert offers[0]["status"] == "sent"

    # Group-by
    by_job = {row["name"]: row["count"] for row in body["candidates_by_job"]}
    assert by_job == {"Store Manager": 4}
    by_dept = {row["name"]: row["count"] for row in body["candidates_by_department"]}
    assert by_dept == {"Retail Operations": 4}


def test_pending_interviews_excludes_past_and_other_statuses(
    client, seed_auth, db_session: Session
):
    now = datetime.now(timezone.utc)
    job = JobOpening(
        slug="j", title="J", department="D", company="C", location="L"
    )
    candidate = Candidate(full_name="X")
    db_session.add_all([job, candidate])
    db_session.flush()
    app = CandidateJobApplication(
        candidate_id=candidate.id, job_opening_id=job.id
    )
    db_session.add(app)
    db_session.flush()

    db_session.add_all(
        [
            # Past interview — should be excluded
            Interview(
                application_id=app.id,
                round_name="Old",
                scheduled_at=now - timedelta(days=1),
                status=INTERVIEW_SCHEDULED,
            ),
            # Future but cancelled — should be excluded
            Interview(
                application_id=app.id,
                round_name="Cancelled",
                scheduled_at=now + timedelta(days=2),
                status="cancelled",
            ),
            # Future scheduled — should appear
            Interview(
                application_id=app.id,
                round_name="Future",
                scheduled_at=now + timedelta(days=5),
                status=INTERVIEW_SCHEDULED,
            ),
        ]
    )
    db_session.commit()

    headers = _hr_auth(client, seed_auth["password"])
    body = client.get(DASHBOARD, headers=headers).json()
    rounds = [i["round_name"] for i in body["pending_interviews"]]
    assert rounds == ["Future"]
