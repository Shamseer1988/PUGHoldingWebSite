"""Smoke tests for the Phase 7 HR ATS models.

These exercise relationships, cascades, and the unique constraints
that later phases rely on.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    EMPLOYMENT_FULL_TIME,
    INTERVIEW_MODE_ONLINE,
    INTERVIEW_SCHEDULED,
    JOB_STATUS_OPEN,
    OFFER_DRAFT,
    SCORE_WEIGHTS,
    STATUS_CV_RECEIVED,
    STATUS_SHORTLISTED,
    Candidate,
    CandidateAIReview,
    CandidateDocument,
    CandidateExtractedData,
    CandidateJobApplication,
    CandidateNote,
    CandidateScore,
    CandidateScoreBreakdown,
    CandidateStatusHistory,
    CandidateTag,
    Interview,
    InterviewFeedback,
    JobOpening,
    OfferTracking,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_score_weights_sum_to_100():
    assert sum(SCORE_WEIGHTS.values()) == 100


# ---------------------------------------------------------------------------
# Job opening basics
# ---------------------------------------------------------------------------


def test_job_opening_round_trip(db_session: Session):
    job = JobOpening(
        slug="test-store-mgr",
        title="Store Manager",
        department="Retail Operations",
        company="Paris Hyper Market",
        location="Doha",
        employment_type=EMPLOYMENT_FULL_TIME,
        min_experience=5,
        max_experience=10,
        status=JOB_STATUS_OPEN,
    )
    db_session.add(job)
    db_session.commit()

    fetched = db_session.execute(
        select(JobOpening).where(JobOpening.slug == "test-store-mgr")
    ).scalar_one()
    assert fetched.title == "Store Manager"
    assert fetched.status == JOB_STATUS_OPEN
    assert fetched.applications == []


def test_job_opening_slug_unique(db_session: Session):
    db_session.add(
        JobOpening(
            slug="dup", title="A", department="X", company="Y", location="Z"
        )
    )
    db_session.commit()

    db_session.add(
        JobOpening(
            slug="dup", title="B", department="X", company="Y", location="Z"
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------------
# Candidate + documents + extracted data
# ---------------------------------------------------------------------------


def test_candidate_with_documents_and_extracted(db_session: Session):
    candidate = Candidate(
        full_name="Jane Doe",
        email="jane@example.com",
        mobile="+97400000000",
        nationality="QA",
        current_location="Doha",
        total_experience_years=6.5,
    )
    candidate.documents.append(
        CandidateDocument(
            filename="jane.pdf",
            file_path="/uploads/jane.pdf",
            mime_type="application/pdf",
            file_size=12345,
            file_hash="abc123",
        )
    )
    candidate.extracted_data = CandidateExtractedData(
        skills="Python, Retail",
        education=[{"degree": "MBA", "year": 2018}],
        languages=["English", "Arabic"],
        previous_companies=[{"name": "Acme", "years": 3}],
        full_text="Resume contents…",
    )
    candidate.tags.append(CandidateTag(tag="referral"))
    candidate.notes.append(CandidateNote(body="Strong communicator."))
    db_session.add(candidate)
    db_session.commit()

    fetched = db_session.execute(
        select(Candidate).where(Candidate.email == "jane@example.com")
    ).scalar_one()
    assert fetched.documents[0].filename == "jane.pdf"
    assert fetched.documents[0].file_hash == "abc123"
    assert fetched.extracted_data is not None
    assert fetched.extracted_data.skills == "Python, Retail"
    assert fetched.extracted_data.education == [{"degree": "MBA", "year": 2018}]
    assert [t.tag for t in fetched.tags] == ["referral"]
    assert [n.body for n in fetched.notes] == ["Strong communicator."]


def test_candidate_cascade_delete_removes_children(db_session: Session):
    candidate = Candidate(full_name="Ghost")
    candidate.documents.append(
        CandidateDocument(filename="a.pdf", file_path="/a.pdf")
    )
    candidate.extracted_data = CandidateExtractedData(skills="x")
    candidate.tags.append(CandidateTag(tag="cold"))
    db_session.add(candidate)
    db_session.commit()

    cid = candidate.id
    db_session.delete(candidate)
    db_session.commit()

    assert db_session.execute(
        select(CandidateDocument).where(CandidateDocument.candidate_id == cid)
    ).first() is None
    assert db_session.execute(
        select(CandidateExtractedData).where(
            CandidateExtractedData.candidate_id == cid
        )
    ).first() is None
    assert db_session.execute(
        select(CandidateTag).where(CandidateTag.candidate_id == cid)
    ).first() is None


def test_candidate_tag_unique_per_candidate(db_session: Session):
    c = Candidate(full_name="Tagged")
    db_session.add(c)
    db_session.flush()

    db_session.add(CandidateTag(candidate_id=c.id, tag="referral"))
    db_session.commit()

    db_session.add(CandidateTag(candidate_id=c.id, tag="referral"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------------
# Application + score + ai review + status history + interviews + offer
# ---------------------------------------------------------------------------


def _setup_application(db_session: Session) -> CandidateJobApplication:
    job = JobOpening(
        slug="role-x",
        title="Role X",
        department="Engineering",
        company="Paris United Group Holding",
        location="Doha",
    )
    candidate = Candidate(full_name="Applicant")
    db_session.add_all([job, candidate])
    db_session.flush()

    app = CandidateJobApplication(
        candidate_id=candidate.id,
        job_opening_id=job.id,
        status=STATUS_CV_RECEIVED,
        applied_at=datetime.now(timezone.utc),
    )
    db_session.add(app)
    db_session.commit()
    return app


def test_application_unique_per_candidate_job(db_session: Session):
    app = _setup_application(db_session)

    dup = CandidateJobApplication(
        candidate_id=app.candidate_id,
        job_opening_id=app.job_opening_id,
        status=STATUS_CV_RECEIVED,
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_score_breakdown_and_ai_review(db_session: Session):
    app = _setup_application(db_session)

    score = CandidateScore(application_id=app.id, total=72)
    score.breakdown = CandidateScoreBreakdown(
        relevant_experience=20,
        required_skills=15,
        education=8,
        industry_experience=8,
        gcc_qatar_experience=8,
        salary_fit=8,
        notice_period=3,
        visa_status=2,
        language_match=0,
        notes={"required_skills": "Matched 4/5 keywords."},
    )
    db_session.add(score)

    review = CandidateAIReview(
        application_id=app.id,
        summary="Strong fit for retail ops.",
        recommendation="recommended",
        model_name="gpt-4o-mini",
    )
    db_session.add(review)
    db_session.commit()

    fetched_score = db_session.execute(
        select(CandidateScore).where(CandidateScore.application_id == app.id)
    ).scalar_one()
    assert fetched_score.total == 72
    assert fetched_score.breakdown is not None
    assert fetched_score.breakdown.relevant_experience == 20

    fetched_review = db_session.execute(
        select(CandidateAIReview).where(CandidateAIReview.application_id == app.id)
    ).scalar_one()
    assert fetched_review.recommendation == "recommended"
    assert fetched_review.summary == "Strong fit for retail ops."


def test_status_history_and_pipeline(db_session: Session):
    app = _setup_application(db_session)

    history = [
        CandidateStatusHistory(
            application_id=app.id,
            old_status=STATUS_CV_RECEIVED,
            new_status=STATUS_SHORTLISTED,
            remarks="Looks great.",
        ),
    ]
    for h in history:
        db_session.add(h)
    app.status = STATUS_SHORTLISTED
    db_session.commit()

    rows = list(
        db_session.execute(
            select(CandidateStatusHistory).where(
                CandidateStatusHistory.application_id == app.id
            )
        ).scalars()
    )
    assert len(rows) == 1
    assert rows[0].new_status == STATUS_SHORTLISTED


def test_interview_with_feedback(db_session: Session):
    app = _setup_application(db_session)

    interview = Interview(
        application_id=app.id,
        round_name="First Interview",
        round_number=1,
        scheduled_at=datetime.now(timezone.utc),
        duration_minutes=45,
        mode=INTERVIEW_MODE_ONLINE,
        location_or_link="https://meet.example.com/abc",
        status=INTERVIEW_SCHEDULED,
    )
    interview.feedback.append(
        InterviewFeedback(
            rating=4,
            recommendation="hire",
            feedback="Good answers.",
            technical_score=4,
            communication_score=5,
            cultural_fit_score=4,
        )
    )
    db_session.add(interview)
    db_session.commit()

    fetched = db_session.execute(
        select(Interview).where(Interview.application_id == app.id)
    ).scalar_one()
    assert fetched.mode == INTERVIEW_MODE_ONLINE
    assert len(fetched.feedback) == 1
    assert fetched.feedback[0].recommendation == "hire"


def test_offer_tracking(db_session: Session):
    app = _setup_application(db_session)

    offer = OfferTracking(
        application_id=app.id,
        salary_offered=12000,
        status=OFFER_DRAFT,
    )
    db_session.add(offer)
    db_session.commit()

    fetched = db_session.execute(
        select(OfferTracking).where(OfferTracking.application_id == app.id)
    ).scalar_one()
    assert fetched.salary_offered == 12000
    assert fetched.status == OFFER_DRAFT


def test_offer_unique_per_application(db_session: Session):
    app = _setup_application(db_session)

    db_session.add(OfferTracking(application_id=app.id, salary_offered=10000))
    db_session.commit()

    db_session.add(OfferTracking(application_id=app.id, salary_offered=11000))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
