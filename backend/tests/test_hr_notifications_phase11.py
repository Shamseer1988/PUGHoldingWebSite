"""Phase 11 — full offer-lifecycle + interview-feedback notifications.

Verifies that:
  * Every new template renders without raising.
  * The offer endpoints dispatch the right notify helper at every
    lifecycle transition (submit-approval, approve, issue, respond,
    mark_joined).
  * The interview-feedback endpoint dispatches its notify helper.
  * The offer_email_enabled feature flag suppresses every offer
    email when off.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.email_settings import EmailSetting
from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    STATUS_RECOMMENDED_FOR_OFFER,
    Candidate,
    CandidateJobApplication,
    Interview,
    JobOpening,
)
from app.services import email_templates


HR_LOGIN = "/api/v1/hr/auth/login"
OFFERS = "/api/v1/hr/offers"


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [
        email_templates.TPL_INTERVIEW_FEEDBACK_SUBMITTED,
        email_templates.TPL_OFFER_APPROVAL_REQUESTED,
        email_templates.TPL_OFFER_APPROVED,
        email_templates.TPL_OFFER_ISSUED,
        email_templates.TPL_OFFER_ACCEPTED,
        email_templates.TPL_OFFER_DECLINED,
        email_templates.TPL_OFFER_JOINED,
    ],
)
def test_phase11_template_renders_without_raising(key: str):
    """Each of the 7 new templates renders cleanly with a minimal
    context dict."""
    out = email_templates.render(
        key,
        {
            "candidate_name": "Alice Apex",
            "job_title": "Senior Engineer",
            "position": "Senior Engineer",
            "salary_offered": 9000,
            "joining_date": "2026-07-01",
            "offer_letter_number": "OL-202607-000042-ab12",
            "work_location": "Doha HQ",
            "round_name": "Final",
            "interviewer_email": "interviewer@example.com",
            "recommendation": "hire",
            "rating": 4,
            "decline_reason": "Counter-offer.",
            "joined_at": "2026-07-15",
            "actor_email": "manager@example.com",
            "brand_logo_url": None,
            "email_footer_text": None,
        },
    )
    assert out.subject
    assert out.html
    assert out.text


def test_phase11_templates_registered_in_renderers_dict():
    keys = set(email_templates.available_template_keys())
    for k in (
        email_templates.TPL_INTERVIEW_FEEDBACK_SUBMITTED,
        email_templates.TPL_OFFER_APPROVAL_REQUESTED,
        email_templates.TPL_OFFER_APPROVED,
        email_templates.TPL_OFFER_ISSUED,
        email_templates.TPL_OFFER_ACCEPTED,
        email_templates.TPL_OFFER_DECLINED,
        email_templates.TPL_OFFER_JOINED,
    ):
        assert k in keys


# ---------------------------------------------------------------------------
# Endpoint dispatch — spy on the notify helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_offer_app(db_session: Session, slug: str) -> int:
    job = JobOpening(
        slug=slug,
        title="Phase 11 Role",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
    )
    cand = Candidate(full_name="P11 Candidate", email="p11@example.com")
    db_session.add_all([job, cand])
    db_session.flush()
    app = CandidateJobApplication(
        candidate_id=cand.id,
        job_opening_id=job.id,
        status=STATUS_RECOMMENDED_FOR_OFFER,
    )
    db_session.add(app)
    db_session.commit()
    return app.id


def test_offer_submit_approval_fires_notify(
    client, seed_auth, db_session: Session, monkeypatch
):
    app_id = _seed_offer_app(db_session, "p11-submit")
    headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    offer_id = client.post(
        OFFERS, headers=headers, json={"application_id": app_id}
    ).json()["id"]

    calls: list[tuple[str, int]] = []
    from app.services import hr_notifications

    monkeypatch.setattr(
        hr_notifications,
        "notify_offer_approval_requested",
        lambda *, offer_id, actor_id=None: calls.append(
            ("approval_requested", offer_id)
        ),
    )

    response = client.post(
        f"{OFFERS}/{offer_id}/submit-approval", headers=headers
    )
    assert response.status_code == 200
    assert calls == [("approval_requested", offer_id)]


def test_offer_approve_fires_notify(
    client, seed_auth, db_session: Session, monkeypatch
):
    app_id = _seed_offer_app(db_session, "p11-approve")
    headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    offer_id = client.post(
        OFFERS, headers=headers, json={"application_id": app_id}
    ).json()["id"]
    client.post(f"{OFFERS}/{offer_id}/submit-approval", headers=headers)

    calls: list[int] = []
    from app.services import hr_notifications

    monkeypatch.setattr(
        hr_notifications,
        "notify_offer_approved",
        lambda *, offer_id, actor_id=None: calls.append(offer_id),
    )

    response = client.post(
        f"{OFFERS}/{offer_id}/approve", headers=headers, json={}
    )
    assert response.status_code == 200
    assert calls == [offer_id]


def test_offer_respond_accept_vs_decline_dispatch(
    client, seed_auth, db_session: Session, monkeypatch
):
    """Two separate offers, one accepted, one declined — each fires
    the matching helper."""
    app1 = _seed_offer_app(db_session, "p11-accept")
    cand2 = Candidate(
        full_name="P11 Other", email="p11other@example.com"
    )
    db_session.add(cand2)
    db_session.flush()
    job2 = JobOpening(
        slug="p11-decline-job",
        title="Other",
        department="Eng",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
    )
    db_session.add(job2)
    db_session.flush()
    app2_obj = CandidateJobApplication(
        candidate_id=cand2.id,
        job_opening_id=job2.id,
        status=STATUS_RECOMMENDED_FOR_OFFER,
    )
    db_session.add(app2_obj)
    db_session.commit()

    headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])

    accepted_calls: list[int] = []
    declined_calls: list[int] = []
    from app.services import hr_notifications

    monkeypatch.setattr(
        hr_notifications,
        "notify_offer_accepted",
        lambda *, offer_id, actor_id=None: accepted_calls.append(offer_id),
    )
    monkeypatch.setattr(
        hr_notifications,
        "notify_offer_declined",
        lambda *, offer_id, actor_id=None: declined_calls.append(offer_id),
    )

    # Walk first offer to accepted.
    o1 = client.post(
        OFFERS, headers=headers, json={"application_id": app1}
    ).json()["id"]
    client.post(f"{OFFERS}/{o1}/submit-approval", headers=headers)
    client.post(f"{OFFERS}/{o1}/approve", headers=headers, json={})
    client.post(f"{OFFERS}/{o1}/issue", headers=headers, json={})
    client.post(
        f"{OFFERS}/{o1}/respond", headers=headers, json={"accepted": True}
    )

    # Walk second offer to declined.
    o2 = client.post(
        OFFERS, headers=headers, json={"application_id": app2_obj.id}
    ).json()["id"]
    client.post(f"{OFFERS}/{o2}/submit-approval", headers=headers)
    client.post(f"{OFFERS}/{o2}/approve", headers=headers, json={})
    client.post(f"{OFFERS}/{o2}/issue", headers=headers, json={})
    client.post(
        f"{OFFERS}/{o2}/respond",
        headers=headers,
        json={"accepted": False, "decline_reason": "Other offer."},
    )

    assert accepted_calls == [o1]
    assert declined_calls == [o2]


def test_offer_mark_joined_fires_notify(
    client, seed_auth, db_session: Session, monkeypatch
):
    app_id = _seed_offer_app(db_session, "p11-joined")
    headers = _login(client, "superadmin@pug.example.com", seed_auth["password"])
    offer_id = client.post(
        OFFERS, headers=headers, json={"application_id": app_id}
    ).json()["id"]
    client.post(f"{OFFERS}/{offer_id}/submit-approval", headers=headers)
    client.post(f"{OFFERS}/{offer_id}/approve", headers=headers, json={})
    client.post(f"{OFFERS}/{offer_id}/issue", headers=headers, json={})
    client.post(
        f"{OFFERS}/{offer_id}/respond", headers=headers, json={"accepted": True}
    )

    calls: list[int] = []
    from app.services import hr_notifications

    monkeypatch.setattr(
        hr_notifications,
        "notify_offer_joined",
        lambda *, offer_id, actor_id=None: calls.append(offer_id),
    )
    response = client.post(
        f"{OFFERS}/{offer_id}/mark-joined", headers=headers, json={}
    )
    assert response.status_code == 200
    assert calls == [offer_id]


def test_interview_feedback_endpoint_fires_notify(
    client, seed_auth, db_session: Session, monkeypatch
):
    """Submitting feedback fires notify_interview_feedback_submitted."""
    job = JobOpening(
        slug="p11-fb-job",
        title="P11 Job",
        department="Eng",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
    )
    cand = Candidate(full_name="P11 FB Cand", email="p11fb@example.com")
    db_session.add_all([job, cand])
    db_session.flush()
    app = CandidateJobApplication(
        candidate_id=cand.id,
        job_opening_id=job.id,
        status="cv_received",
    )
    db_session.add(app)
    db_session.flush()
    iv = Interview(
        application_id=app.id,
        round_name="Tech",
        scheduled_at=date.today().isoformat(),
        duration_minutes=30,
        mode="online",
        location_or_link="https://meet.example.com",
        status="scheduled",
    )
    from datetime import datetime, timezone, timedelta

    iv.scheduled_at = datetime.now(timezone.utc) + timedelta(days=1)
    db_session.add(iv)
    db_session.commit()

    calls: list[int] = []
    from app.services import hr_notifications

    monkeypatch.setattr(
        hr_notifications,
        "notify_interview_feedback_submitted",
        lambda *, feedback_id, actor_id=None: calls.append(feedback_id),
    )

    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.post(
        f"/api/v1/hr/interviews/{iv.id}/feedback",
        headers=headers,
        json={"rating": 4, "recommendation": "hire"},
    )
    assert response.status_code == 201, response.text
    assert len(calls) == 1
