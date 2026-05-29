"""Phase 6 — Offer lifecycle.

Covers the full state machine layered on Phase-1 RBAC + Phase-3
recruitment statuses:

  * Create requires candidate in recommended_for_offer or selected.
  * Update is permitted in draft / pending_approval / approved only.
  * submit-approval / approve / reject_internal / issue / respond /
    mark_joined / mark_not_joined / withdraw transitions follow the
    state machine and reject illegal jumps with 409.
  * Approve is gated on hr:offers:approve and respects the
    self-approval guard (creator cannot approve own offer).
  * issue auto-generates an offer_letter_number if HR didn't set one.
  * mark_joined and mark_not_joined mirror the candidate's recruitment
    status to STATUS_JOINED / STATUS_NOT_JOINED.
  * Dashboard stats endpoint partitions by status.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    OFFER_DRAFT,
    OFFER_SENT,
    STATUS_JOINED,
    STATUS_NOT_JOINED,
    STATUS_RECOMMENDED_FOR_OFFER,
    STATUS_SELECTED,
    Candidate,
    CandidateJobApplication,
    JobOpening,
    OfferTracking,
)


HR_LOGIN = "/api/v1/hr/auth/login"
OFFERS = "/api/v1/hr/offers"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_application(
    db_session: Session,
    slug: str = "p6-job",
    initial_status: str = STATUS_RECOMMENDED_FOR_OFFER,
) -> CandidateJobApplication:
    job = JobOpening(
        slug=slug,
        title="Phase 6 Job",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    cand = Candidate(full_name="Phase 6 Candidate", email="p6@example.com")
    db_session.add_all([job, cand])
    db_session.flush()
    app = CandidateJobApplication(
        candidate_id=cand.id,
        job_opening_id=job.id,
        status=initial_status,
    )
    db_session.add(app)
    db_session.commit()
    return app


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


def test_create_requires_recommended_or_selected(
    client, seed_auth, db_session: Session
):
    """Cannot draft an offer for a candidate still in early pipeline
    stages."""
    app = _make_application(
        db_session, slug="p6-too-early", initial_status="cv_received"
    )
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.post(
        OFFERS,
        headers=headers,
        json={"application_id": app.id, "salary_offered": 5000},
    )
    assert response.status_code == 409
    assert "recommended_for_offer" in response.json()["detail"].lower()


def test_create_works_for_recommended_for_offer(
    client, seed_auth, db_session: Session
):
    app = _make_application(db_session, slug="p6-create-ok")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    response = client.post(
        OFFERS,
        headers=headers,
        json={
            "application_id": app.id,
            "position": "Senior Engineer",
            "salary_offered": 9500,
            "joining_date": str(date(2026, 7, 1)),
            "probation_period": "3 months",
            "work_location": "Doha HQ",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == OFFER_DRAFT
    assert body["approval_status"] == "draft"
    assert body["salary_offered"] == 9500


def test_one_offer_per_application(client, seed_auth, db_session: Session):
    app = _make_application(db_session, slug="p6-dupe")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    first = client.post(OFFERS, headers=headers, json={"application_id": app.id})
    assert first.status_code == 201
    second = client.post(OFFERS, headers=headers, json={"application_id": app.id})
    assert second.status_code == 409


# ---------------------------------------------------------------------------
# Full happy-path lifecycle
# ---------------------------------------------------------------------------


def test_full_lifecycle_through_joined(client, seed_auth, db_session: Session):
    """draft -> pending_approval -> approved -> sent -> accepted ->
    joined. Verifies the candidate recruitment status follows."""
    app = _make_application(db_session, slug="p6-lifecycle")
    # Use super admin throughout to bypass self-approval guard.
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])

    create = client.post(
        OFFERS, headers=su_headers,
        json={
            "application_id": app.id,
            "position": "DevOps Engineer",
            "salary_offered": 8000,
        },
    )
    assert create.status_code == 201
    offer_id = create.json()["id"]

    submit = client.post(f"{OFFERS}/{offer_id}/submit-approval", headers=su_headers)
    assert submit.status_code == 200
    assert submit.json()["status"] == "pending_approval"

    approve = client.post(
        f"{OFFERS}/{offer_id}/approve",
        headers=su_headers,
        json={},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    issue = client.post(f"{OFFERS}/{offer_id}/issue", headers=su_headers, json={})
    assert issue.status_code == 200, issue.text
    body = issue.json()
    assert body["status"] == OFFER_SENT
    assert body["offer_letter_number"]  # auto-generated
    assert body["sent_at"] is not None
    # Candidate recruitment status pushed to offer_sent.
    db_session.expire_all()
    assert db_session.get(CandidateJobApplication, app.id).status == "offer_sent"

    respond = client.post(
        f"{OFFERS}/{offer_id}/respond",
        headers=su_headers,
        json={"accepted": True},
    )
    assert respond.status_code == 200
    assert respond.json()["status"] == "accepted"
    assert respond.json()["joining_status"] == "pending"

    joined = client.post(f"{OFFERS}/{offer_id}/mark-joined", headers=su_headers, json={})
    assert joined.status_code == 200
    assert joined.json()["status"] == "joined"
    db_session.expire_all()
    assert (
        db_session.get(CandidateJobApplication, app.id).status == STATUS_JOINED
    )


def test_decline_path_blocks_joined(client, seed_auth, db_session: Session):
    app = _make_application(db_session, slug="p6-decline")
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    offer_id = client.post(
        OFFERS, headers=su_headers, json={"application_id": app.id}
    ).json()["id"]
    client.post(f"{OFFERS}/{offer_id}/submit-approval", headers=su_headers)
    client.post(f"{OFFERS}/{offer_id}/approve", headers=su_headers, json={})
    client.post(f"{OFFERS}/{offer_id}/issue", headers=su_headers, json={})

    response = client.post(
        f"{OFFERS}/{offer_id}/respond",
        headers=su_headers,
        json={"accepted": False, "decline_reason": "Counter-offer accepted."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "declined"
    assert body["decline_reason"] == "Counter-offer accepted."

    # Cannot mark_joined a declined offer.
    cannot = client.post(
        f"{OFFERS}/{offer_id}/mark-joined", headers=su_headers, json={}
    )
    assert cannot.status_code == 409


def test_mark_not_joined_updates_candidate_status(
    client, seed_auth, db_session: Session
):
    app = _make_application(db_session, slug="p6-not-joined")
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    offer_id = client.post(
        OFFERS, headers=su_headers, json={"application_id": app.id}
    ).json()["id"]
    client.post(f"{OFFERS}/{offer_id}/submit-approval", headers=su_headers)
    client.post(f"{OFFERS}/{offer_id}/approve", headers=su_headers, json={})
    client.post(f"{OFFERS}/{offer_id}/issue", headers=su_headers, json={})
    client.post(
        f"{OFFERS}/{offer_id}/respond",
        headers=su_headers,
        json={"accepted": True},
    )

    response = client.post(
        f"{OFFERS}/{offer_id}/mark-not-joined",
        headers=su_headers,
        json={"reason": "Personal emergency."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "not_joined"
    db_session.expire_all()
    assert (
        db_session.get(CandidateJobApplication, app.id).status == STATUS_NOT_JOINED
    )


# ---------------------------------------------------------------------------
# Approval rules
# ---------------------------------------------------------------------------


def test_approve_requires_offers_approve_permission(
    client, seed_auth, db_session: Session
):
    """HR Executive cannot approve offers."""
    app = _make_application(db_session, slug="p6-approve-perm")
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    offer_id = client.post(
        OFFERS, headers=su_headers, json={"application_id": app.id}
    ).json()["id"]
    client.post(f"{OFFERS}/{offer_id}/submit-approval", headers=su_headers)

    exec_headers = _login(client, "hrexec@pug.example.com", seed_auth["password"])
    response = client.post(
        f"{OFFERS}/{offer_id}/approve", headers=exec_headers, json={}
    )
    assert response.status_code == 403


def test_creator_cannot_approve_own_offer(
    client, seed_auth, db_session: Session
):
    """HR Manager (legacy alias hr@) creates AND tries to approve —
    blocked by the self-approval guard."""
    app = _make_application(db_session, slug="p6-self-approve")
    manager_headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    offer_id = client.post(
        OFFERS, headers=manager_headers, json={"application_id": app.id}
    ).json()["id"]
    client.post(f"{OFFERS}/{offer_id}/submit-approval", headers=manager_headers)

    response = client.post(
        f"{OFFERS}/{offer_id}/approve", headers=manager_headers, json={}
    )
    assert response.status_code == 403
    assert "create" in response.json()["detail"].lower()


def test_reject_internal_kicks_back_to_draft(
    client, seed_auth, db_session: Session
):
    app = _make_application(db_session, slug="p6-reject")
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    offer_id = client.post(
        OFFERS, headers=su_headers, json={"application_id": app.id}
    ).json()["id"]
    client.post(f"{OFFERS}/{offer_id}/submit-approval", headers=su_headers)

    response = client.post(
        f"{OFFERS}/{offer_id}/reject",
        headers=su_headers,
        json={"remarks": "Salary out of band — re-budget."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == OFFER_DRAFT
    assert body["approval_status"] == "rejected"
    assert body["rejection_reason"] == "Salary out of band — re-budget."


# ---------------------------------------------------------------------------
# Withdraw + delete
# ---------------------------------------------------------------------------


def test_withdraw_from_sent(client, seed_auth, db_session: Session):
    app = _make_application(db_session, slug="p6-withdraw")
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    offer_id = client.post(
        OFFERS, headers=su_headers, json={"application_id": app.id}
    ).json()["id"]
    client.post(f"{OFFERS}/{offer_id}/submit-approval", headers=su_headers)
    client.post(f"{OFFERS}/{offer_id}/approve", headers=su_headers, json={})
    client.post(f"{OFFERS}/{offer_id}/issue", headers=su_headers, json={})

    response = client.post(
        f"{OFFERS}/{offer_id}/withdraw",
        headers=su_headers,
        json={"remarks": "Headcount frozen."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"


def test_delete_blocked_after_issue(client, seed_auth, db_session: Session):
    app = _make_application(db_session, slug="p6-del-blocked")
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    offer_id = client.post(
        OFFERS, headers=su_headers, json={"application_id": app.id}
    ).json()["id"]
    client.post(f"{OFFERS}/{offer_id}/submit-approval", headers=su_headers)
    client.post(f"{OFFERS}/{offer_id}/approve", headers=su_headers, json={})
    client.post(f"{OFFERS}/{offer_id}/issue", headers=su_headers, json={})

    response = client.delete(f"{OFFERS}/{offer_id}", headers=su_headers)
    assert response.status_code == 409


def test_delete_works_on_draft(client, seed_auth, db_session: Session):
    app = _make_application(db_session, slug="p6-del-ok")
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    offer_id = client.post(
        OFFERS, headers=su_headers, json={"application_id": app.id}
    ).json()["id"]

    response = client.delete(f"{OFFERS}/{offer_id}", headers=su_headers)
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# Stats + status history
# ---------------------------------------------------------------------------


def test_stats_endpoint_counts_by_status(client, seed_auth, db_session: Session):
    """Three offers in different states → stats reflects them."""
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    for slug in ("stat-a", "stat-b", "stat-c"):
        app = _make_application(db_session, slug=f"p6-{slug}")
        oid = client.post(
            OFFERS, headers=su_headers, json={"application_id": app.id}
        ).json()["id"]
        if slug != "stat-a":
            client.post(f"{OFFERS}/{oid}/submit-approval", headers=su_headers)
        if slug == "stat-c":
            client.post(f"{OFFERS}/{oid}/approve", headers=su_headers, json={})

    response = client.get(f"{OFFERS}/stats", headers=su_headers)
    assert response.status_code == 200, response.text
    stats = response.json()
    assert stats["pending_approval"] == 1
    assert stats["approved"] == 1


def test_status_history_records_lifecycle(
    client, seed_auth, db_session: Session
):
    app = _make_application(db_session, slug="p6-history")
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    oid = client.post(
        OFFERS, headers=su_headers, json={"application_id": app.id}
    ).json()["id"]
    client.post(f"{OFFERS}/{oid}/submit-approval", headers=su_headers)
    client.post(f"{OFFERS}/{oid}/approve", headers=su_headers, json={})

    response = client.get(f"{OFFERS}/{oid}/status-history", headers=su_headers)
    assert response.status_code == 200
    history = response.json()
    actions = [h["action"] for h in history]
    assert "created" in actions
    assert "submit_approval" in actions
    assert "approve" in actions


# ---------------------------------------------------------------------------
# View permission for non-HR viewer
# ---------------------------------------------------------------------------


def test_viewer_can_list_offers(client, seed_auth, db_session: Session):
    """Viewer/Auditor role has hr:offers:view but not create/approve."""
    app = _make_application(db_session, slug="p6-viewer")
    su_headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    client.post(OFFERS, headers=su_headers, json={"application_id": app.id})

    viewer_headers = _login(client, "viewer@pug.example.com", seed_auth["password"])
    list_resp = client.get(OFFERS, headers=viewer_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1


def test_viewer_cannot_create_offer(client, seed_auth, db_session: Session):
    app = _make_application(db_session, slug="p6-viewer-create")
    viewer_headers = _login(client, "viewer@pug.example.com", seed_auth["password"])
    response = client.post(
        OFFERS, headers=viewer_headers, json={"application_id": app.id}
    )
    assert response.status_code == 403


def test_interviewer_cannot_list_offers(client, seed_auth):
    """Interviewer has no offers:view permission."""
    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.get(OFFERS, headers=headers)
    assert response.status_code == 403
