"""assessment field types + HR review trail

Revision ID: 20260531_0027
Revises: 20260531_0026
Create Date: 2026-05-31

Extends the assessment engine from MCQ-multi-only to typed questions and
adds an HR review-and-advance trail. Additive only (per CLAUDE.md — no
column drops):

* ``hr_assessment_questions``: ``type`` (default ``multi_choice`` so every
  existing row backfills), ``help_text``, ``is_required`` (default true),
  ``config`` JSON (default ``{}``).
* ``hr_assessment_answers``: ``value`` JSON (null for legacy MCQ rows,
  which keep using ``selected_choice_ids``).
* ``hr_assessment_submissions``: ``review_status`` (default ``pending``),
  ``reviewed_by_user_id``, ``reviewed_at``, ``reviewer_overall_comment``,
  ``reviewer_score_override``.
* new ``hr_assessment_review_events`` audit table.

Existing submissions stay valid: ``selected_choice_ids`` remains
queryable, ``value`` is null for legacy rows, and ``type`` defaults to
``multi_choice``. No data loss. The candidate file-upload (attachment)
type is reserved in the app enum but its storage table ships later.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260531_0027"
down_revision: str = "20260531_0026"
branch_labels = None
depends_on = None


QUESTION_TYPES = (
    "short_text",
    "long_text",
    "date",
    "checkbox",
    "single_choice",
    "multi_choice",
    "attachment",
)
REVIEW_ACTIONS = (
    "draft_saved",
    "approved_advanced",
    "rejected",
    "changes_requested",
    "score_overridden",
)


def _in_clause(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def upgrade() -> None:
    # --- hr_assessment_questions: typed questions -----------------------
    op.add_column(
        "hr_assessment_questions",
        sa.Column(
            "type",
            sa.String(length=20),
            nullable=False,
            server_default="multi_choice",
        ),
    )
    op.add_column(
        "hr_assessment_questions",
        sa.Column("help_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "hr_assessment_questions",
        sa.Column(
            "is_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "hr_assessment_questions",
        sa.Column(
            "config",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.create_check_constraint(
        "ck_hr_assessment_questions_type",
        "hr_assessment_questions",
        _in_clause("type", QUESTION_TYPES),
    )

    # --- hr_assessment_answers: typed payload + per-question review -----
    op.add_column(
        "hr_assessment_answers",
        sa.Column("value", sa.JSON(), nullable=True),
    )
    op.add_column(
        "hr_assessment_answers",
        sa.Column("reviewer_passed", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "hr_assessment_answers",
        sa.Column("reviewer_note", sa.Text(), nullable=True),
    )

    # --- hr_assessment_submissions: HR review columns -------------------
    op.add_column(
        "hr_assessment_submissions",
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "hr_assessment_submissions",
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "hr_assessment_submissions",
        sa.Column(
            "reviewed_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "hr_assessment_submissions",
        sa.Column("reviewer_overall_comment", sa.Text(), nullable=True),
    )
    op.add_column(
        "hr_assessment_submissions",
        sa.Column("reviewer_score_override", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_hr_assessment_submissions_review_status",
        "hr_assessment_submissions",
        ["review_status"],
    )
    op.create_foreign_key(
        "fk_hr_assessment_submissions_reviewed_by",
        "hr_assessment_submissions",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- new audit table ------------------------------------------------
    op.create_table(
        "hr_assessment_review_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "submission_id",
            sa.Integer(),
            sa.ForeignKey(
                "hr_assessment_submissions.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("from_status", sa.String(length=40), nullable=True),
        sa.Column("to_status", sa.String(length=40), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            _in_clause("action", REVIEW_ACTIONS),
            name="ck_hr_assessment_review_events_action",
        ),
    )
    op.create_index(
        "ix_hr_assessment_review_events_submission_id",
        "hr_assessment_review_events",
        ["submission_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_hr_assessment_review_events_submission_id")
    op.drop_table("hr_assessment_review_events")

    op.drop_constraint(
        "fk_hr_assessment_submissions_reviewed_by",
        "hr_assessment_submissions",
        type_="foreignkey",
    )
    op.drop_index("ix_hr_assessment_submissions_review_status")
    op.drop_column("hr_assessment_submissions", "reviewer_score_override")
    op.drop_column("hr_assessment_submissions", "reviewer_overall_comment")
    op.drop_column("hr_assessment_submissions", "reviewed_at")
    op.drop_column("hr_assessment_submissions", "reviewed_by_user_id")
    op.drop_column("hr_assessment_submissions", "review_status")

    op.drop_column("hr_assessment_answers", "reviewer_note")
    op.drop_column("hr_assessment_answers", "reviewer_passed")
    op.drop_column("hr_assessment_answers", "value")

    op.drop_constraint(
        "ck_hr_assessment_questions_type",
        "hr_assessment_questions",
        type_="check",
    )
    op.drop_column("hr_assessment_questions", "config")
    op.drop_column("hr_assessment_questions", "is_required")
    op.drop_column("hr_assessment_questions", "help_text")
    op.drop_column("hr_assessment_questions", "type")
