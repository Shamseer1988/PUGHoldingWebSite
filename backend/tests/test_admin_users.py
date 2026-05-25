"""Tests for the Phase-5 follow-up admin Users & Roles endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auth import AuditLog, User


ADMIN_LOGIN = "/api/v1/admin/auth/login"
USERS = "/api/v1/admin/users"
ROLES = "/api/v1/admin/roles"


def _system_headers(client: TestClient, password: str) -> dict:
    response = client.post(
        ADMIN_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def test_admin_lists_roles(client, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    body = client.get(ROLES, headers=headers).json()
    names = [r["name"] for r in body]
    assert "Super Admin" in names
    assert "Website Admin" in names
    assert "HR Manager" in names


def test_admin_filters_roles_by_scope(client, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    body = client.get(f"{ROLES}?scope=hr", headers=headers).json()
    assert all(r["scope"] == "hr" for r in body)
    assert len(body) >= 1


# ---------------------------------------------------------------------------
# List users
# ---------------------------------------------------------------------------


def test_admin_lists_users(client, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    body = client.get(USERS, headers=headers).json()
    emails = {u["email"] for u in body}
    # The four seeded users are visible
    assert {
        "superadmin@pug.example.com",
        "webadmin@pug.example.com",
        "hr@pug.example.com",
        "disabled@pug.example.com",
    } <= emails
    # Each row carries the roles + derived scopes
    super_row = next(u for u in body if u["email"] == "superadmin@pug.example.com")
    assert super_row["is_superuser"] is True
    assert "system" in super_row["scopes"]
    assert any(r["name"] == "Super Admin" for r in super_row["roles"])


def test_list_can_hide_inactive_users(client, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    body = client.get(f"{USERS}?include_inactive=false", headers=headers).json()
    emails = {u["email"] for u in body}
    assert "disabled@pug.example.com" not in emails


def test_list_filters_by_scope(client, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    body = client.get(f"{USERS}?scope=hr", headers=headers).json()
    emails = {u["email"] for u in body}
    # Super admin has system scope which counts as HR via has_scope —
    # but the filter is strict on assigned role scopes, so only the
    # HR user matches.
    assert "hr@pug.example.com" in emails
    # webadmin has only website scope, must not appear.
    assert "webadmin@pug.example.com" not in emails


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_user_with_role(client, db_session: Session, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    roles = client.get(ROLES, headers=headers).json()
    hr_role = next(r for r in roles if r["name"] == "HR Manager")

    response = client.post(
        USERS,
        headers=headers,
        json={
            "email": "new.recruiter@pug.example.com",
            "full_name": "New Recruiter",
            "password": "FreshPass!22",
            "role_ids": [hr_role["id"]],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "new.recruiter@pug.example.com"
    assert body["is_active"] is True
    assert "hr" in body["scopes"]
    assert {r["name"] for r in body["roles"]} == {"HR Manager"}

    # Newly created user can actually log in via HR login.
    login = client.post(
        "/api/v1/hr/auth/login",
        json={
            "email": "new.recruiter@pug.example.com",
            "password": "FreshPass!22",
        },
    )
    assert login.status_code == 200

    # Audit log entry created
    audit_rows = db_session.query(AuditLog).filter(
        AuditLog.action == "users.create"
    ).all()
    assert len(audit_rows) == 1
    assert audit_rows[0].target_type == "user"


def test_create_user_rejects_duplicate_email(client, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    response = client.post(
        USERS,
        headers=headers,
        json={
            "email": "hr@pug.example.com",
            "full_name": "Different person",
            "password": "FreshPass!22",
            "role_ids": [],
        },
    )
    assert response.status_code == 409


def test_create_user_rejects_unknown_role_id(client, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    response = client.post(
        USERS,
        headers=headers,
        json={
            "email": "weird@pug.example.com",
            "full_name": "Weird",
            "password": "FreshPass!22",
            "role_ids": [9999],
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_user_name_and_roles(client, db_session: Session, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    roles = client.get(ROLES, headers=headers).json()
    super_id = next(r["id"] for r in roles if r["name"] == "Super Admin")
    hr_user_id = seed_auth["users"]["hr@pug.example.com"].id

    response = client.patch(
        f"{USERS}/{hr_user_id}",
        headers=headers,
        json={
            "full_name": "HR Manager Promoted",
            "role_ids": [super_id],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["full_name"] == "HR Manager Promoted"
    assert {r["name"] for r in body["roles"]} == {"Super Admin"}
    assert "system" in body["scopes"]


def test_update_user_password_rotates_hash(client, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    user_id = seed_auth["users"]["hr@pug.example.com"].id

    response = client.patch(
        f"{USERS}/{user_id}",
        headers=headers,
        json={"password": "RotatedPass!99"},
    )
    assert response.status_code == 200

    # Old password no longer works.
    old = client.post(
        "/api/v1/hr/auth/login",
        json={
            "email": "hr@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    assert old.status_code == 401

    # New password works.
    fresh = client.post(
        "/api/v1/hr/auth/login",
        json={
            "email": "hr@pug.example.com",
            "password": "RotatedPass!99",
        },
    )
    assert fresh.status_code == 200


def test_update_rejects_self_deactivation(client, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    super_id = seed_auth["users"]["superadmin@pug.example.com"].id

    response = client.patch(
        f"{USERS}/{super_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 400
    assert "deactivate your own" in response.json()["detail"].lower()


def test_update_rejects_self_demotion(client, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    super_id = seed_auth["users"]["superadmin@pug.example.com"].id

    response = client.patch(
        f"{USERS}/{super_id}",
        headers=headers,
        json={"is_superuser": False},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Deactivate (DELETE)
# ---------------------------------------------------------------------------


def test_deactivate_user_clears_roles_and_blocks_login(
    client, db_session: Session, seed_auth
):
    headers = _system_headers(client, seed_auth["password"])
    user_id = seed_auth["users"]["hr@pug.example.com"].id

    response = client.delete(f"{USERS}/{user_id}", headers=headers)
    assert response.status_code == 204

    # The test session keeps a copy of the user from the seed fixture —
    # expire it so we re-read the actual row the endpoint wrote.
    db_session.expire_all()
    refreshed = db_session.get(User, user_id)
    assert refreshed is not None
    assert refreshed.is_active is False
    assert refreshed.roles == []

    # Login attempt fails because user is inactive.
    login = client.post(
        "/api/v1/hr/auth/login",
        json={
            "email": "hr@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    assert login.status_code == 401


def test_deactivate_self_blocked(client, seed_auth):
    headers = _system_headers(client, seed_auth["password"])
    super_id = seed_auth["users"]["superadmin@pug.example.com"].id
    response = client.delete(f"{USERS}/{super_id}", headers=headers)
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Scope isolation — HR / website-only users can't reach this surface.
# ---------------------------------------------------------------------------


def test_users_endpoint_blocks_website_only_user(client, seed_auth):
    login = client.post(
        ADMIN_LOGIN,
        json={
            "email": "webadmin@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get(USERS, headers=headers)
    assert response.status_code == 403


def test_users_endpoint_blocks_hr_only_user(client, seed_auth):
    login = client.post(
        "/api/v1/hr/auth/login",
        json={
            "email": "hr@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get(USERS, headers=headers)
    assert response.status_code == 403
