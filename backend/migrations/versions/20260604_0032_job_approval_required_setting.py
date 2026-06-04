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
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260604_0032"
down_revision = "20260603_0031"
branch_labels = None
depends_on = None


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


def downgrade() -> None:
    op.drop_column("email_settings", "job_approval_required")
