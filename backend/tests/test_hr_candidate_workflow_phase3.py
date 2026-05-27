"""Phase 3 — separate recruitment / interview / offer statuses + unified timeline.

Pins the behavior added in Phase 3:

  * The three new recruitment statuses (waiting_list,
    recommended_for_offer, not_joined) are accepted by the status
    endpoint and respect the new transition graph.
  * The unified candidate timeline endpoint returns events from all
    three streams sorted newest-first.
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    STATUS_FINAL_INTERVIEW,
    STATUS_NOT_JOINED,
    STATUS_OFFER_SENT,
    STATUS_RECOMMENDED_FOR_OFFER,
    STATUS_SELECTED,
    STATUS_WAITING_LIST,
    Candidate,
    CandidateJobApplication,
    JobOpening,
)


HR_LOGIN = "/api/v1/hr/auth/login"
HR_UPLOAD = "/api/v1/hr/candidates/upload"
HR_STATUS = "/api/v1/hr/candidates/{cid}/applications/{aid}/status"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_application(
    db_session: Session, slug: str = "phase3-job"
) -> CandidateJobApplication:
    job = JobOpening(
        slug=slug,
        title="Senior Engineer",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    cand = Candidate(
        full_name="Phase 3 Candidate",
        email="phase3@example.com",
    )
    db_session.add_all([job, cand])
    db_session.flush()
    app = CandidateJobApplication(
        candidate_id=cand.id,
        job_opening_id=job.id,
        status=STATUS_FINAL_INTERVIEW,
    )
    db_session.add(app)
    db_session.commit()
    return app


# ---------------------------------------------------------------------------
# New recruitment statuses
# ---------------------------------------------------------------------------


def test_waiting_list_is_reachable_from_final_interview(
    client, seed_auth, db_session: Session
):
    """final_interview → waiting_list is a valid transition."""
    app = _make_application(db_session, "wl-job")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    response = client.post(
        HR_STATUS.format(cid=app.candidate_id, aid=app.id),
        json={"new_status": STATUS_WAITING_LIST},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.get(CandidateJobApplication, app.id).status == STATUS_WAITING_LIST


def test_recommended_for_offer_is_reachable_from_final_interview(
    client, seed_auth, db_session: Session
):
    app = _make_application(db_session, "rfo-job")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    response = client.post(
        HR_STATUS.format(cid=app.candidate_id, aid=app.id),
        json={"new_status": STATUS_RECOMMENDED_FOR_OFFER},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def test_recommended_for_offer_can_promote_to_selected(
    client, seed_auth, db_session: Session
):
    """The workflow allows recommended_for_offer → selected (the
    manager's authorisation step)."""
    app = _make_application(db_session, "promote-job")
    app.status = STATUS_RECOMMENDED_FOR_OFFER
    db_session.commit()

    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.post(
        HR_STATUS.format(cid=app.candidate_id, aid=app.id),
        json={"new_status": STATUS_SELECTED},
        headers=headers,
    )
    assert response.status_code == 200


def test_not_joined_is_reachable_from_offer_sent(
    client, seed_auth, db_session: Session
):
    """offer_sent → not_joined is valid (candidate accepted but didn't
    show up). Distinct from rejected which is HR-initiated."""
    app = _make_application(db_session, "nj-job")
    app.status = STATUS_OFFER_SENT
    db_session.commit()

    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.post(
        HR_STATUS.format(cid=app.candidate_id, aid=app.id),
        json={"new_status": STATUS_NOT_JOINED},
        headers=headers,
    )
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Unified timeline endpoint
# ---------------------------------------------------------------------------


def test_timeline_endpoint_returns_applied_event_for_new_application(
    client, seed_auth, db_session: Session
):
    app = _make_application(db_session, "timeline-base")

    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.get(
        f"/api/v1/hr/candidates/{app.candidate_id}/timeline",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    events = response.json()
    assert any(
        e["stream"] == "recruitment" and e["action"] == "applied" for e in events
    )


def test_timeline_endpoint_includes_status_changes(
    client, seed_auth, db_session: Session
):
    """When HR moves the candidate through statuses, each transition
    shows up in the timeline."""
    app = _make_application(db_session, "timeline-statuses")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    # Push through two transitions.
    client.post(
        HR_STATUS.format(cid=app.candidate_id, aid=app.id),
        json={"new_status": STATUS_WAITING_LIST},
        headers=headers,
    )
    client.post(
        HR_STATUS.format(cid=app.candidate_id, aid=app.id),
        json={"new_status": STATUS_RECOMMENDED_FOR_OFFER},
        headers=headers,
    )

    response = client.get(
        f"/api/v1/hr/candidates/{app.candidate_id}/timeline",
        headers=headers,
    )
    assert response.status_code == 200
    events = response.json()
    status_changes = [
        e for e in events if e["action"] == "status_changed"
    ]
    # Two changes recorded
    assert len(status_changes) >= 2
    new_statuses = {e["new_status"] for e in status_changes}
    assert STATUS_WAITING_LIST in new_statuses
    assert STATUS_RECOMMENDED_FOR_OFFER in new_statuses


def test_timeline_endpoint_403_for_users_without_view_full(
    client, seed_auth, db_session: Session
):
    """Interviewer doesn't hold hr:candidates:view_full → 403 on
    /candidates/{id}/timeline."""
    app = _make_application(db_session, "timeline-perm")
    headers = _login(client, "interviewer@pug.example.com", seed_auth["password"])
    response = client.get(
        f"/api/v1/hr/candidates/{app.candidate_id}/timeline",
        headers=headers,
    )
    assert response.status_code == 403


def test_timeline_endpoint_404_for_unknown_candidate(client, seed_auth):
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.get(
        "/api/v1/hr/candidates/999999/timeline",
        headers=headers,
    )
    assert response.status_code == 404


def test_timeline_events_sorted_newest_first(
    client, seed_auth, db_session: Session
):
    app = _make_application(db_session, "timeline-sort")
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    client.post(
        HR_STATUS.format(cid=app.candidate_id, aid=app.id),
        json={"new_status": STATUS_WAITING_LIST},
        headers=headers,
    )

    response = client.get(
        f"/api/v1/hr/candidates/{app.candidate_id}/timeline",
        headers=headers,
    )
    events = response.json()
    # Each event has occurred_at; verify the list is descending.
    timestamps = [e["occurred_at"] for e in events]
    assert timestamps == sorted(timestamps, reverse=True)
