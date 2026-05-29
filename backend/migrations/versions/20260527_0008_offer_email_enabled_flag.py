"""hr — Phase 11: master mute switch for offer-related emails

Revision ID: 20260527_0008
Revises: 20260527_0007
Create Date: 2026-05-27

Adds a single boolean ``offer_email_enabled`` on ``email_settings``
matching the existing per-stream flags for candidate / interview /
job-approval notifications. When false, every offer-related email
(approval-requested, approved, issued, accepted, declined, joined) is
short-circuited at the dispatch layer.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260527_0008"
down_revision: str = "20260527_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("email_settings")}
    if "offer_email_enabled" in existing:
        return
    with op.batch_alter_table("email_settings") as batch:
        batch.add_column(
            sa.Column(
                "offer_email_enabled",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("email_settings") as batch:
        try:
            batch.drop_column("offer_email_enabled")
        except Exception:
            pass
