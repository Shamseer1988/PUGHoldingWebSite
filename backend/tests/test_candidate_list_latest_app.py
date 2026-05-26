"""Verify CandidateListItem now exposes ``latest_application_id``."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.endpoints.hr_candidates import _serialize_list_item
from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    STATUS_CV_RECEIVED,
    Candidate,
    CandidateJobApplication,
    JobOpening,
)


def test_latest_application_id_is_populated(db_session: Session):
    job = JobOpening(
        slug="latest-app-test",
        title="Test",
        department="Eng",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    cand = Candidate(full_name="Test", email="t@e.com")
    db_session.add_all([job, cand])
    db_session.flush()

    app1 = CandidateJobApplication(
        candidate_id=cand.id, job_opening_id=job.id, status=STATUS_CV_RECEIVED
    )
    db_session.add(app1)
    db_session.flush()

    # Add a more recent application — should be the one picked.
    import time

    time.sleep(0.01)
    app2 = CandidateJobApplication(
        candidate_id=cand.id, job_opening_id=None, status=STATUS_CV_RECEIVED
    )
    db_session.add(app2)
    db_session.commit()
    db_session.refresh(cand)

    item = _serialize_list_item(cand, top_score=None, latest_status=None)
    assert item.latest_application_id == app2.id


def test_latest_application_id_is_none_when_no_applications(db_session: Session):
    cand = Candidate(full_name="No Apps", email="na@e.com")
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)

    item = _serialize_list_item(cand, top_score=None, latest_status=None)
    assert item.latest_application_id is None
