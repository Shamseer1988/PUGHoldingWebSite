"""F2 — interview scorecard templates

Revision ID: 20260527_0012
Revises: 20260527_0011
Create Date: 2026-05-27

Adds:
  * hr_scorecard_templates table
  * hr_interview_feedback.scorecard_template_id  (FK SET NULL)
  * hr_interview_feedback.scorecard_scores       (JSON)
  * hr_interview_feedback.scorecard_total        (Integer, cached
                                                   weighted total)

All additive — existing feedback rows are untouched and behave as
free-text feedback until a scorecard is filled in.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260527_0012"
down_revision: str = "20260527_0011"
branch_labels = None
depends_on = None


NEW_FEEDBACK_COLS = (
    ("scorecard_template_id", sa.Integer(), True, None),
    ("scorecard_scores", sa.JSON(), True, None),
    ("scorecard_total", sa.Integer(), True, None),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- 1. hr_scorecard_templates ---
    if "hr_scorecard_templates" not in inspector.get_table_names():
        op.create_table(
            "hr_scorecard_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "scope",
                sa.String(16),
                nullable=False,
                server_default="global",
            ),
            sa.Column("job_opening_id", sa.Integer(), nullable=True),
            sa.Column("dimensions", sa.JSON(), nullable=False),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
            sa.Column(
                "is_default",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
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
                "scope IN ('global', 'job')",
                name="ck_hr_scorecard_templates_scope",
            ),
        )
        op.create_index(
            "ix_hr_scorecard_templates_name",
            "hr_scorecard_templates",
            ["name"],
        )
        op.create_index(
            "ix_hr_scorecard_templates_scope",
            "hr_scorecard_templates",
            ["scope"],
        )
        op.create_index(
            "ix_hr_scorecard_templates_job_id",
            "hr_scorecard_templates",
            ["job_opening_id"],
        )
        op.create_index(
            "ix_hr_scorecard_templates_default",
            "hr_scorecard_templates",
            ["is_default"],
        )
        if bind.dialect.name != "sqlite":
            try:
                op.create_foreign_key(
                    "fk_hr_scorecard_templates_job",
                    "hr_scorecard_templates",
                    "hr_job_openings",
                    ["job_opening_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
                op.create_foreign_key(
                    "fk_hr_scorecard_templates_creator",
                    "hr_scorecard_templates",
                    "users",
                    ["created_by_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            except Exception:
                pass

    # --- 2. extend hr_interview_feedback ---
    existing = {
        col["name"] for col in inspector.get_columns("hr_interview_feedback")
    }
    with op.batch_alter_table("hr_interview_feedback") as batch:
        for name, type_, nullable, default in NEW_FEEDBACK_COLS:
            if name in existing:
                continue
            kwargs = {"nullable": nullable}
            if default is not None:
                kwargs["server_default"] = default
            batch.add_column(sa.Column(name, type_, **kwargs))
    if bind.dialect.name != "sqlite":
        try:
            op.create_foreign_key(
                "fk_hr_feedback_scorecard_template",
                "hr_interview_feedback",
                "hr_scorecard_templates",
                ["scorecard_template_id"],
                ["id"],
                ondelete="SET NULL",
            )
        except Exception:
            pass
    try:
        op.create_index(
            "ix_hr_interview_feedback_scorecard_template",
            "hr_interview_feedback",
            ["scorecard_template_id"],
        )
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()
    try:
        op.drop_index(
            "ix_hr_interview_feedback_scorecard_template",
            table_name="hr_interview_feedback",
        )
    except Exception:
        pass
    if bind.dialect.name != "sqlite":
        try:
            op.drop_constraint(
                "fk_hr_feedback_scorecard_template",
                "hr_interview_feedback",
                type_="foreignkey",
            )
        except Exception:
            pass
    with op.batch_alter_table("hr_interview_feedback") as batch:
        for name, _, _, _ in NEW_FEEDBACK_COLS:
            try:
                batch.drop_column(name)
            except Exception:
                pass
    try:
        op.drop_table("hr_scorecard_templates")
    except Exception:
        pass
