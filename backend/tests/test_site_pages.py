"""Tests for the predefined site-pages CMS endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.cms import SITE_PAGE_KEYS, SitePage


ADMIN = "/api/v1/admin/cms/site-pages"
PUBLIC = "/api/v1/public/site-pages"
LOGIN = "/api/v1/admin/auth/login"


def _admin_token(client: TestClient, password: str) -> dict:
    resp = client.post(
        LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_admin_list_creates_rows_for_every_known_key(client, seed_auth):
    """A fresh install (no rows yet) should still return one row per
    page key — they're created on the fly so the admin UI never sees
    empty state."""
    headers = _admin_token(client, seed_auth["password"])
    resp = client.get(ADMIN, headers=headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    returned_keys = {r["page_key"] for r in rows}
    assert returned_keys == set(SITE_PAGE_KEYS)
    # Empty defaults — null fields, {} sections.
    for row in rows:
        assert row["sections"] == {}


def test_admin_get_unknown_key_404(client, seed_auth):
    headers = _admin_token(client, seed_auth["password"])
    resp = client.get(f"{ADMIN}/not-a-page", headers=headers)
    assert resp.status_code == 404


def test_admin_can_update_hero_and_sections(client, seed_auth, db_session):
    headers = _admin_token(client, seed_auth["password"])
    payload = {
        "hero_eyebrow": "About Paris United Group",
        "hero_title": "A diversified holding group",
        "hero_description": "We operate across retail, distribution, and services.",
        "banner_image_url": "/uploads/img/about-hero.jpg",
        "sections": {
            "vision": {"title": "Our vision", "body": "To be the most trusted..."},
            "mission": {"title": "Our mission", "body": "We bring..."},
            "history_intro": {"body": "We started with one..."},
        },
    }
    resp = client.put(f"{ADMIN}/about", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["hero_title"] == payload["hero_title"]
    assert body["sections"]["vision"]["title"] == "Our vision"
    assert body["banner_image_url"] == "/uploads/img/about-hero.jpg"

    row = db_session.execute(
        SitePage.__table__.select().where(SitePage.page_key == "about")
    ).first()
    assert row is not None


def test_public_endpoint_returns_seeded_content(client, seed_auth):
    """After an admin edit, the public route returns the latest copy."""
    headers = _admin_token(client, seed_auth["password"])
    client.put(
        f"{ADMIN}/careers",
        headers=headers,
        json={"hero_title": "Build your career with us"},
    )
    pub = client.get(f"{PUBLIC}/careers")
    assert pub.status_code == 200
    assert pub.json()["hero_title"] == "Build your career with us"


def test_public_endpoint_404_for_unknown_key(client):
    assert client.get(f"{PUBLIC}/not-a-page").status_code == 404


def test_admin_update_writes_audit_log(client, seed_auth, db_session):
    from app.models.auth import AuditLog
    from sqlalchemy import select

    headers = _admin_token(client, seed_auth["password"])
    client.put(
        f"{ADMIN}/contact",
        headers=headers,
        json={"hero_title": "Talk to us"},
    )
    rows = list(db_session.execute(select(AuditLog)).scalars())
    site_writes = [r for r in rows if r.action == "cms.site_page.update"]
    assert site_writes, "site_page update did not write an audit row"
    assert site_writes[-1].target_id == "contact"


def test_site_page_update_requires_website_scope(client, seed_auth):
    """HR-only users can't edit the site copy."""
    hr = client.post(
        "/api/v1/hr/auth/login",
        json={
            "email": "hr@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    headers = {"Authorization": f"Bearer {hr.json()['access_token']}"}
    resp = client.put(
        f"{ADMIN}/about", headers=headers, json={"hero_title": "x"}
    )
    assert resp.status_code == 403
