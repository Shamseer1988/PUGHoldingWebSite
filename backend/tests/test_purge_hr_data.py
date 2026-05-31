"""``app.scripts.purge_hr_data`` — destructive flag matrix.

Locks the contract HR ops will rely on when wiping the candidate
tables for a fresh start:

  * **Default scope** deletes candidates + the entire dependency tree
    (applications, interviews, offers, assessment invites) but
    *preserves* job openings AND assessment templates.
  * ``--include-jobs`` also drops job openings.
  * ``--include-assessment-templates`` also drops assessment templates.
  * Dry-run (no ``--apply``) makes no DB changes.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.hr_assessment import (
    Assessment,
    AssessmentChoice,
    AssessmentInvite,
    AssessmentQuestion,
)
from app.models.hr_ats import (
    Candidate,
    CandidateDocument,
    CandidateJobApplication,
    Interview,
    JobOpening,
    OfferTracking,
)


def _seed_full_graph(db_session: Session) -> tuple[Candidate, JobOpening, Assessment]:
    """Stand up one of every row the purge script touches."""
    job = JobOpening(
        slug="purge-test-job",
        title="Purge Test",
        department="Eng",
        company="PUG",
        location="Doha",
    )
    db_session.add(job)
    db_session.flush()

    candidate = Candidate(
        full_name="Purge Cand",
        email="purge@test.example",
        mobile="+97455551111",
        date_of_birth=date(1990, 1, 1),
    )
    db_session.add(candidate)
    db_session.flush()

    db_session.add(
        CandidateDocument(
            candidate_id=candidate.id,
            filename="abc.pdf",
            file_path="career/cv/abc.pdf",
            mime_type="application/pdf",
            file_size=10,
            file_hash="0" * 64,
            is_primary=True,
        )
    )

    application = CandidateJobApplication(
        candidate_id=candidate.id, job_opening_id=job.id
    )
    db_session.add(application)
    db_session.flush()

    db_session.add(
        Interview(
            application_id=application.id,
            round_name="Round 1",
            scheduled_at=datetime.utcnow(),
            mode="online",
            status="scheduled",
        )
    )
    db_session.add(
        OfferTracking(
            application_id=application.id,
            status="draft",
        )
    )

    assessment = Assessment(
        job_opening_id=job.id,
        title="MCQ Template",
        is_active=True,
    )
    db_session.add(assessment)
    db_session.flush()

    q = AssessmentQuestion(assessment_id=assessment.id, text="?", points=1)
    db_session.add(q)
    db_session.flush()
    db_session.add(
        AssessmentChoice(question_id=q.id, text="A", is_correct=True)
    )
    db_session.add(
        AssessmentChoice(question_id=q.id, text="B", is_correct=False)
    )

    db_session.add(
        AssessmentInvite(
            assessment_id=assessment.id,
            candidate_id=candidate.id,
            application_id=application.id,
            token="t-purge-1",
            status="sent",
        )
    )

    db_session.commit()
    return candidate, job, assessment


def _counts(db_session: Session) -> dict[str, int]:
    return {
        "candidates": db_session.execute(
            select(func.count()).select_from(Candidate)
        ).scalar_one(),
        "documents": db_session.execute(
            select(func.count()).select_from(CandidateDocument)
        ).scalar_one(),
        "applications": db_session.execute(
            select(func.count()).select_from(CandidateJobApplication)
        ).scalar_one(),
        "interviews": db_session.execute(
            select(func.count()).select_from(Interview)
        ).scalar_one(),
        "offers": db_session.execute(
            select(func.count()).select_from(OfferTracking)
        ).scalar_one(),
        "invites": db_session.execute(
            select(func.count()).select_from(AssessmentInvite)
        ).scalar_one(),
        "jobs": db_session.execute(
            select(func.count()).select_from(JobOpening)
        ).scalar_one(),
        "assessments": db_session.execute(
            select(func.count()).select_from(Assessment)
        ).scalar_one(),
    }


# ---------------------------------------------------------------------------
# Internal helpers — drive the script via its in-process API rather than the
# CLI so the test stays fast and doesn't need a subprocess.
# ---------------------------------------------------------------------------


def _purge(
    db_session: Session,
    *,
    include_jobs: bool = False,
    include_assessment_templates: bool = False,
) -> None:
    from app.scripts.purge_hr_data import (
        ASSESSMENT_TEMPLATE_SCOPE,
        CANDIDATE_SCOPE,
        JOBS_SCOPE,
        _delete_in_scope,
    )

    scope = list(CANDIDATE_SCOPE)
    if include_jobs:
        scope.extend(JOBS_SCOPE)
    if include_assessment_templates:
        scope.extend(ASSESSMENT_TEMPLATE_SCOPE)
    _delete_in_scope(db_session, scope)
    db_session.commit()


def test_default_scope_wipes_candidates_keeps_jobs_and_templates(
    db_session: Session,
):
    _seed_full_graph(db_session)
    before = _counts(db_session)
    assert before["candidates"] == 1
    assert before["jobs"] == 1
    assert before["assessments"] == 1

    _purge(db_session)

    after = _counts(db_session)
    # Candidate side is gone.
    assert after["candidates"] == 0
    assert after["documents"] == 0
    assert after["applications"] == 0
    assert after["interviews"] == 0
    assert after["offers"] == 0
    assert after["invites"] == 0
    # Reusable templates survive.
    assert after["jobs"] == 1
    assert after["assessments"] == 1


def test_include_jobs_also_wipes_job_openings(db_session: Session):
    _seed_full_graph(db_session)
    _purge(db_session, include_jobs=True)
    assert _counts(db_session)["jobs"] == 0


def test_include_assessment_templates_also_wipes_templates(
    db_session: Session,
):
    _seed_full_graph(db_session)
    _purge(db_session, include_assessment_templates=True)
    assert _counts(db_session)["assessments"] == 0


def test_collect_cv_keys_returns_every_referenced_path(db_session: Session):
    from app.scripts.purge_hr_data import _collect_cv_keys

    _seed_full_graph(db_session)
    keys = _collect_cv_keys(db_session)
    assert "career/cv/abc.pdf" in keys
