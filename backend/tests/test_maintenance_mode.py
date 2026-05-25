"""Tests for the under-construction / maintenance-mode toggle.

The flag lives on ``site_settings.maintenance_mode_enabled``. The
backend's job is just to round-trip it (and the optional message +
ETA fields) through the admin PATCH and the public GET. The actual
"render the maintenance page instead of the site" lives in the
Next.js public layout, so there's nothing to assert here about
rendered HTML — only that the API surface is correct.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.cms import SiteSetting


PUBLIC_SETTINGS = "/api/v1/public/site-settings"
ADMIN_SETTINGS = "/api/v1/admin/cms/site-settings"
ADMIN_LOGIN = "/api/v1/admin/auth/login"


def _auth(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(ADMIN_LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_maintenance_mode_defaults_to_off_on_public_endpoint(client):
    """A fresh deployment must not accidentally hide the site."""
    body = client.get(PUBLIC_SETTINGS).json()
    assert body["maintenance_mode_enabled"] is False
    assert body["maintenance_message"] is None
    assert body["maintenance_eta"] is None


def test_admin_can_enable_maintenance_mode(client, seed_auth, db_session):
    headers = _auth(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    resp = client.patch(
        ADMIN_SETTINGS,
        headers=headers,
        json={
            "maintenance_mode_enabled": True,
            "maintenance_message": "Quick polish — back in an hour.",
            "maintenance_eta": "Today 4 PM GMT",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["maintenance_mode_enabled"] is True
    assert body["maintenance_message"] == "Quick polish — back in an hour."
    assert body["maintenance_eta"] == "Today 4 PM GMT"

    # And it's persisted — the public endpoint sees it too.
    pub = client.get(PUBLIC_SETTINGS).json()
    assert pub["maintenance_mode_enabled"] is True
    assert pub["maintenance_message"] == "Quick polish — back in an hour."
    assert pub["maintenance_eta"] == "Today 4 PM GMT"


def test_admin_can_disable_maintenance_mode(client, seed_auth, db_session):
    """Turning it off clears the toggle but leaves the message in place
    (so it's ready next time)."""
    db_session.add(
        SiteSetting(
            id=1,
            site_name="PUG",
            maintenance_mode_enabled=True,
            maintenance_message="prior copy",
        )
    )
    db_session.commit()

    headers = _auth(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    resp = client.patch(
        ADMIN_SETTINGS,
        headers=headers,
        json={"maintenance_mode_enabled": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["maintenance_mode_enabled"] is False
    # Previously-set message survives (admin didn't touch it).
    assert body["maintenance_message"] == "prior copy"


def test_maintenance_toggle_writes_audit_log(client, seed_auth, db_session):
    """Like every CMS write, toggling maintenance leaves an audit trail."""
    from app.models.auth import AuditLog
    from sqlalchemy import select

    headers = _auth(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    client.patch(
        ADMIN_SETTINGS,
        headers=headers,
        json={"maintenance_mode_enabled": True},
    )

    rows = list(db_session.execute(select(AuditLog)).scalars())
    cms_writes = [r for r in rows if r.action == "cms.site_settings.update"]
    assert cms_writes, "maintenance toggle did not write an audit row"
    assert "maintenance_mode_enabled" in (cms_writes[-1].details or {}).get(
        "changed_keys", []
    )


def test_maintenance_mode_requires_website_scope(client, seed_auth):
    """HR-only users cannot flip the site into maintenance mode."""
    hr = client.post(
        "/api/v1/hr/auth/login",
        json={
            "email": "hr@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    headers = {"Authorization": f"Bearer {hr.json()['access_token']}"}

    resp = client.patch(
        ADMIN_SETTINGS,
        headers=headers,
        json={"maintenance_mode_enabled": True},
    )
    assert resp.status_code == 403
