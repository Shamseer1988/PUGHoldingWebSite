"""F1 — saved candidate searches (talent pool)

Revision ID: 20260527_0011
Revises: 20260527_0010
Create Date: 2026-05-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260527_0011"
down_revision: str = "20260527_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "hr_saved_candidate_searches" in inspector.get_table_names():
        return

    op.create_table(
        "hr_saved_candidate_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column(
            "scope",
            sa.String(16),
            nullable=False,
            server_default="private",
        ),
        sa.Column(
            "pinned",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result_count", sa.Integer(), nullable=True),
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
        sa.UniqueConstraint(
            "owner_id", "name", name="uq_hr_saved_searches_owner_name"
        ),
        sa.CheckConstraint(
            "scope IN ('private', 'team')",
            name="ck_hr_saved_searches_scope",
        ),
    )
    op.create_index(
        "ix_hr_saved_candidate_searches_owner_id",
        "hr_saved_candidate_searches",
        ["owner_id"],
    )
    op.create_index(
        "ix_hr_saved_candidate_searches_name",
        "hr_saved_candidate_searches",
        ["name"],
    )
    op.create_index(
        "ix_hr_saved_candidate_searches_scope",
        "hr_saved_candidate_searches",
        ["scope"],
    )
    if bind.dialect.name != "sqlite":
        try:
            op.create_foreign_key(
                "fk_hr_saved_searches_owner",
                "hr_saved_candidate_searches",
                "users",
                ["owner_id"],
                ["id"],
                ondelete="SET NULL",
            )
        except Exception:
            pass


def downgrade() -> None:
    op.drop_table("hr_saved_candidate_searches")
