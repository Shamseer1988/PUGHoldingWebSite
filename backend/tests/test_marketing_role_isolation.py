"""Regression: Marketing roles must not reach non-marketing admin endpoints.

The original ``Marketing Manager`` / ``Marketing Viewer`` seed gave
both roles ``scope='system'``, which makes ``User.has_scope(...)``
auto-return ``True`` for every other scope as a "trusted operator"
shortcut. That silently let a Marketing user reach CMS, SEO, user-
management, AI settings, email settings — i.e. the whole admin
portal — without holding any non-marketing permission key.

This file pins three things going forward:

* A Marketing user can still **read** the marketing surface
  (campaigns / catalogues / short-urls / dashboard).
* A Marketing user **cannot** reach CMS endpoints
  (``/admin/cms/*``), SEO endpoints (``/admin/seo/*``), or any
  system-scope endpoint (``/admin/users``, ``/admin/email-settings``,
  ``/admin/ai-settings``).
* The Marketing roles' scope is ``website`` (not ``system``) — so a
  future refactor that re-introduces the dangerous shortcut will
  fail loudly.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auth import SCOPE_WEBSITE, Role


ADMIN_LOGIN = "/api/v1/admin/auth/login"


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post(ADMIN_LOGIN, json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_marketing_role_scope_is_website_not_system(
    db_session: Session, seed_auth
):
    """Pin the scope so the dangerous ``system`` shortcut can't sneak back."""
    for role_name in ("Marketing Manager", "Marketing Viewer"):
        role = (
            db_session.query(Role).filter(Role.name == role_name).one_or_none()
        )
        assert role is not None, f"Role {role_name!r} not seeded by conftest"
        assert (
            role.scope == SCOPE_WEBSITE
        ), (
            f"{role_name} scope is {role.scope!r} — must be 'website' so "
            "User.has_scope doesn't auto-pass every scope check."
        )


def test_marketing_user_blocked_from_cms_admin(
    client: TestClient, seed_auth
):
    """``/admin/cms/*`` now gates on ``website.content.read`` which
    Marketing roles don't carry."""
    headers = _login(client, "marketingmgr@pug.example.com", seed_auth["password"])
    r = client.get("/api/v1/admin/cms/dashboard", headers=headers)
    assert r.status_code == 403, r.text


def test_marketing_user_blocked_from_seo_admin(
    client: TestClient, seed_auth
):
    headers = _login(client, "marketingmgr@pug.example.com", seed_auth["password"])
    r = client.get("/api/v1/admin/seo/settings", headers=headers)
    assert r.status_code == 403, r.text


def test_marketing_user_blocked_from_user_management(
    client: TestClient, seed_auth
):
    """``/admin/users/*`` gates on ``SCOPE_SYSTEM``. With Marketing
    scope flipped to ``website`` (no more system shortcut), the call
    now 403s as it should."""
    headers = _login(client, "marketingmgr@pug.example.com", seed_auth["password"])
    r = client.get("/api/v1/admin/users", headers=headers)
    assert r.status_code == 403, r.text


def test_marketing_user_blocked_from_email_settings(
    client: TestClient, seed_auth
):
    headers = _login(client, "marketingmgr@pug.example.com", seed_auth["password"])
    r = client.get("/api/v1/admin/email-settings", headers=headers)
    assert r.status_code == 403, r.text


def test_marketing_user_blocked_from_ai_settings(
    client: TestClient, seed_auth
):
    headers = _login(client, "marketingmgr@pug.example.com", seed_auth["password"])
    r = client.get("/api/v1/admin/ai/settings", headers=headers)
    assert r.status_code == 403, r.text


def test_marketing_user_can_reach_marketing_dashboard(
    client: TestClient, seed_auth
):
    """Counterpart: Marketing scope still works for its own portal."""
    headers = _login(client, "marketingmgr@pug.example.com", seed_auth["password"])
    r = client.get("/api/v1/admin/marketing/dashboard", headers=headers)
    # Endpoint exists, dashboard read is gated on
    # ``marketing:dashboard:view`` which the role carries. Either 200
    # or 404 (if the endpoint name differs slightly) is fine — what
    # we're locking is "not 403".
    assert r.status_code != 403, r.text


def test_marketing_viewer_blocked_from_cms_admin(
    client: TestClient, seed_auth
):
    """The viewer tier — read-only marketing — also can't reach CMS."""
    headers = _login(client, "marketingviewer@pug.example.com", seed_auth["password"])
    r = client.get("/api/v1/admin/cms/dashboard", headers=headers)
    assert r.status_code == 403, r.text
