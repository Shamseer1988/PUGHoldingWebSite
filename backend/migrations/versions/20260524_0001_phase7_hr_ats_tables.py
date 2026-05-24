"""Phase 7 - create HR ATS tables.

Revision ID: 20260524_0001
Revises: 20260523_0002
Create Date: 2026-05-24

Tables introduced:
- hr_job_openings
- hr_candidates
- hr_candidate_documents
- hr_candidate_extracted_data
- hr_candidate_notes
- hr_candidate_tags
- hr_candidate_job_applications
- hr_candidate_scores
- hr_candidate_score_breakdowns
- hr_candidate_ai_reviews
- hr_candidate_status_history
- hr_interviews
- hr_interview_feedback
- hr_offer_tracking
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0001"
down_revision: Union[str, None] = "20260523_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # hr_job_openings
    # ------------------------------------------------------------------
    op.create_table(
        "hr_job_openings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=False),
        sa.Column("division", sa.String(length=120), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column(
            "employment_type",
            sa.String(length=32),
            nullable=False,
            server_default="full_time",
        ),
        sa.Column("min_experience", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_experience", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_education", sa.String(length=255), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("visa_requirement", sa.String(length=120), nullable=True),
        sa.Column("nationality_preference", sa.String(length=255), nullable=True),
        sa.Column("language_requirement", sa.String(length=255), nullable=True),
        sa.Column("notice_period_preference", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("responsibilities", sa.Text(), nullable=True),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("required_skills", sa.Text(), nullable=True),
        sa.Column("preferred_skills", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column(
            "posted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_hr_jobs_slug"),
    )
    op.create_index("ix_hr_jobs_slug", "hr_job_openings", ["slug"])
    op.create_index("ix_hr_jobs_department", "hr_job_openings", ["department"])
    op.create_index("ix_hr_jobs_company", "hr_job_openings", ["company"])
    op.create_index("ix_hr_jobs_status", "hr_job_openings", ["status"])
    op.create_index("ix_hr_jobs_posted_at", "hr_job_openings", ["posted_at"])

    # ------------------------------------------------------------------
    # hr_candidates
    # ------------------------------------------------------------------
    op.create_table(
        "hr_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("mobile", sa.String(length=40), nullable=True),
        sa.Column("nationality", sa.String(length=120), nullable=True),
        sa.Column("current_location", sa.String(length=255), nullable=True),
        sa.Column("current_designation", sa.String(length=255), nullable=True),
        sa.Column("current_company", sa.String(length=255), nullable=True),
        sa.Column("total_experience_years", sa.Float(), nullable=True),
        sa.Column("gcc_experience_years", sa.Float(), nullable=True),
        sa.Column("qatar_experience_years", sa.Float(), nullable=True),
        sa.Column("expected_salary", sa.Integer(), nullable=True),
        sa.Column("notice_period", sa.String(length=120), nullable=True),
        sa.Column("visa_status", sa.String(length=120), nullable=True),
        sa.Column("availability", sa.String(length=120), nullable=True),
        sa.Column(
            "is_blacklisted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("blacklist_reason", sa.Text(), nullable=True),
        sa.Column(
            "blacklisted_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("blacklisted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_hr_candidates_full_name", "hr_candidates", ["full_name"])
    op.create_index("ix_hr_candidates_email", "hr_candidates", ["email"])
    op.create_index("ix_hr_candidates_mobile", "hr_candidates", ["mobile"])
    op.create_index("ix_hr_candidates_blacklisted", "hr_candidates", ["is_blacklisted"])
    op.create_index("ix_hr_candidates_archived", "hr_candidates", ["is_archived"])

    # ------------------------------------------------------------------
    # hr_candidate_documents
    # ------------------------------------------------------------------
    op.create_table(
        "hr_candidate_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "uploaded_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_hr_docs_candidate", "hr_candidate_documents", ["candidate_id"])
    op.create_index("ix_hr_docs_file_hash", "hr_candidate_documents", ["file_hash"])

    # ------------------------------------------------------------------
    # hr_candidate_extracted_data
    # ------------------------------------------------------------------
    op.create_table(
        "hr_candidate_extracted_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidates.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("skills", sa.Text(), nullable=True),
        sa.Column("education", sa.JSON(), nullable=True),
        sa.Column("certifications", sa.JSON(), nullable=True),
        sa.Column("languages", sa.JSON(), nullable=True),
        sa.Column("previous_companies", sa.JSON(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ------------------------------------------------------------------
    # hr_candidate_notes
    # ------------------------------------------------------------------
    op.create_table(
        "hr_candidate_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_hr_notes_candidate", "hr_candidate_notes", ["candidate_id"])

    # ------------------------------------------------------------------
    # hr_candidate_tags
    # ------------------------------------------------------------------
    op.create_table(
        "hr_candidate_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(length=60), nullable=False),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("candidate_id", "tag", name="uq_hr_tags_candidate_tag"),
    )
    op.create_index("ix_hr_tags_candidate", "hr_candidate_tags", ["candidate_id"])
    op.create_index("ix_hr_tags_tag", "hr_candidate_tags", ["tag"])

    # ------------------------------------------------------------------
    # hr_candidate_job_applications
    # ------------------------------------------------------------------
    op.create_table(
        "hr_candidate_job_applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_opening_id",
            sa.Integer(),
            sa.ForeignKey("hr_job_openings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default="cv_received",
        ),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("last_rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "candidate_id", "job_opening_id", name="uq_hr_applications_candidate_job"
        ),
    )
    op.create_index("ix_hr_apps_candidate", "hr_candidate_job_applications", ["candidate_id"])
    op.create_index("ix_hr_apps_job", "hr_candidate_job_applications", ["job_opening_id"])
    op.create_index("ix_hr_apps_status", "hr_candidate_job_applications", ["status"])
    op.create_index("ix_hr_apps_applied_at", "hr_candidate_job_applications", ["applied_at"])

    # ------------------------------------------------------------------
    # hr_candidate_scores
    # ------------------------------------------------------------------
    op.create_table(
        "hr_candidate_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_manual_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column(
            "overridden_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ------------------------------------------------------------------
    # hr_candidate_score_breakdowns
    # ------------------------------------------------------------------
    op.create_table(
        "hr_candidate_score_breakdowns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "score_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidate_scores.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("relevant_experience", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_skills", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("education", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("industry_experience", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gcc_qatar_experience", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("salary_fit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notice_period", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("visa_status", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("language_match", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.JSON(), nullable=True),
    )

    # ------------------------------------------------------------------
    # hr_candidate_ai_reviews
    # ------------------------------------------------------------------
    op.create_table(
        "hr_candidate_ai_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("weaknesses", sa.Text(), nullable=True),
        sa.Column("missing_information", sa.Text(), nullable=True),
        sa.Column("risk_points", sa.Text(), nullable=True),
        sa.Column("suggested_questions", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.String(length=40), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ------------------------------------------------------------------
    # hr_candidate_status_history
    # ------------------------------------------------------------------
    op.create_table(
        "hr_candidate_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_status", sa.String(length=40), nullable=True),
        sa.Column("new_status", sa.String(length=40), nullable=False),
        sa.Column(
            "changed_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("blacklist_approval", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_hr_status_history_application",
        "hr_candidate_status_history",
        ["application_id"],
    )
    op.create_index(
        "ix_hr_status_history_created_at",
        "hr_candidate_status_history",
        ["created_at"],
    )

    # ------------------------------------------------------------------
    # hr_interviews
    # ------------------------------------------------------------------
    op.create_table(
        "hr_interviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("round_name", sa.String(length=120), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column(
            "mode",
            sa.String(length=20),
            nullable=False,
            server_default="online",
        ),
        sa.Column("location_or_link", sa.String(length=500), nullable=True),
        sa.Column(
            "interviewer_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_hr_interviews_application", "hr_interviews", ["application_id"])
    op.create_index("ix_hr_interviews_scheduled_at", "hr_interviews", ["scheduled_at"])
    op.create_index("ix_hr_interviews_status", "hr_interviews", ["status"])
    op.create_index("ix_hr_interviews_interviewer", "hr_interviews", ["interviewer_id"])

    # ------------------------------------------------------------------
    # hr_interview_feedback
    # ------------------------------------------------------------------
    op.create_table(
        "hr_interview_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "interview_id",
            sa.Integer(),
            sa.ForeignKey("hr_interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "submitted_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("recommendation", sa.String(length=20), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("technical_score", sa.Integer(), nullable=True),
        sa.Column("communication_score", sa.Integer(), nullable=True),
        sa.Column("cultural_fit_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_hr_interview_feedback_interview", "hr_interview_feedback", ["interview_id"]
    )

    # ------------------------------------------------------------------
    # hr_offer_tracking
    # ------------------------------------------------------------------
    op.create_table(
        "hr_offer_tracking",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("salary_offered", sa.Integer(), nullable=True),
        sa.Column("joining_date", sa.Date(), nullable=True),
        sa.Column("benefits_summary", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_hr_offers_status", "hr_offer_tracking", ["status"])


def downgrade() -> None:
    # Reverse order of upgrade.
    op.drop_index("ix_hr_offers_status", table_name="hr_offer_tracking")
    op.drop_table("hr_offer_tracking")

    op.drop_index("ix_hr_interview_feedback_interview", table_name="hr_interview_feedback")
    op.drop_table("hr_interview_feedback")

    op.drop_index("ix_hr_interviews_interviewer", table_name="hr_interviews")
    op.drop_index("ix_hr_interviews_status", table_name="hr_interviews")
    op.drop_index("ix_hr_interviews_scheduled_at", table_name="hr_interviews")
    op.drop_index("ix_hr_interviews_application", table_name="hr_interviews")
    op.drop_table("hr_interviews")

    op.drop_index("ix_hr_status_history_created_at", table_name="hr_candidate_status_history")
    op.drop_index("ix_hr_status_history_application", table_name="hr_candidate_status_history")
    op.drop_table("hr_candidate_status_history")

    op.drop_table("hr_candidate_ai_reviews")
    op.drop_table("hr_candidate_score_breakdowns")
    op.drop_table("hr_candidate_scores")

    op.drop_index("ix_hr_apps_applied_at", table_name="hr_candidate_job_applications")
    op.drop_index("ix_hr_apps_status", table_name="hr_candidate_job_applications")
    op.drop_index("ix_hr_apps_job", table_name="hr_candidate_job_applications")
    op.drop_index("ix_hr_apps_candidate", table_name="hr_candidate_job_applications")
    op.drop_table("hr_candidate_job_applications")

    op.drop_index("ix_hr_tags_tag", table_name="hr_candidate_tags")
    op.drop_index("ix_hr_tags_candidate", table_name="hr_candidate_tags")
    op.drop_table("hr_candidate_tags")

    op.drop_index("ix_hr_notes_candidate", table_name="hr_candidate_notes")
    op.drop_table("hr_candidate_notes")

    op.drop_table("hr_candidate_extracted_data")

    op.drop_index("ix_hr_docs_file_hash", table_name="hr_candidate_documents")
    op.drop_index("ix_hr_docs_candidate", table_name="hr_candidate_documents")
    op.drop_table("hr_candidate_documents")

    op.drop_index("ix_hr_candidates_archived", table_name="hr_candidates")
    op.drop_index("ix_hr_candidates_blacklisted", table_name="hr_candidates")
    op.drop_index("ix_hr_candidates_mobile", table_name="hr_candidates")
    op.drop_index("ix_hr_candidates_email", table_name="hr_candidates")
    op.drop_index("ix_hr_candidates_full_name", table_name="hr_candidates")
    op.drop_table("hr_candidates")

    op.drop_index("ix_hr_jobs_posted_at", table_name="hr_job_openings")
    op.drop_index("ix_hr_jobs_status", table_name="hr_job_openings")
    op.drop_index("ix_hr_jobs_company", table_name="hr_job_openings")
    op.drop_index("ix_hr_jobs_department", table_name="hr_job_openings")
    op.drop_index("ix_hr_jobs_slug", table_name="hr_job_openings")
    op.drop_table("hr_job_openings")
