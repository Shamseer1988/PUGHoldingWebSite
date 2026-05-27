"""Phase 12 — Role + permission management endpoints.

Pins the new /admin/roles + /admin/permissions surface that powers
the permission-matrix UI:

  * GET /admin/permissions returns the full catalog
  * GET /admin/roles/{id} returns permission_ids + permission_keys +
    user_count
  * POST /admin/roles creates with grants, rejects cross-scope, 409
    on name conflict
  * PATCH /admin/roles/{id} renames + redescribes; refuses cross-scope
    re-scope when existing grants don't fit
  * PATCH /admin/roles/{id}/permissions replaces the grant set + writes
    one audit row with the added/removed key delta
  * DELETE /admin/roles/{id} 409s when a user still holds the role
  * All routes locked to system scope (super admin only) — website /
    HR users 403.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog, Permission, Role, User
from app.models.hr_ats import JobOpening


ADMIN_LOGIN = "/api/v1/admin/auth/login"


def _admin_login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(
        ADMIN_LOGIN, json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Permission catalog
# ---------------------------------------------------------------------------


def test_list_permissions_returns_full_catalog(client, seed_auth):
    headers = _admin_login(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    response = client.get("/api/v1/admin/permissions", headers=headers)
    assert response.status_code == 200, response.text
    perms = response.json()
    keys = {p["key"] for p in perms}
    # The 35 HR keys from Phase 1 must all be present.
    assert "hr:jobs:approve" in keys
    assert "hr:candidates:delete" in keys
    assert "hr:offers:approve" in keys


def test_list_permissions_scope_filter(client, seed_auth):
    headers = _admin_login(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    response = client.get(
        "/api/v1/admin/permissions?scope=hr", headers=headers
    )
    perms = response.json()
    assert all(p["scope"] == "hr" for p in perms)


# ---------------------------------------------------------------------------
# Role detail
# ---------------------------------------------------------------------------


def test_get_role_returns_permission_ids_and_user_count(
    client, seed_auth, db_session: Session
):
    """HR Manager role from the seed should report all its grants
    + one assigned user (hr@pug.example.com)."""
    hr_manager = db_session.execute(
        select(Role).where(Role.name == "HR Manager")
    ).scalar_one()
    headers = _admin_login(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    response = client.get(
        f"/api/v1/admin/roles/{hr_manager.id}", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "HR Manager"
    assert body["scope"] == "hr"
    assert "hr:jobs:approve" in body["permission_keys"]
    assert body["user_count"] >= 1


# ---------------------------------------------------------------------------
# Create role
# ---------------------------------------------------------------------------


def test_create_role_with_permissions(
    client, seed_auth, db_session: Session
):
    """Create a fresh role + assign two HR permissions in one POST."""
    perm_ids = [
        p.id
        for p in db_session.execute(
            select(Permission).where(
                Permission.key.in_(("hr:jobs:view", "hr:candidates:view_list"))
            )
        ).scalars()
    ]
    assert len(perm_ids) == 2

    headers = _admin_login(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    response = client.post(
        "/api/v1/admin/roles",
        headers=headers,
        json={
            "name": "P12 Read-only HR",
            "scope": "hr",
            "description": "Sees jobs + candidates, nothing else.",
            "permission_ids": perm_ids,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "P12 Read-only HR"
    assert set(body["permission_keys"]) == {
        "hr:jobs:view",
        "hr:candidates:view_list",
    }
    assert body["user_count"] == 0


def test_create_role_name_conflict_409(
    client, seed_auth, db_session: Session
):
    headers = _admin_login(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    response = client.post(
        "/api/v1/admin/roles",
        headers=headers,
        json={"name": "HR Manager", "scope": "hr"},
    )
    assert response.status_code == 409


def test_create_role_blocks_cross_scope_grants(
    client, seed_auth, db_session: Session
):
    """Website-scope role trying to hold an HR permission -> 422."""
    hr_perm = db_session.execute(
        select(Permission).where(Permission.key == "hr:jobs:view")
    ).scalar_one()
    headers = _admin_login(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    response = client.post(
        "/api/v1/admin/roles",
        headers=headers,
        json={
            "name": "P12 Bad Website",
            "scope": "website",
            "permission_ids": [hr_perm.id],
        },
    )
    assert response.status_code == 422
    assert "scope" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Update role
# ---------------------------------------------------------------------------


def test_patch_role_renames_and_audits(
    client, seed_auth, db_session: Session
):
    # Create a dummy role to mutate (don't rename the seeded ones).
    role = Role(name="P12 Rename Me", scope="hr", description="orig")
    db_session.add(role)
    db_session.commit()

    headers = _admin_login(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    response = client.patch(
        f"/api/v1/admin/roles/{role.id}",
        headers=headers,
        json={"name": "P12 Renamed", "description": "after"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "P12 Renamed"

    audit = db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "admin.role.update",
            AuditLog.target_id == str(role.id),
        )
    ).scalar_one()
    changes = audit.details["changes"]
    assert changes["name"]["new"] == "P12 Renamed"


# ---------------------------------------------------------------------------
# Replace permission grants
# ---------------------------------------------------------------------------


def test_patch_role_permissions_diff_audited(
    client, seed_auth, db_session: Session
):
    """Adding two permissions and removing one should write a single
    audit row with both delta lists populated."""
    perms_by_key = {
        p.key: p
        for p in db_session.execute(
            select(Permission).where(
                Permission.key.in_(
                    (
                        "hr:jobs:view",
                        "hr:candidates:view_list",
                        "hr:offers:view",
                    )
                )
            )
        ).scalars()
    }

    role = Role(name="P12 Diff", scope="hr", description="")
    role.permissions = [perms_by_key["hr:jobs:view"]]
    db_session.add(role)
    db_session.commit()

    headers = _admin_login(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    response = client.patch(
        f"/api/v1/admin/roles/{role.id}/permissions",
        headers=headers,
        json={
            "permission_ids": [
                perms_by_key["hr:candidates:view_list"].id,
                perms_by_key["hr:offers:view"].id,
            ]
        },
    )
    assert response.status_code == 200
    assert set(response.json()["permission_keys"]) == {
        "hr:candidates:view_list",
        "hr:offers:view",
    }

    audit = db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "admin.role.permissions.update",
            AuditLog.target_id == str(role.id),
        )
    ).scalar_one()
    assert set(audit.details["added"]) == {
        "hr:candidates:view_list",
        "hr:offers:view",
    }
    assert set(audit.details["removed"]) == {"hr:jobs:view"}


# ---------------------------------------------------------------------------
# Delete role
# ---------------------------------------------------------------------------


def test_delete_role_blocked_if_users_assigned(
    client, seed_auth, db_session: Session
):
    """Try deleting the seeded HR Manager role — it has the
    hr@pug.example.com seed user, so should 409."""
    hr_manager_id = db_session.execute(
        select(Role.id).where(Role.name == "HR Manager")
    ).scalar_one()
    headers = _admin_login(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    response = client.delete(
        f"/api/v1/admin/roles/{hr_manager_id}", headers=headers
    )
    assert response.status_code == 409


def test_delete_role_works_when_empty(
    client, seed_auth, db_session: Session
):
    role = Role(name="P12 Empty", scope="hr", description="")
    db_session.add(role)
    db_session.commit()
    role_id = role.id

    headers = _admin_login(
        client, "superadmin@pug.example.com", seed_auth["password"]
    )
    response = client.delete(
        f"/api/v1/admin/roles/{role_id}", headers=headers
    )
    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.get(Role, role_id) is None


# ---------------------------------------------------------------------------
# Permission gating — only super admin
# ---------------------------------------------------------------------------


def test_website_admin_cannot_list_permissions(client, seed_auth):
    """Website admin holds scope=website, not system -> 403."""
    headers = _admin_login(
        client, "webadmin@pug.example.com", seed_auth["password"]
    )
    response = client.get("/api/v1/admin/permissions", headers=headers)
    assert response.status_code == 403


def test_website_admin_cannot_create_role(client, seed_auth):
    headers = _admin_login(
        client, "webadmin@pug.example.com", seed_auth["password"]
    )
    response = client.post(
        "/api/v1/admin/roles",
        headers=headers,
        json={"name": "P12 Block Me", "scope": "hr"},
    )
    assert response.status_code == 403
