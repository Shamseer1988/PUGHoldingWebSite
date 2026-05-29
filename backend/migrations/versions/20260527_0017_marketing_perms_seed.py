"""marketing — seed marketing:* permissions + grant to Super Admin

Revision ID: 20260527_0017
Revises: 20260527_0016
Create Date: 2026-05-27

The marketing-module endpoints (commit 1) require two new fine-grained
permission keys:

    marketing:campaigns:manage
    marketing:catalogues:manage

This migration:
  1. Inserts them into the ``permissions`` table (idempotent — skips
     if a row with the same key already exists).
  2. Grants both to the ``Super Admin`` role so the existing seeded
     account can manage the marketing surface immediately.

Other roles do NOT get the grant by default; site admins can attach
the keys via Users & roles whenever a marketing-author role is added.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260527_0017"
down_revision: str = "20260527_0016"
branch_labels = None
depends_on = None


PERMS = (
    ("marketing:campaigns:manage", "system", "Create and manage offer campaigns"),
    ("marketing:catalogues:manage", "system", "Upload and manage catalogues"),
)


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. Insert permission rows (idempotent) -----------------------------
    for key, scope, description in PERMS:
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

    # --- 2. Grant both keys to Super Admin (if the role exists) -------------
    super_admin = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Super Admin'")
    ).first()
    if super_admin is None:
        # Fresh DB before seed_users.py runs — nothing to grant.
        return
    role_id = super_admin[0]
    for key, _scope, _desc in PERMS:
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


def downgrade() -> None:
    bind = op.get_bind()
    for key, _scope, _desc in PERMS:
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
