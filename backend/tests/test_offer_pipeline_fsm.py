"""Phase 0 — offer milestones funnel through the candidate FSM.

Regression cover for the fix that routes the offer module's recruitment
status pushes through ``candidate_workflow.change_status`` instead of
writing ``CandidateJobApplication.status`` directly. Issuing an offer while
the application is still ``recommended_for_offer`` must step through
``selected`` (the FSM's required hop) before ``offer_sent`` — and every hop
must leave a ``CandidateStatusHistory`` row, so the recruitment status has a
single, transition-validated authority.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    STATUS_OFFER_SENT,
    STATUS_RECOMMENDED_FOR_OFFER,
    STATUS_SELECTED,
    Candidate,
    CandidateJobApplication,
    CandidateStatusHistory,
    JobOpening,
)

HR_LOGIN = "/api/v1/hr/auth/login"
OFFERS = "/api/v1/hr/offers"


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_application(
    db_session: Session,
    slug: str,
    initial_status: str = STATUS_RECOMMENDED_FOR_OFFER,
) -> CandidateJobApplication:
    job = JobOpening(
        slug=slug,
        title="FSM Job",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    cand = Candidate(full_name="FSM Candidate", email=f"{slug}@example.com")
    db_session.add_all([job, cand])
    db_session.flush()
    app = CandidateJobApplication(
        candidate_id=cand.id, job_opening_id=job.id, status=initial_status
    )
    db_session.add(app)
    db_session.commit()
    return app


def _history_new_statuses(db_session: Session, application_id: int) -> list[str]:
    rows = (
        db_session.execute(
            select(CandidateStatusHistory)
            .where(CandidateStatusHistory.application_id == application_id)
            .order_by(CandidateStatusHistory.id)
        )
        .scalars()
        .all()
    )
    return [r.new_status for r in rows]


def test_issue_from_recommended_steps_through_selected(
    client, seed_auth, db_session: Session
):
    """Issuing an offer drafted at recommended_for_offer advances the
    pipeline recommended_for_offer -> selected -> offer_sent via the FSM,
    recording a history row for each hop (not a single illegal jump)."""
    app = _make_application(
        db_session, "fsm-issue-recommended", initial_status=STATUS_RECOMMENDED_FOR_OFFER
    )
    su = _login(client, "superadmin@pug.example.com", seed_auth["password"])

    oid = client.post(OFFERS, headers=su, json={"application_id": app.id}).json()["id"]
    assert client.post(f"{OFFERS}/{oid}/submit-approval", headers=su).status_code == 200
    assert client.post(f"{OFFERS}/{oid}/approve", headers=su, json={}).status_code == 200
    issue = client.post(f"{OFFERS}/{oid}/issue", headers=su, json={})
    assert issue.status_code == 200, issue.text

    db_session.expire_all()
    assert db_session.get(CandidateJobApplication, app.id).status == STATUS_OFFER_SENT

    # The FSM hop is visible in history: selected precedes offer_sent.
    new_statuses = _history_new_statuses(db_session, app.id)
    assert STATUS_SELECTED in new_statuses, new_statuses
    assert STATUS_OFFER_SENT in new_statuses, new_statuses
    assert new_statuses.index(STATUS_SELECTED) < new_statuses.index(STATUS_OFFER_SENT)


def test_issue_from_selected_records_single_hop(
    client, seed_auth, db_session: Session
):
    """When the application is already selected, issuing moves it straight
    to offer_sent — one transition, no spurious extra 'selected' hop."""
    app = _make_application(
        db_session, "fsm-issue-selected", initial_status=STATUS_SELECTED
    )
    su = _login(client, "superadmin@pug.example.com", seed_auth["password"])

    oid = client.post(OFFERS, headers=su, json={"application_id": app.id}).json()["id"]
    client.post(f"{OFFERS}/{oid}/submit-approval", headers=su)
    client.post(f"{OFFERS}/{oid}/approve", headers=su, json={})
    assert client.post(f"{OFFERS}/{oid}/issue", headers=su, json={}).status_code == 200

    db_session.expire_all()
    assert db_session.get(CandidateJobApplication, app.id).status == STATUS_OFFER_SENT

    new_statuses = _history_new_statuses(db_session, app.id)
    assert new_statuses[-1] == STATUS_OFFER_SENT
    # The application started at 'selected', so no 'selected' transition is recorded.
    assert STATUS_SELECTED not in new_statuses, new_statuses
