"""Integration tests for the Phase 5 Website Admin CMS endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
from app.models.cms import Company


ADMIN_LOGIN = "/api/v1/admin/auth/login"
CMS = "/api/v1/admin/cms"


def _auth(client: TestClient, email: str, password: str) -> dict:
    response = client.post(
        ADMIN_LOGIN, json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Scope isolation
# ---------------------------------------------------------------------------


def test_cms_requires_website_scope(client, seed_auth):
    # HR token: should be rejected by every CMS endpoint.
    hr_login = client.post(
        "/api/v1/hr/auth/login",
        json={"email": "hr@pug.example.com", "password": seed_auth["password"]},
    )
    hr_token = hr_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {hr_token}"}

    for url in [
        f"{CMS}/dashboard",
        f"{CMS}/hero-slides",
        f"{CMS}/companies",
        f"{CMS}/news",
        f"{CMS}/contact-messages",
    ]:
        response = client.get(url, headers=headers)
        assert response.status_code == 403, f"{url} should be 403, got {response.status_code}"


def test_cms_requires_authentication(client, seed_auth):
    response = client.get(f"{CMS}/dashboard")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Companies CRUD
# ---------------------------------------------------------------------------


def test_company_crud_roundtrip(client, seed_auth, db_session: Session):
    headers = _auth(
        client, "webadmin@pug.example.com", seed_auth["password"]
    )

    # Empty initially
    assert client.get(f"{CMS}/companies", headers=headers).json() == []

    # Create
    payload = {
        "slug": "test-co",
        "name": "Test Co",
        "category": "retail",
        "initials": "TC",
        "short_description": "A test company",
        "services": ["Alpha", "Beta"],
    }
    create_resp = client.post(f"{CMS}/companies", json=payload, headers=headers)
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert created["slug"] == "test-co"
    assert [s["name"] for s in created["services"]] == ["Alpha", "Beta"]
    company_id = created["id"]

    # Update (rename + replace services)
    patch_resp = client.patch(
        f"{CMS}/companies/{company_id}",
        json={"name": "Test Co Renamed", "services": ["Gamma"]},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Test Co Renamed"
    assert [s["name"] for s in patch_resp.json()["services"]] == ["Gamma"]

    # Audit log contains both events
    audit_actions = [
        row.action for row in db_session.execute(select(AuditLog)).scalars()
    ]
    assert "cms.company.create" in audit_actions
    assert "cms.company.update" in audit_actions

    # Delete
    del_resp = client.delete(
        f"{CMS}/companies/{company_id}", headers=headers
    )
    assert del_resp.status_code == 204

    # Gone
    assert client.get(f"{CMS}/companies", headers=headers).json() == []


def test_company_create_rejects_duplicate_slug(client, seed_auth):
    headers = _auth(client, "webadmin@pug.example.com", seed_auth["password"])
    payload = {
        "slug": "dup",
        "name": "Dup 1",
        "category": "services",
        "initials": "D1",
    }
    assert client.post(f"{CMS}/companies", json=payload, headers=headers).status_code == 201
    dup = client.post(f"{CMS}/companies", json=payload, headers=headers)
    assert dup.status_code == 409


# ---------------------------------------------------------------------------
# News CRUD
# ---------------------------------------------------------------------------


def test_news_create_and_list(client, seed_auth):
    headers = _auth(client, "webadmin@pug.example.com", seed_auth["password"])
    payload = {
        "slug": "hello-world",
        "title": "Hello World",
        "category": "company",
        "summary": "Saying hello",
        "body": "Hello.",
    }
    create = client.post(f"{CMS}/news", json=payload, headers=headers)
    assert create.status_code == 201, create.text
    assert create.json()["slug"] == "hello-world"

    listed = client.get(f"{CMS}/news", headers=headers)
    assert listed.status_code == 200
    slugs = [n["slug"] for n in listed.json()]
    assert "hello-world" in slugs


# ---------------------------------------------------------------------------
# Hero slides
# ---------------------------------------------------------------------------


def test_hero_slide_lifecycle(client, seed_auth):
    headers = _auth(client, "webadmin@pug.example.com", seed_auth["password"])

    create = client.post(
        f"{CMS}/hero-slides",
        json={"title": "Slide A", "display_order": 1},
        headers=headers,
    )
    assert create.status_code == 201
    slide_id = create.json()["id"]

    patch = client.patch(
        f"{CMS}/hero-slides/{slide_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["is_active"] is False

    listed = client.get(f"{CMS}/hero-slides", headers=headers).json()
    assert any(s["id"] == slide_id for s in listed)

    assert (
        client.delete(f"{CMS}/hero-slides/{slide_id}", headers=headers).status_code
        == 204
    )


# ---------------------------------------------------------------------------
# Site settings (auto-created on first read)
# ---------------------------------------------------------------------------


def test_site_settings_auto_create_and_update(client, seed_auth):
    headers = _auth(client, "webadmin@pug.example.com", seed_auth["password"])

    first = client.get(f"{CMS}/site-settings", headers=headers)
    assert first.status_code == 200
    assert first.json()["site_name"]  # default value populated

    patched = client.patch(
        f"{CMS}/site-settings",
        json={"contact_phone": "+974 1234"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["contact_phone"] == "+974 1234"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_dashboard_returns_summary(client, seed_auth, db_session: Session):
    # Seed one company so the count > 0
    db_session.add(
        Company(slug="seed-co", name="Seed", category="retail", initials="SC")
    )
    db_session.commit()

    headers = _auth(client, "webadmin@pug.example.com", seed_auth["password"])
    response = client.get(f"{CMS}/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    keys = {s["key"] for s in body["stats"]}
    assert {"companies", "news", "leadership", "hero_slides", "contact_unread", "subscribers"} <= keys
    assert isinstance(body["contact_messages_per_month"], list)
    assert isinstance(body["news_per_month"], list)
