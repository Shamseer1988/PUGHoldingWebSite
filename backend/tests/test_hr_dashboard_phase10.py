"""Phase 10 — dashboard master-plan stat cards.

The master plan asks for twelve dashboard stat cards. This test pins
that every key shows up in the /hr/dashboard response so future
refactors don't drop one silently.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_PENDING,
    INTERVIEW_COMPLETED,
    JOB_STATUS_OPEN,
    OFFER_PENDING_APPROVAL,
    OFFER_SENT,
    PUBLISH_STATUS_PUBLISHED,
    STATUS_CV_RECEIVED,
    Candidate,
    CandidateJobApplication,
    Interview,
    JobOpening,
    OfferTracking,
)


HR_LOGIN = "/api/v1/hr/auth/login"


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_dashboard_exposes_all_master_plan_keys(client, seed_auth):
    """The twelve master-plan cards must all be present in /dashboard."""
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.get("/api/v1/hr/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    keys = {s["key"] for s in response.json()["stats"]}
    required = {
        "total_jobs",
        "pending_approval_jobs",
        "live_jobs",
        "total_candidates",
        "new_applications",
        "shortlisted",
        "interviews_today",
        "pending_feedback",
        "offers_pending_approval",
        "offers_issued",
        "joining_pending",
        "joined_this_month",
    }
    missing = required - keys
    assert not missing, f"Missing dashboard cards: {missing}"


def test_pending_approval_jobs_counts_correctly(
    client, seed_auth, db_session: Session
):
    """Insert two pending-approval jobs and one approved — dashboard
    should report pending_approval_jobs = 2."""
    for slug, ap in (
        ("p10-pa-a", APPROVAL_STATUS_PENDING),
        ("p10-pa-b", APPROVAL_STATUS_PENDING),
        ("p10-pa-c", APPROVAL_STATUS_APPROVED),
    ):
        db_session.add(
            JobOpening(
                slug=slug,
                title=f"P10 Job {slug}",
                department="Engineering",
                company="PUG",
                location="Doha",
                status=JOB_STATUS_OPEN,
                approval_status=ap,
            )
        )
    db_session.commit()

    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    stats = {
        s["key"]: s["value"]
        for s in client.get("/api/v1/hr/dashboard", headers=headers).json()[
            "stats"
        ]
    }
    assert stats["pending_approval_jobs"] == 2


def test_live_jobs_uses_three_way_gate(
    client, seed_auth, db_session: Session
):
    """live_jobs = status=open AND approval=approved AND publish=published."""
    # Approved + published + open  -> counted
    db_session.add(
        JobOpening(
            slug="p10-live-yes",
            title="Live",
            department="Eng",
            company="PUG",
            location="Doha",
            status=JOB_STATUS_OPEN,
            approval_status=APPROVAL_STATUS_APPROVED,
            publish_status=PUBLISH_STATUS_PUBLISHED,
        )
    )
    # Approved but draft publish status -> NOT counted
    db_session.add(
        JobOpening(
            slug="p10-live-no-pub",
            title="No publish",
            department="Eng",
            company="PUG",
            location="Doha",
            status=JOB_STATUS_OPEN,
            approval_status=APPROVAL_STATUS_APPROVED,
            publish_status="draft",
        )
    )
    db_session.commit()

    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    stats = {
        s["key"]: s["value"]
        for s in client.get("/api/v1/hr/dashboard", headers=headers).json()[
            "stats"
        ]
    }
    assert stats["live_jobs"] == 1


def test_pending_feedback_counts_completed_without_feedback(
    client, seed_auth, db_session: Session
):
    """Pending feedback = completed interviews with no InterviewFeedback row."""
    job = JobOpening(
        slug="p10-pf-job",
        title="Job",
        department="Eng",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
    )
    cand = Candidate(full_name="P10 PF Cand", email="p10pf@example.com")
    db_session.add_all([job, cand])
    db_session.flush()
    app = CandidateJobApplication(
        candidate_id=cand.id,
        job_opening_id=job.id,
        status=STATUS_CV_RECEIVED,
    )
    db_session.add(app)
    db_session.flush()
    # One completed interview without feedback.
    db_session.add(
        Interview(
            application_id=app.id,
            round_name="Round 1",
            scheduled_at=datetime.now(timezone.utc) - timedelta(days=1),
            duration_minutes=30,
            mode="online",
            location_or_link="https://example.com",
            status=INTERVIEW_COMPLETED,
        )
    )
    db_session.commit()

    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    stats = {
        s["key"]: s["value"]
        for s in client.get("/api/v1/hr/dashboard", headers=headers).json()[
            "stats"
        ]
    }
    assert stats["pending_feedback"] >= 1


def test_offers_split_by_lifecycle_state(
    client, seed_auth, db_session: Session
):
    """offers_pending_approval, offers_issued, joining_pending are
    correctly partitioned by OfferTracking.status / joining_status."""
    job = JobOpening(
        slug="p10-of-job",
        title="Job",
        department="Eng",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
    )
    db_session.add(job)
    db_session.flush()

    def _app() -> int:
        cand = Candidate(
            full_name=f"P10 Off {len(db_session.new) + 1}",
            email=f"p10off{len(db_session.new)}@example.com",
        )
        db_session.add(cand)
        db_session.flush()
        app = CandidateJobApplication(
            candidate_id=cand.id,
            job_opening_id=job.id,
            status=STATUS_CV_RECEIVED,
        )
        db_session.add(app)
        db_session.flush()
        return app.id

    db_session.add(
        OfferTracking(application_id=_app(), status=OFFER_PENDING_APPROVAL)
    )
    db_session.add(
        OfferTracking(application_id=_app(), status=OFFER_SENT)
    )
    db_session.add(
        OfferTracking(
            application_id=_app(),
            status="accepted",
            joining_status="pending",
        )
    )
    db_session.commit()

    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    stats = {
        s["key"]: s["value"]
        for s in client.get("/api/v1/hr/dashboard", headers=headers).json()[
            "stats"
        ]
    }
    assert stats["offers_pending_approval"] == 1
    assert stats["offers_issued"] == 1
    assert stats["joining_pending"] == 1
