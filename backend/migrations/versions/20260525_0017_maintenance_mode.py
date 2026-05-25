"""Add maintenance-mode columns to site_settings.

When ``maintenance_mode_enabled`` is True the public Next.js layout
renders a maintenance page in place of every public route. Admin and
HR portals are unaffected so the team can still log in and turn it
back off. ``maintenance_message`` overrides the default copy on the
page; ``maintenance_eta`` is a short "Back by" hint.

Revision ID: 20260525_0017
Revises: 20260525_0016
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260525_0017"
down_revision: Union[str, None] = "20260525_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.add_column(
            sa.Column(
                "maintenance_mode_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch.add_column(
            sa.Column("maintenance_message", sa.Text(), nullable=True)
        )
        batch.add_column(
            sa.Column("maintenance_eta", sa.String(length=120), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.drop_column("maintenance_eta")
        batch.drop_column("maintenance_message")
        batch.drop_column("maintenance_mode_enabled")
