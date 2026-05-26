"""Tests for the auto-review engine + auto-review rule endpoints (phase 4).

Covers:

* No active rule → every candidate lands in hr_review_pending.
* High-score + matching skills → auto_shortlisted.
* Low-score + auto_reject_enabled=true → auto_rejected.
* Low-score WITHOUT auto_reject_enabled → still hr_review_pending (HR
  signs off on every rejection unless explicitly opted in).
* Missing required skill keeps the candidate in HR review even at a
  high score.
* Hard-rule mismatch (visa keyword) lists the flag in ``risk_flags``.
* Endpoints: GET/PUT rule, POST run, GET summary, GET per-app review.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    AUTO_REVIEW_HR_PENDING,
    AUTO_REVIEW_REJECTED,
    AUTO_REVIEW_SHORTLISTED,
    JOB_STATUS_OPEN,
    STATUS_CV_RECEIVED,
    Candidate,
    CandidateAutoReview,
    CandidateExtractedData,
    CandidateJobApplication,
    CandidateScore,
    JobAutoReviewRule,
    JobOpening,
)
from app.services import candidate_auto_review


HR_LOGIN = "/api/v1/hr/auth/login"


def _auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_job_and_app(
    db_session: Session,
    *,
    candidate_kwargs: dict | None = None,
    skills: str = "python, postgresql, fastapi",
    total_score: int = 80,
) -> tuple[JobOpening, CandidateJobApplication]:
    job = JobOpening(
        slug=f"job-{db_session.execute(select(JobOpening)).scalars().all().__len__()}",
        title="Senior Engineer",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
        required_skills="python, postgresql, fastapi",
        preferred_skills="aws",
    )
    db_session.add(job)
    db_session.flush()

    cand_kwargs = candidate_kwargs or {}
    candidate = Candidate(
        full_name=cand_kwargs.pop("full_name", "Jane Doe"),
        email=cand_kwargs.pop("email", "jane@example.com"),
        **cand_kwargs,
    )
    db_session.add(candidate)
    db_session.flush()

    extracted = CandidateExtractedData(
        candidate_id=candidate.id,
        skills=skills,
    )
    db_session.add(extracted)

    app = CandidateJobApplication(
        candidate_id=candidate.id,
        job_opening_id=job.id,
        status=STATUS_CV_RECEIVED,
    )
    db_session.add(app)
    db_session.flush()

    score = CandidateScore(application_id=app.id, total=total_score)
    db_session.add(score)
    db_session.commit()
    return job, app


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def test_no_active_rule_returns_hr_review_pending(db_session: Session):
    _, app = _make_job_and_app(db_session, total_score=95)
    review = candidate_auto_review.run_auto_review(db_session, application=app)
    db_session.commit()
    assert review.decision == AUTO_REVIEW_HR_PENDING


def test_high_score_with_skills_auto_shortlists(db_session: Session):
    job, app = _make_job_and_app(db_session, total_score=88)
    rule = candidate_auto_review.get_or_create_rule(
        db_session, job_opening_id=job.id
    )
    rule.is_active = True
    rule.auto_shortlist_threshold = 80
    db_session.commit()

    review = candidate_auto_review.run_auto_review(
        db_session, application=app, rule=rule
    )
    db_session.commit()
    assert review.decision == AUTO_REVIEW_SHORTLISTED
    assert "python" in (review.matched_skills or [])


def test_low_score_auto_reject_only_when_flag_enabled(db_session: Session):
    job, app = _make_job_and_app(db_session, total_score=30)
    rule = candidate_auto_review.get_or_create_rule(
        db_session, job_opening_id=job.id
    )
    rule.is_active = True
    rule.auto_shortlist_threshold = 80
    rule.auto_reject_threshold = 50
    rule.auto_reject_enabled = False
    db_session.commit()

    review = candidate_auto_review.run_auto_review(
        db_session, application=app, rule=rule
    )
    db_session.commit()
    # Without the explicit opt-in, never auto-reject.
    assert review.decision == AUTO_REVIEW_HR_PENDING

    rule.auto_reject_enabled = True
    db_session.commit()
    review = candidate_auto_review.run_auto_review(
        db_session, application=app, rule=rule
    )
    db_session.commit()
    assert review.decision == AUTO_REVIEW_REJECTED


def test_missing_required_skill_holds_for_hr_review(db_session: Session):
    job, app = _make_job_and_app(
        db_session, skills="ruby, rails", total_score=85
    )
    rule = candidate_auto_review.get_or_create_rule(
        db_session, job_opening_id=job.id
    )
    rule.is_active = True
    rule.auto_shortlist_threshold = 80
    db_session.commit()

    review = candidate_auto_review.run_auto_review(
        db_session, application=app, rule=rule
    )
    db_session.commit()
    assert review.decision == AUTO_REVIEW_HR_PENDING
    assert "python" in (review.missing_skills or [])


def test_visa_keyword_mismatch_records_risk_flag(db_session: Session):
    job, app = _make_job_and_app(
        db_session,
        candidate_kwargs={"visa_status": "Visit Visa"},
        total_score=90,
    )
    rule = candidate_auto_review.get_or_create_rule(
        db_session, job_opening_id=job.id
    )
    rule.is_active = True
    rule.auto_shortlist_threshold = 80
    rule.visa_keywords = ["transferable", "qid"]
    db_session.commit()

    review = candidate_auto_review.run_auto_review(
        db_session, application=app, rule=rule
    )
    db_session.commit()
    assert review.decision == AUTO_REVIEW_HR_PENDING
    assert any("visa" in flag for flag in (review.risk_flags or []))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def test_upsert_and_run_endpoints(client, seed_auth, db_session: Session):
    job, app = _make_job_and_app(db_session, total_score=90)
    headers = _auth(client, seed_auth["password"])

    # Create rule via PUT.
    put = client.put(
        f"/api/v1/hr/jobs/{job.id}/auto-review-rule",
        json={
            "is_active": True,
            "auto_shortlist_threshold": 80,
            "auto_reject_threshold": 30,
            "required_skills": ["python", "postgresql"],
        },
        headers=headers,
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["is_active"] is True
    assert body["required_skills"] == ["python", "postgresql"]

    # GET returns it.
    get = client.get(f"/api/v1/hr/jobs/{job.id}/auto-review-rule", headers=headers)
    assert get.status_code == 200
    assert get.json()["auto_shortlist_threshold"] == 80

    # Run on the whole job.
    run = client.post(
        f"/api/v1/hr/jobs/{job.id}/auto-review-run", headers=headers
    )
    assert run.status_code == 200
    assert run.json()["reviewed"] == 1

    # Summary reports the auto-shortlist.
    summary = client.get(
        f"/api/v1/hr/jobs/{job.id}/auto-review-summary", headers=headers
    )
    assert summary.status_code == 200
    s = summary.json()
    assert s["auto_shortlisted"] == 1
    assert s["total_applications"] == 1

    # Per-application read.
    review_resp = client.get(
        f"/api/v1/hr/candidates/{app.candidate_id}/applications/{app.id}/auto-review",
        headers=headers,
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["decision"] == AUTO_REVIEW_SHORTLISTED
