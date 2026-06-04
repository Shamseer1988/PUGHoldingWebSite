"""hr — global "require job approval" setting (Super Admin toggle)

Revision ID: 20260604_0032
Revises: 20260603_0031
Create Date: 2026-06-04

Adds ``email_settings.job_approval_required`` (default TRUE) — the global
on/off for the HR job-approval workflow. A Super Admin flips it off to let
jobs publish straight on create; per-role bypass is handled separately by the
new ``hr:jobs:post_direct`` permission.

Additive + backfilled via ``server_default``, so existing installs keep the
current (approval-required) behaviour with no data migration.

Also seeds the new ``hr:jobs:post_direct`` permission row (granted to no role)
so the per-role bypass is grantable from the role matrix right after
``alembic upgrade`` — no manual re-seed needed.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260604_0032"
down_revision = "20260603_0031"
branch_labels = None
depends_on = None


PERM_KEY = "hr:jobs:post_direct"
PERM_SCOPE = "hr"
PERM_DESC = "Post jobs directly without approval (when approval is required globally)"


def upgrade() -> None:
    op.add_column(
        "email_settings",
        sa.Column(
            "job_approval_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    # Register the per-role bypass permission so it shows up in the role
    # matrix and can be granted. Granted to NO role by default (skipping
    # approval is an explicit per-role opt-in a Super Admin makes; even Super
    # Admin is left without it so its own jobs still follow the flow).
    # Idempotent — mirrors 20260527_0017_marketing_perms_seed.
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM permissions WHERE key = :key"),
        {"key": PERM_KEY},
    ).first()
    if existing is None:
        bind.execute(
            sa.text(
                "INSERT INTO permissions (key, scope, description) "
                "VALUES (:key, :scope, :description)"
            ),
            {"key": PERM_KEY, "scope": PERM_SCOPE, "description": PERM_DESC},
        )


def downgrade() -> None:
    bind = op.get_bind()
    perm = bind.execute(
        sa.text("SELECT id FROM permissions WHERE key = :key"),
        {"key": PERM_KEY},
    ).first()
    if perm is not None:
        perm_id = perm[0]
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
            {"pid": perm_id},
        )
        bind.execute(
            sa.text("DELETE FROM permissions WHERE id = :pid"), {"pid": perm_id}
        )
    op.drop_column("email_settings", "job_approval_required")
