"""Integration tests for the /admin/auth and /hr/auth endpoints.

Covers the Phase 2 deliverable:
- Website admin can log in separately
- HR admin can log in separately
- HR-only user cannot log in via /admin/auth/login (wrong scope -> 403)
- Website-only user cannot log in via /hr/auth/login   (wrong scope -> 403)
- Invalid credentials return 401
- /me requires authentication and is scope-isolated
- Login/logout/failed-login attempts produce audit_logs rows
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog


ADMIN_LOGIN = "/api/v1/admin/auth/login"
ADMIN_ME = "/api/v1/admin/auth/me"
ADMIN_LOGOUT = "/api/v1/admin/auth/logout"

HR_LOGIN = "/api/v1/hr/auth/login"
HR_ME = "/api/v1/hr/auth/me"
HR_LOGOUT = "/api/v1/hr/auth/logout"


def _login(client: TestClient, url: str, email: str, password: str):
    return client.post(url, json={"email": email, "password": password})


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_website_admin_can_login_at_admin_endpoint(client, seed_auth):
    response = _login(
        client, ADMIN_LOGIN, "webadmin@pug.example.com", seed_auth["password"]
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert "website" in body["user"]["scopes"]
    assert body["user"]["email"] == "webadmin@pug.example.com"


def test_hr_admin_can_login_at_hr_endpoint(client, seed_auth):
    response = _login(
        client, HR_LOGIN, "hr@pug.example.com", seed_auth["password"]
    )
    assert response.status_code == 200
    body = response.json()
    assert "hr" in body["user"]["scopes"]


def test_super_admin_can_login_at_both_endpoints(client, seed_auth):
    pw = seed_auth["password"]
    r_admin = _login(client, ADMIN_LOGIN, "superadmin@pug.example.com", pw)
    r_hr = _login(client, HR_LOGIN, "superadmin@pug.example.com", pw)
    assert r_admin.status_code == 200
    assert r_hr.status_code == 200


# ---------------------------------------------------------------------------
# Cross-scope isolation (the headline Phase 2 deliverable)
# ---------------------------------------------------------------------------


def test_hr_user_cannot_login_at_admin_endpoint(client, seed_auth):
    response = _login(
        client, ADMIN_LOGIN, "hr@pug.example.com", seed_auth["password"]
    )
    assert response.status_code == 403
    assert "does not have access" in response.json()["detail"].lower()


def test_website_user_cannot_login_at_hr_endpoint(client, seed_auth):
    response = _login(
        client, HR_LOGIN, "webadmin@pug.example.com", seed_auth["password"]
    )
    assert response.status_code == 403


def test_admin_token_rejected_on_hr_me(client, seed_auth):
    pw = seed_auth["password"]
    login = _login(client, ADMIN_LOGIN, "webadmin@pug.example.com", pw).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    response = client.get(HR_ME, headers=headers)
    assert response.status_code == 403


def test_hr_token_rejected_on_admin_me(client, seed_auth):
    pw = seed_auth["password"]
    login = _login(client, HR_LOGIN, "hr@pug.example.com", pw).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    response = client.get(ADMIN_ME, headers=headers)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Negative paths
# ---------------------------------------------------------------------------


def test_invalid_password_returns_401(client, seed_auth):
    response = _login(client, ADMIN_LOGIN, "webadmin@pug.example.com", "nope")
    assert response.status_code == 401


def test_unknown_email_returns_401(client, seed_auth):
    response = _login(client, ADMIN_LOGIN, "ghost@pug.example.com", "whatever")
    assert response.status_code == 401


def test_inactive_user_cannot_login(client, seed_auth):
    response = _login(
        client, ADMIN_LOGIN, "disabled@pug.example.com", seed_auth["password"]
    )
    # Disabled accounts fail the credential gate with the same generic 401.
    assert response.status_code == 401


def test_me_requires_authentication(client, seed_auth):
    assert client.get(ADMIN_ME).status_code == 401
    assert client.get(HR_ME).status_code == 401


def test_logout_writes_audit_entry(client, seed_auth, db_session: Session):
    pw = seed_auth["password"]
    login = _login(client, ADMIN_LOGIN, "webadmin@pug.example.com", pw).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    response = client.post(ADMIN_LOGOUT, headers=headers)
    assert response.status_code == 204

    actions = [
        row.action
        for row in db_session.execute(select(AuditLog)).scalars()
    ]
    assert "auth.login.success" in actions
    assert "auth.logout" in actions


def test_failed_login_writes_audit_entry(client, seed_auth, db_session: Session):
    _login(client, ADMIN_LOGIN, "webadmin@pug.example.com", "wrong-password")

    rows = db_session.execute(
        select(AuditLog).where(AuditLog.action == "auth.login.failed")
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].details.get("reason") == "invalid_credentials"


def test_wrong_scope_login_writes_audit_entry(client, seed_auth, db_session: Session):
    _login(client, ADMIN_LOGIN, "hr@pug.example.com", seed_auth["password"])

    rows = db_session.execute(
        select(AuditLog).where(AuditLog.action == "auth.login.wrong_scope")
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].scope == "website"
