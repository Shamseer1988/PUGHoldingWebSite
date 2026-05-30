"""hr — Phase 2 assessment workflow tables + permission keys

Revision ID: 20260530_0025
Revises: 20260530_0024
Create Date: 2026-05-30

Bootstraps the candidate assessment feature (HR Phase 2):

* Six new tables under the ``hr_assessment*`` / ``hr_assessments``
  prefix — see ``app.models.hr_assessment`` for the design notes.
* Two new permission keys:
    - ``hr:assessments:manage`` — create / edit templates, send /
      cancel invites, view submissions.
    - ``hr:assessments:view``   — read templates + submissions
      (no edit / send rights).
* Grants ``manage`` to Super Admin, HR Admin, HR Manager and
  HR Executive (Executive needs ``manage`` so a recruiter can send
  assessments to their own candidates); grants read-only ``view``
  to Department Manager and Viewer / Auditor. Roles missing from
  the install are skipped silently so a stripped-down environment
  doesn't break the migration.

Every INSERT is idempotent so re-running in dev / on a partially-
migrated DB doesn't explode.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260530_0025"
down_revision: str = "20260530_0024"
branch_labels = None
depends_on = None


NEW_PERMS = (
    (
        "hr:assessments:manage",
        "hr",
        "Create, edit and send candidate assessments + view submissions",
    ),
    (
        "hr:assessments:view",
        "hr",
        "Read candidate assessment templates and submissions",
    ),
)


ROLE_GRANTS = {
    "Super Admin":       ("hr:assessments:manage", "hr:assessments:view"),
    "HR Admin":          ("hr:assessments:manage", "hr:assessments:view"),
    "HR Manager":        ("hr:assessments:manage", "hr:assessments:view"),
    "HR Executive":      ("hr:assessments:manage", "hr:assessments:view"),
    "Department Manager": ("hr:assessments:view",),
    "Viewer / Auditor":  ("hr:assessments:view",),
}


def _create_assessments_table() -> None:
    op.create_table(
        "hr_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_opening_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("time_limit_minutes", sa.Integer(), nullable=True),
        sa.Column("passing_score", sa.Integer(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["job_opening_id"], ["hr_job_openings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_hr_assessments_job_opening_id", "hr_assessments", ["job_opening_id"]
    )
    op.create_index(
        "ix_hr_assessments_created_by_id", "hr_assessments", ["created_by_id"]
    )


def _create_questions_table() -> None:
    op.create_table(
        "hr_assessment_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "order_index", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("points", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["hr_assessments.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_hr_assessment_questions_assessment_id",
        "hr_assessment_questions",
        ["assessment_id"],
    )


def _create_choices_table() -> None:
    op.create_table(
        "hr_assessment_choices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "order_index", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "is_correct", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["hr_assessment_questions.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_hr_assessment_choices_question_id",
        "hr_assessment_choices",
        ["question_id"],
    )


def _create_invites_table() -> None:
    op.create_table(
        "hr_assessment_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "verified_identity_field", sa.String(16), nullable=True
        ),
        sa.Column("sent_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["hr_assessments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["hr_candidates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["hr_candidate_job_applications.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sent_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "candidate_id",
            "assessment_id",
            name="uq_hr_assessment_invites_candidate_assessment",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'opened', 'submitted', 'expired', 'cancelled')",
            name="ck_hr_assessment_invites_status",
        ),
    )
    op.create_index(
        "ix_hr_assessment_invites_token",
        "hr_assessment_invites",
        ["token"],
        unique=True,
    )
    op.create_index(
        "ix_hr_assessment_invites_assessment_id",
        "hr_assessment_invites",
        ["assessment_id"],
    )
    op.create_index(
        "ix_hr_assessment_invites_candidate_id",
        "hr_assessment_invites",
        ["candidate_id"],
    )
    op.create_index(
        "ix_hr_assessment_invites_application_id",
        "hr_assessment_invites",
        ["application_id"],
    )
    op.create_index(
        "ix_hr_assessment_invites_status",
        "hr_assessment_invites",
        ["status"],
    )


def _create_submissions_table() -> None:
    op.create_table(
        "hr_assessment_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invite_id", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["invite_id"],
            ["hr_assessment_invites.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "invite_id", name="uq_hr_assessment_submissions_invite_id"
        ),
    )


def _create_answers_table() -> None:
    op.create_table(
        "hr_assessment_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column(
            "selected_choice_ids",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["hr_assessment_submissions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["hr_assessment_questions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "submission_id",
            "question_id",
            name="uq_hr_assessment_answers_submission_question",
        ),
    )
    op.create_index(
        "ix_hr_assessment_answers_submission_id",
        "hr_assessment_answers",
        ["submission_id"],
    )
    op.create_index(
        "ix_hr_assessment_answers_question_id",
        "hr_assessment_answers",
        ["question_id"],
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # Create in dependency order: parent → child. Each guarded by an
    # existence check so a partially-applied prior run can be re-run
    # without errors.
    if "hr_assessments" not in existing_tables:
        _create_assessments_table()
    if "hr_assessment_questions" not in existing_tables:
        _create_questions_table()
    if "hr_assessment_choices" not in existing_tables:
        _create_choices_table()
    if "hr_assessment_invites" not in existing_tables:
        _create_invites_table()
    if "hr_assessment_submissions" not in existing_tables:
        _create_submissions_table()
    if "hr_assessment_answers" not in existing_tables:
        _create_answers_table()

    # --- Seed permissions (idempotent) ---------------------------------------
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

    # --- Grant permissions to roles (idempotent) -----------------------------
    for role_name, perm_keys in ROLE_GRANTS.items():
        role = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"),
            {"name": role_name},
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


def downgrade() -> None:
    bind = op.get_bind()

    # Drop permission grants + permission rows first so the FK from
    # role_permissions doesn't fight us.
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

    # Drop in reverse dependency order: children → parent.
    op.drop_table("hr_assessment_answers")
    op.drop_table("hr_assessment_submissions")
    op.drop_table("hr_assessment_invites")
    op.drop_table("hr_assessment_choices")
    op.drop_table("hr_assessment_questions")
    op.drop_table("hr_assessments")
