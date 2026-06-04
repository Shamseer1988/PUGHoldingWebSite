"""Phase 1 — withdrawing an issued offer frees the candidate for re-issue.

Repo-owner decision: a withdrawal is not a dead end. The offer moves to its
terminal ``withdrawn`` state (so it still shows on the dashboard's Withdrawn
card / status filter) and, if it had been issued, the candidate is reverted
from ``offer_sent`` back to ``selected`` through the candidate FSM
(transition-validated + recorded in CandidateStatusHistory). HR can then
draft a fresh offer — ``create_offer`` revives the same row, since offers
are 1:1 with the application.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    OFFER_DRAFT,
    OFFER_WITHDRAWN,
    STATUS_OFFER_SENT,
    STATUS_SELECTED,
    Candidate,
    CandidateJobApplication,
    CandidateStatusHistory,
    JobOpening,
    OfferTracking,
)
from app.services.candidate_workflow import allowed_next_statuses

HR_LOGIN = "/api/v1/hr/auth/login"
OFFERS = "/api/v1/hr/offers"


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_application(
    db_session: Session, slug: str, *, initial_status: str = STATUS_SELECTED
) -> CandidateJobApplication:
    job = JobOpening(
        slug=slug,
        title="Withdraw Job",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    cand = Candidate(full_name="Withdraw Candidate", email=f"{slug}@example.com")
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


def _issue(client, headers, application_id: int) -> int:
    oid = client.post(
        OFFERS, headers=headers, json={"application_id": application_id}
    ).json()["id"]
    assert client.post(f"{OFFERS}/{oid}/submit-approval", headers=headers).status_code == 200
    assert client.post(f"{OFFERS}/{oid}/approve", headers=headers, json={}).status_code == 200
    assert client.post(f"{OFFERS}/{oid}/issue", headers=headers, json={}).status_code == 200
    return oid


def test_offer_sent_can_revert_to_selected_in_fsm() -> None:
    """The withdraw path relies on a single backward FSM edge."""
    assert STATUS_SELECTED in allowed_next_statuses(STATUS_OFFER_SENT)


def test_withdraw_after_issue_reverts_candidate_and_allows_reissue(
    client, seed_auth, db_session: Session
) -> None:
    app = _make_application(db_session, "withdraw-reissue")
    su = _login(client, "superadmin@pug.example.com", seed_auth["password"])

    oid = _issue(client, su, app.id)
    db_session.expire_all()
    assert db_session.get(CandidateJobApplication, app.id).status == STATUS_OFFER_SENT

    resp = client.post(
        f"{OFFERS}/{oid}/withdraw",
        headers=su,
        json={"remarks": "Revising the salary package before re-sending."},
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    # Candidate is pulled back to 'selected' (with a real history hop)...
    assert db_session.get(CandidateJobApplication, app.id).status == STATUS_SELECTED
    assert _history_new_statuses(db_session, app.id)[-1] == STATUS_SELECTED
    # ...and the offer rests in its terminal 'withdrawn' state.
    offer = db_session.get(OfferTracking, oid)
    assert offer.status == OFFER_WITHDRAWN
    assert offer.withdrawn_at is not None

    # Drafting a fresh offer revives the same 1:1 row as a clean draft.
    recreate = client.post(OFFERS, headers=su, json={"application_id": app.id})
    assert recreate.status_code in (200, 201), recreate.text
    assert recreate.json()["id"] == oid
    db_session.expire_all()
    revived = db_session.get(OfferTracking, oid)
    assert revived.status == OFFER_DRAFT
    assert revived.withdrawn_at is None  # withdrawal cleared on revive

    # The revived offer goes the full distance again — candidate re-sent.
    assert client.post(f"{OFFERS}/{oid}/submit-approval", headers=su).status_code == 200
    assert client.post(f"{OFFERS}/{oid}/approve", headers=su, json={}).status_code == 200
    assert client.post(f"{OFFERS}/{oid}/issue", headers=su, json={}).status_code == 200
    db_session.expire_all()
    assert db_session.get(CandidateJobApplication, app.id).status == STATUS_OFFER_SENT


def test_withdraw_before_issue_leaves_candidate_untouched(
    client, seed_auth, db_session: Session
) -> None:
    """Withdrawing a never-issued offer is terminal for the offer but does
    not move the candidate (they were never pushed to 'offer_sent')."""
    app = _make_application(db_session, "withdraw-predraft")
    su = _login(client, "superadmin@pug.example.com", seed_auth["password"])

    oid = client.post(OFFERS, headers=su, json={"application_id": app.id}).json()["id"]
    assert client.post(f"{OFFERS}/{oid}/submit-approval", headers=su).status_code == 200
    assert client.post(f"{OFFERS}/{oid}/approve", headers=su, json={}).status_code == 200

    resp = client.post(
        f"{OFFERS}/{oid}/withdraw",
        headers=su,
        json={"remarks": "Position put on hold."},
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    # Candidate untouched; no spurious history rows for this application.
    assert db_session.get(CandidateJobApplication, app.id).status == STATUS_SELECTED
    assert _history_new_statuses(db_session, app.id) == []
    offer = db_session.get(OfferTracking, oid)
    assert offer.status == OFFER_WITHDRAWN
    assert offer.withdrawn_at is not None
