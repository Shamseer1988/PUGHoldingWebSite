"""DB integrity — CHECK constraints on the later enum status columns.

Covers the constraints added in migration ``20260603_0031`` (mirrored on
the models so ``create_all`` carries them). Each test inserts a valid row
(a positive control, proving the row is otherwise well-formed) then an
off-enum row and asserts the CHECK rejects it. Runs on the suite's SQLite
engine, which enforces CHECK constraints built by ``create_all``.
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    APPROVAL_ACTION_CREATED,
    AUTO_REVIEW_HR_PENDING,
    EMAIL_LOG_SENT,
    JOB_STATUS_OPEN,
    OFFER_JOINING_PENDING,
    REVISION_STATUS_PENDING,
    SCHEDULED_REPORT_STATUS_SUCCESS,
    Candidate,
    CandidateAutoReview,
    CandidateJobApplication,
    EmailLog,
    JobApprovalHistory,
    JobOpening,
    JobRevision,
    OfferTracking,
    ScheduledReport,
)


def _job(db_session: Session, slug: str) -> JobOpening:
    job = JobOpening(
        slug=slug,
        title="CK Job",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    db_session.add(job)
    db_session.commit()
    return job


def _application(db_session: Session, slug: str) -> CandidateJobApplication:
    job = _job(db_session, slug)
    cand = Candidate(full_name="CK Candidate", email=f"{slug}@example.com")
    db_session.add(cand)
    db_session.flush()
    app = CandidateJobApplication(
        candidate_id=cand.id, job_opening_id=job.id, status="cv_received"
    )
    db_session.add(app)
    db_session.commit()
    return app


def _reject(db_session: Session, obj: object) -> None:
    """Adding ``obj`` must trip a CHECK constraint on flush."""
    db_session.add(obj)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_email_log_status_constraint(db_session: Session) -> None:
    db_session.add(EmailLog(status=EMAIL_LOG_SENT))
    db_session.commit()
    _reject(db_session, EmailLog(status="bogus"))


def test_scheduled_report_last_run_status_constraint(db_session: Session) -> None:
    db_session.add(
        ScheduledReport(
            name="r1",
            report_type="candidate_full_export",
            recipients=["a@b.com"],
            last_run_status=SCHEDULED_REPORT_STATUS_SUCCESS,
        )
    )
    db_session.commit()
    _reject(
        db_session,
        ScheduledReport(
            name="r2",
            report_type="candidate_full_export",
            recipients=["a@b.com"],
            last_run_status="bogus",
        ),
    )


def test_job_revision_status_constraint(db_session: Session) -> None:
    job = _job(db_session, "ck-rev")
    db_session.add(
        JobRevision(job_opening_id=job.id, payload={}, status=REVISION_STATUS_PENDING)
    )
    db_session.commit()
    _reject(db_session, JobRevision(job_opening_id=job.id, payload={}, status="bogus"))


def test_job_approval_history_action_constraint(db_session: Session) -> None:
    job = _job(db_session, "ck-appr")
    db_session.add(
        JobApprovalHistory(job_opening_id=job.id, action=APPROVAL_ACTION_CREATED)
    )
    db_session.commit()
    _reject(db_session, JobApprovalHistory(job_opening_id=job.id, action="bogus"))


def test_candidate_auto_review_decision_constraint(db_session: Session) -> None:
    # application_id is unique on the table, so the valid + invalid rows
    # need separate applications.
    app_ok = _application(db_session, "ck-auto-ok")
    db_session.add(
        CandidateAutoReview(application_id=app_ok.id, decision=AUTO_REVIEW_HR_PENDING)
    )
    db_session.commit()
    app_bad = _application(db_session, "ck-auto-bad")
    _reject(db_session, CandidateAutoReview(application_id=app_bad.id, decision="bogus"))


def test_offer_joining_status_constraint(db_session: Session) -> None:
    app_ok = _application(db_session, "ck-join-ok")
    db_session.add(
        OfferTracking(application_id=app_ok.id, joining_status=OFFER_JOINING_PENDING)
    )
    db_session.commit()
    app_bad = _application(db_session, "ck-join-bad")
    _reject(db_session, OfferTracking(application_id=app_bad.id, joining_status="bogus"))
