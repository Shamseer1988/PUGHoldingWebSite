"""F4 — scheduled report digests

Revision ID: 20260527_0013
Revises: 20260527_0012
Create Date: 2026-05-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260527_0013"
down_revision: str = "20260527_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "hr_scheduled_reports" in inspector.get_table_names():
        return

    op.create_table(
        "hr_scheduled_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("report_type", sa.String(64), nullable=False),
        sa.Column(
            "frequency",
            sa.String(16),
            nullable=False,
            server_default="daily",
        ),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(16), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_row_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "frequency IN ('daily', 'weekly', 'monthly')",
            name="ck_hr_scheduled_reports_frequency",
        ),
    )
    op.create_index(
        "ix_hr_scheduled_reports_owner_id",
        "hr_scheduled_reports",
        ["owner_id"],
    )
    op.create_index(
        "ix_hr_scheduled_reports_name",
        "hr_scheduled_reports",
        ["name"],
    )
    op.create_index(
        "ix_hr_scheduled_reports_frequency",
        "hr_scheduled_reports",
        ["frequency"],
    )
    op.create_index(
        "ix_hr_scheduled_reports_report_type",
        "hr_scheduled_reports",
        ["report_type"],
    )
    if bind.dialect.name != "sqlite":
        try:
            op.create_foreign_key(
                "fk_hr_scheduled_reports_owner",
                "hr_scheduled_reports",
                "users",
                ["owner_id"],
                ["id"],
                ondelete="SET NULL",
            )
        except Exception:
            pass


def downgrade() -> None:
    op.drop_table("hr_scheduled_reports")
