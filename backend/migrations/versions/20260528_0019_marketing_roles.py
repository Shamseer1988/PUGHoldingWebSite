"""marketing — granular permission keys + Marketing Manager/Viewer roles

Revision ID: 20260528_0019
Revises: 20260528_0018
Create Date: 2026-05-28

Round-2 on the marketing permission catalogue. Adds three new keys
so a viewer (analytics-only) and a manager (full CRUD) can coexist:

    marketing:dashboard:view
    marketing:campaigns:read
    marketing:catalogues:read

And seeds two roles tuned for a marketing-only operator that should
not see HR/users/site-settings:

    Marketing Manager   — full marketing CRUD + dashboard
    Marketing Viewer    — read + dashboard only

Idempotent — every INSERT checks for an existing row first so the
migration can be re-run during dev without exploding. Existing
``Super Admin`` and the legacy ``marketing:*:manage`` grants are
preserved untouched.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260528_0019"
down_revision: str = "20260528_0018"
branch_labels = None
depends_on = None


# (key, scope, description) — scope=system so they're visible to all
# scoped admin tokens regardless of whether the operator is logged
# into the website or HR portal.
NEW_PERMS = (
    (
        "marketing:dashboard:view",
        "system",
        "View the Marketing analytics dashboard",
    ),
    (
        "marketing:campaigns:read",
        "system",
        "Browse offer campaigns (read-only)",
    ),
    (
        "marketing:catalogues:read",
        "system",
        "Browse catalogues and pages (read-only)",
    ),
)


# Role → list of permission keys to grant on insert. ``Marketing
# Manager`` gets every key (including the existing two manage keys);
# ``Marketing Viewer`` gets dashboard + read keys only.
NEW_ROLES = (
    (
        "Marketing Manager",
        "system",
        (
            "Marketing portal admin — full access to campaigns, catalogues, "
            "PDF compressor and the analytics dashboard. Cannot touch HR, "
            "users or site settings."
        ),
        (
            "marketing:dashboard:view",
            "marketing:campaigns:read",
            "marketing:campaigns:manage",
            "marketing:catalogues:read",
            "marketing:catalogues:manage",
        ),
    ),
    (
        "Marketing Viewer",
        "system",
        (
            "Marketing analyst — read-only access to campaigns and "
            "catalogues plus the analytics dashboard. Cannot upload, "
            "edit or delete."
        ),
        (
            "marketing:dashboard:view",
            "marketing:campaigns:read",
            "marketing:catalogues:read",
        ),
    ),
)


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. Insert the three new permission rows (idempotent) ---------------
    for key, scope, description in NEW_PERMS:
        existing = bind.execute(
            sa.text("SELECT id FROM permissions WHERE key = :key"),
            {"key": key},
        ).first()
        if existing is None:
            bind.execute(
                sa.text(
                    "INSERT INTO permissions (key, scope, description) "
                    "VALUES (:key, :scope, :description)"
                ),
                {"key": key, "scope": scope, "description": description},
            )

    # --- 2. Insert the two new roles (idempotent) ---------------------------
    for name, scope, description, _perm_keys in NEW_ROLES:
        existing = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"),
            {"name": name},
        ).first()
        if existing is None:
            bind.execute(
                sa.text(
                    "INSERT INTO roles (name, scope, description) "
                    "VALUES (:name, :scope, :description)"
                ),
                {"name": name, "scope": scope, "description": description},
            )

    # --- 3. Wire permissions to the two roles (idempotent) ------------------
    for name, _scope, _desc, perm_keys in NEW_ROLES:
        role = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"),
            {"name": name},
        ).first()
        if role is None:
            continue
        role_id = role[0]
        for key in perm_keys:
            perm = bind.execute(
                sa.text("SELECT id FROM permissions WHERE key = :key"),
                {"key": key},
            ).first()
            if perm is None:
                continue
            perm_id = perm[0]
            already = bind.execute(
                sa.text(
                    "SELECT 1 FROM role_permissions "
                    "WHERE role_id = :rid AND permission_id = :pid"
                ),
                {"rid": role_id, "pid": perm_id},
            ).first()
            if already is None:
                bind.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:rid, :pid)"
                    ),
                    {"rid": role_id, "pid": perm_id},
                )

    # --- 4. Grant the three new keys to Super Admin (if present) ------------
    super_admin = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Super Admin'")
    ).first()
    if super_admin is not None:
        sa_id = super_admin[0]
        for key, _scope, _desc in NEW_PERMS:
            perm = bind.execute(
                sa.text("SELECT id FROM permissions WHERE key = :key"),
                {"key": key},
            ).first()
            if perm is None:
                continue
            perm_id = perm[0]
            already = bind.execute(
                sa.text(
                    "SELECT 1 FROM role_permissions "
                    "WHERE role_id = :rid AND permission_id = :pid"
                ),
                {"rid": sa_id, "pid": perm_id},
            ).first()
            if already is None:
                bind.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:rid, :pid)"
                    ),
                    {"rid": sa_id, "pid": perm_id},
                )


def downgrade() -> None:
    bind = op.get_bind()

    # Tear down role_permissions for the new roles first, then the
    # roles themselves, then the new permission rows. We don't
    # remove the new permission grants on Super Admin separately
    # because deleting the permission row cascades.
    for name, _scope, _desc, _keys in NEW_ROLES:
        role = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"),
            {"name": name},
        ).first()
        if role is None:
            continue
        role_id = role[0]
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE role_id = :rid"),
            {"rid": role_id},
        )
        bind.execute(
            sa.text("DELETE FROM user_roles WHERE role_id = :rid"),
            {"rid": role_id},
        )
        bind.execute(
            sa.text("DELETE FROM roles WHERE id = :rid"), {"rid": role_id}
        )

    for key, _scope, _desc in NEW_PERMS:
        perm = bind.execute(
            sa.text("SELECT id FROM permissions WHERE key = :key"),
            {"key": key},
        ).first()
        if perm is None:
            continue
        perm_id = perm[0]
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id = :pid"
            ),
            {"pid": perm_id},
        )
        bind.execute(
            sa.text("DELETE FROM permissions WHERE id = :pid"),
            {"pid": perm_id},
        )
