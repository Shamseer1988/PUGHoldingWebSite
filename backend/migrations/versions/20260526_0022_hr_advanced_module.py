"""HR Advanced Module - approval workflow, email logs, auto-review, interview extras.

Adds:

* New columns on ``hr_job_openings``: approval_status, publish_status,
  approved_by_id, approved_at, submitted_for_approval_by_id,
  submitted_for_approval_at, rejected_by_id, rejected_at, approval_remarks,
  active_revision_id.
* New columns on ``hr_interviews``: calendar_event_id, meeting_link,
  calendar_provider, email_sent_at, email_delivery_status,
  additional_attendee_emails, cc_emails, bcc_emails,
  candidate_email_override, email_subject, email_note.
* New table ``hr_job_approval_history`` (one row per approval action).
* New table ``hr_job_revisions`` (pending edits on approved jobs).
* New table ``hr_email_logs`` (branded email send log).
* New table ``hr_auto_review_rules`` (per-job auto-shortlist config).
* New table ``hr_candidate_auto_reviews`` (auto-review outcomes).
* Existing rows are back-filled: jobs with status='open' become
  approval_status='approved', publish_status='published' so existing
  public listings stay live without manual intervention.

Revision ID: 20260526_0022
Revises: 20260526_0021
Create Date: 2026-05-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260526_0022"
down_revision: Union[str, None] = "20260526_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # hr_job_openings — new approval columns
    # ------------------------------------------------------------------
    with op.batch_alter_table("hr_job_openings") as batch:
        batch.add_column(
            sa.Column(
                "approval_status",
                sa.String(length=32),
                nullable=False,
                server_default="draft",
            )
        )
        batch.add_column(
            sa.Column(
                "publish_status",
                sa.String(length=32),
                nullable=False,
                server_default="draft",
            )
        )
        batch.add_column(sa.Column("approved_by_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("submitted_for_approval_by_id", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "submitted_for_approval_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("rejected_by_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("approval_remarks", sa.Text(), nullable=True))
        batch.add_column(sa.Column("active_revision_id", sa.Integer(), nullable=True))

    op.create_index(
        "ix_hr_jobs_approval_status",
        "hr_job_openings",
        ["approval_status"],
    )
    op.create_index(
        "ix_hr_jobs_publish_status",
        "hr_job_openings",
        ["publish_status"],
    )

    # Back-fill existing data so existing public jobs stay live:
    # any job with status='open' is treated as already approved/published.
    op.execute(
        """
        UPDATE hr_job_openings
        SET approval_status = 'approved',
            publish_status = 'published'
        WHERE status = 'open'
        """
    )

    # ------------------------------------------------------------------
    # hr_interviews — new email + calendar columns
    # ------------------------------------------------------------------
    with op.batch_alter_table("hr_interviews") as batch:
        batch.add_column(sa.Column("calendar_event_id", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("meeting_link", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("calendar_provider", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("email_delivery_status", sa.String(length=32), nullable=True)
        )
        batch.add_column(sa.Column("additional_attendee_emails", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("cc_emails", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("bcc_emails", sa.JSON(), nullable=True))
        batch.add_column(
            sa.Column("candidate_email_override", sa.String(length=255), nullable=True)
        )
        batch.add_column(sa.Column("email_subject", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("email_note", sa.Text(), nullable=True))

    # ------------------------------------------------------------------
    # hr_job_approval_history
    # ------------------------------------------------------------------
    op.create_table(
        "hr_job_approval_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_opening_id",
            sa.Integer(),
            sa.ForeignKey("hr_job_openings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("old_approval_status", sa.String(length=32), nullable=True),
        sa.Column("new_approval_status", sa.String(length=32), nullable=True),
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("changed_fields", sa.JSON(), nullable=True),
        sa.Column("revision_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_hr_job_approval_history_job",
        "hr_job_approval_history",
        ["job_opening_id"],
    )
    op.create_index(
        "ix_hr_job_approval_history_action",
        "hr_job_approval_history",
        ["action"],
    )
    op.create_index(
        "ix_hr_job_approval_history_created_at",
        "hr_job_approval_history",
        ["created_at"],
    )

    # ------------------------------------------------------------------
    # hr_job_revisions
    # ------------------------------------------------------------------
    op.create_table(
        "hr_job_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_opening_id",
            sa.Integer(),
            sa.ForeignKey("hr_job_openings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reviewed_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
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
    )
    op.create_index("ix_hr_job_revisions_job", "hr_job_revisions", ["job_opening_id"])
    op.create_index("ix_hr_job_revisions_status", "hr_job_revisions", ["status"])

    # ------------------------------------------------------------------
    # hr_email_logs
    # ------------------------------------------------------------------
    op.create_table(
        "hr_email_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(length=32), nullable=True),
        sa.Column("template_key", sa.String(length=120), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("to_emails", sa.JSON(), nullable=True),
        sa.Column("cc_emails", sa.JSON(), nullable=True),
        sa.Column("bcc_emails", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("provider_response", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("related_type", sa.String(length=64), nullable=True),
        sa.Column("related_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_hr_email_logs_scope", "hr_email_logs", ["scope"])
    op.create_index("ix_hr_email_logs_template", "hr_email_logs", ["template_key"])
    op.create_index("ix_hr_email_logs_status", "hr_email_logs", ["status"])
    op.create_index("ix_hr_email_logs_related_type", "hr_email_logs", ["related_type"])
    op.create_index("ix_hr_email_logs_related_id", "hr_email_logs", ["related_id"])
    op.create_index("ix_hr_email_logs_created_at", "hr_email_logs", ["created_at"])

    # ------------------------------------------------------------------
    # hr_auto_review_rules (one per job)
    # ------------------------------------------------------------------
    op.create_table(
        "hr_auto_review_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_opening_id",
            sa.Integer(),
            sa.ForeignKey("hr_job_openings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "auto_reject_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("min_score", sa.Integer(), nullable=True),
        sa.Column("required_skills", sa.JSON(), nullable=True),
        sa.Column("preferred_skills", sa.JSON(), nullable=True),
        sa.Column("min_experience", sa.Float(), nullable=True),
        sa.Column("max_expected_salary", sa.Integer(), nullable=True),
        sa.Column("visa_keywords", sa.JSON(), nullable=True),
        sa.Column("location_keywords", sa.JSON(), nullable=True),
        sa.Column("nationality_keywords", sa.JSON(), nullable=True),
        sa.Column("notice_period_keywords", sa.JSON(), nullable=True),
        sa.Column("auto_shortlist_threshold", sa.Integer(), nullable=True),
        sa.Column("auto_reject_threshold", sa.Integer(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
    )

    # ------------------------------------------------------------------
    # hr_candidate_auto_reviews (one per application)
    # ------------------------------------------------------------------
    op.create_table(
        "hr_candidate_auto_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "rule_id",
            sa.Integer(),
            sa.ForeignKey("hr_auto_review_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("matched_skills", sa.JSON(), nullable=True),
        sa.Column("missing_skills", sa.JSON(), nullable=True),
        sa.Column("risk_flags", sa.JSON(), nullable=True),
        sa.Column("reason_summary", sa.Text(), nullable=True),
        sa.Column("recommendation_source", sa.String(length=64), nullable=True),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "reviewed_by_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
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
    )
    op.create_index(
        "ix_hr_candidate_auto_reviews_decision",
        "hr_candidate_auto_reviews",
        ["decision"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hr_candidate_auto_reviews_decision",
        table_name="hr_candidate_auto_reviews",
    )
    op.drop_table("hr_candidate_auto_reviews")
    op.drop_table("hr_auto_review_rules")

    op.drop_index("ix_hr_email_logs_created_at", table_name="hr_email_logs")
    op.drop_index("ix_hr_email_logs_related_id", table_name="hr_email_logs")
    op.drop_index("ix_hr_email_logs_related_type", table_name="hr_email_logs")
    op.drop_index("ix_hr_email_logs_status", table_name="hr_email_logs")
    op.drop_index("ix_hr_email_logs_template", table_name="hr_email_logs")
    op.drop_index("ix_hr_email_logs_scope", table_name="hr_email_logs")
    op.drop_table("hr_email_logs")

    op.drop_index("ix_hr_job_revisions_status", table_name="hr_job_revisions")
    op.drop_index("ix_hr_job_revisions_job", table_name="hr_job_revisions")
    op.drop_table("hr_job_revisions")

    op.drop_index(
        "ix_hr_job_approval_history_created_at",
        table_name="hr_job_approval_history",
    )
    op.drop_index(
        "ix_hr_job_approval_history_action",
        table_name="hr_job_approval_history",
    )
    op.drop_index(
        "ix_hr_job_approval_history_job",
        table_name="hr_job_approval_history",
    )
    op.drop_table("hr_job_approval_history")

    with op.batch_alter_table("hr_interviews") as batch:
        batch.drop_column("email_note")
        batch.drop_column("email_subject")
        batch.drop_column("candidate_email_override")
        batch.drop_column("bcc_emails")
        batch.drop_column("cc_emails")
        batch.drop_column("additional_attendee_emails")
        batch.drop_column("email_delivery_status")
        batch.drop_column("email_sent_at")
        batch.drop_column("calendar_provider")
        batch.drop_column("meeting_link")
        batch.drop_column("calendar_event_id")

    op.drop_index("ix_hr_jobs_publish_status", table_name="hr_job_openings")
    op.drop_index("ix_hr_jobs_approval_status", table_name="hr_job_openings")

    with op.batch_alter_table("hr_job_openings") as batch:
        batch.drop_column("active_revision_id")
        batch.drop_column("approval_remarks")
        batch.drop_column("rejected_at")
        batch.drop_column("rejected_by_id")
        batch.drop_column("submitted_for_approval_at")
        batch.drop_column("submitted_for_approval_by_id")
        batch.drop_column("approved_at")
        batch.drop_column("approved_by_id")
        batch.drop_column("publish_status")
        batch.drop_column("approval_status")
