"""Offer-letter template CRUD + apply-to-offer rendering."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    STATUS_RECOMMENDED_FOR_OFFER,
    Candidate,
    CandidateJobApplication,
    JobOpening,
)

HR_LOGIN = "/api/v1/hr/auth/login"
ADMIN_LOGIN = "/api/v1/admin/auth/login"
TEMPLATES = "/api/v1/hr/offer-templates"
OFFERS = "/api/v1/hr/offers"


def _login(client: TestClient, email: str, password: str) -> dict:
    r = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _su(client, seed_auth):
    return _login(client, "superadmin@pug.example.com", seed_auth["password"])


def _make_application(db_session: Session, slug: str = "tpl-job") -> CandidateJobApplication:
    job = JobOpening(
        slug=slug,
        title="Template Job",
        department="Engineering",
        company="PUG",
        location="Doha",
        status=JOB_STATUS_OPEN,
        approval_status="approved",
        publish_status="published",
    )
    cand = Candidate(full_name="Asha Khan", email="asha@example.com")
    db_session.add_all([job, cand])
    db_session.flush()
    app = CandidateJobApplication(
        candidate_id=cand.id,
        job_opening_id=job.id,
        status=STATUS_RECOMMENDED_FOR_OFFER,
    )
    db_session.add(app)
    db_session.commit()
    return app


def test_templates_require_hr_scope(client, seed_auth):
    r = client.post(
        ADMIN_LOGIN,
        json={"email": "webadmin@pug.example.com", "password": seed_auth["password"]},
    )
    admin_token = r.json()["access_token"]
    rejected = client.get(
        TEMPLATES, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert rejected.status_code == 403


def test_tokens_endpoint_lists_merge_fields(client, seed_auth):
    headers = _su(client, seed_auth)
    r = client.get(f"{TEMPLATES}/tokens", headers=headers)
    assert r.status_code == 200, r.text
    tokens = {t["token"] for t in r.json()}
    assert {"candidate_name", "position", "salary", "joining_date"} <= tokens


def test_template_crud_and_single_default(client, seed_auth):
    headers = _su(client, seed_auth)

    t1 = client.post(
        TEMPLATES,
        headers=headers,
        json={"name": "Standard", "body": "Hello {{candidate_name}}", "is_default": True},
    )
    assert t1.status_code == 201, t1.text
    t1_id = t1.json()["id"]
    assert t1.json()["is_default"] is True

    # Second default clears the first.
    t2 = client.post(
        TEMPLATES,
        headers=headers,
        json={"name": "Senior", "body": "Dear {{candidate_name}}", "is_default": True},
    )
    assert t2.status_code == 201
    assert client.get(f"{TEMPLATES}/{t1_id}", headers=headers).json()["is_default"] is False

    listed = client.get(TEMPLATES, headers=headers).json()
    assert {row["name"] for row in listed} >= {"Standard", "Senior"}

    patched = client.patch(
        f"{TEMPLATES}/{t1_id}", headers=headers, json={"body": "Updated body"}
    )
    assert patched.status_code == 200 and patched.json()["body"] == "Updated body"

    assert client.delete(f"{TEMPLATES}/{t1_id}", headers=headers).status_code == 204
    assert client.get(f"{TEMPLATES}/{t1_id}", headers=headers).status_code == 404


def test_apply_template_renders_merge_fields(client, seed_auth, db_session: Session):
    headers = _su(client, seed_auth)
    app = _make_application(db_session, slug="tpl-apply")

    offer_id = client.post(
        OFFERS, headers=headers, json={"application_id": app.id}
    ).json()["id"]
    # Fill the fields the template references.
    client.patch(
        f"{OFFERS}/{offer_id}",
        headers=headers,
        json={"position": "Site Engineer", "salary_offered": 12000},
    )

    tpl_id = client.post(
        TEMPLATES,
        headers=headers,
        json={
            "name": "Render test",
            "body": "Dear {{candidate_name}}, role {{position}}, salary {{salary}} at {{company}}.",
        },
    ).json()["id"]

    applied = client.post(
        f"{OFFERS}/{offer_id}/apply-template",
        headers=headers,
        json={"template_id": tpl_id},
    )
    assert applied.status_code == 200, applied.text
    assert (
        applied.json()["letter_body"]
        == "Dear Asha Khan, role Site Engineer, salary QAR 12,000 at PUG."
    )


def test_apply_template_404_on_unknown(client, seed_auth, db_session: Session):
    headers = _su(client, seed_auth)
    app = _make_application(db_session, slug="tpl-404")
    offer_id = client.post(
        OFFERS, headers=headers, json={"application_id": app.id}
    ).json()["id"]
    r = client.post(
        f"{OFFERS}/{offer_id}/apply-template",
        headers=headers,
        json={"template_id": 999999},
    )
    assert r.status_code == 404


def test_letter_body_editable_via_patch(client, seed_auth, db_session: Session):
    headers = _su(client, seed_auth)
    app = _make_application(db_session, slug="tpl-edit")
    offer_id = client.post(
        OFFERS, headers=headers, json={"application_id": app.id}
    ).json()["id"]

    client.patch(
        f"{OFFERS}/{offer_id}",
        headers=headers,
        json={"letter_body": "Hand-edited letter body."},
    )
    got = client.get(f"{OFFERS}/{offer_id}", headers=headers).json()
    assert got["letter_body"] == "Hand-edited letter body."
