"""hr — enforce enum CHECK constraints on every status-bearing column

Revision ID: 20260527_0009
Revises: 20260527_0008
Create Date: 2026-05-27

Phase 14 hardening — bolt named CHECK constraints onto every column
that's supposed to hold one of a fixed set of enum strings. Catches
typos, raw-SQL drift, and any future code path that bypasses the
service-layer state-machine guards. Mirrors the
``CheckConstraint`` declarations now present on the SQLAlchemy models
so ``Base.metadata.create_all`` (the test path) and this migration
(the prod path) converge on the same schema.

Tables + columns covered:

  hr_job_openings                  status, approval_status, publish_status
  hr_candidate_job_applications    status
  hr_interviews                    status, mode
  hr_offer_tracking                status, approval_status

SQLite cannot add CHECK constraints to an existing table without
rebuilding it, so on SQLite we no-op (the model definitions already
carry the constraint at create_all time, which is the only path that
matters for the test suite).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260527_0009"
down_revision: str = "20260527_0008"
branch_labels = None
depends_on = None


# Mirror the enum tuples defined in app.models.hr_ats — we duplicate
# them here so migrations stay stable even if the model file is
# refactored later. Update both sides if a state is ever added.
JOB_STATUSES = ("open", "on_hold", "closed")
APPROVAL_STATUSES = (
    "draft",
    "pending_approval",
    "approved",
    "rejected",
    "revision_required",
)
PUBLISH_STATUSES = ("draft", "published", "unpublished")
RECRUITMENT_STATUSES = (
    "cv_received",
    "ai_reviewed",
    "hr_review_pending",
    "shortlisted",
    "first_interview",
    "technical_interview",
    "final_interview",
    "waiting_list",
    "recommended_for_offer",
    "selected",
    "offer_sent",
    "joined",
    "not_joined",
    "rejected",
    "blacklisted",
)
INTERVIEW_STATUSES = (
    "scheduled",
    "completed",
    "cancelled",
    "rescheduled",
    "no_show",
)
INTERVIEW_MODES = ("online", "phone", "in_person")
OFFER_STATUSES = (
    "draft",
    "pending_approval",
    "approved",
    "sent",
    "accepted",
    "declined",
    "withdrawn",
    "joined",
    "not_joined",
)
OFFER_APPROVAL_STATUSES = (
    "draft",
    "pending_approval",
    "approved",
    "rejected",
)


# (table, constraint_name, column, allowed_values)
CONSTRAINTS = (
    ("hr_job_openings", "ck_hr_jobs_status", "status", JOB_STATUSES),
    (
        "hr_job_openings",
        "ck_hr_jobs_approval_status",
        "approval_status",
        APPROVAL_STATUSES,
    ),
    (
        "hr_job_openings",
        "ck_hr_jobs_publish_status",
        "publish_status",
        PUBLISH_STATUSES,
    ),
    (
        "hr_candidate_job_applications",
        "ck_hr_applications_status",
        "status",
        RECRUITMENT_STATUSES,
    ),
    ("hr_interviews", "ck_hr_interviews_status", "status", INTERVIEW_STATUSES),
    ("hr_interviews", "ck_hr_interviews_mode", "mode", INTERVIEW_MODES),
    ("hr_offer_tracking", "ck_hr_offers_status", "status", OFFER_STATUSES),
    (
        "hr_offer_tracking",
        "ck_hr_offers_approval_status",
        "approval_status",
        OFFER_APPROVAL_STATUSES,
    ),
)


def _in_clause(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite can't ALTER TABLE ADD CONSTRAINT; the models already
        # declare these constraints so a fresh sqlite DB built via
        # create_all has them. Nothing to do here.
        return
    for table, name, column, values in CONSTRAINTS:
        try:
            op.create_check_constraint(name, table, _in_clause(column, values))
        except Exception:
            # Idempotent — if the constraint already exists (e.g. a
            # rerun on a partially-migrated DB), skip it.
            pass


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    for table, name, _column, _values in CONSTRAINTS:
        try:
            op.drop_constraint(name, table, type_="check")
        except Exception:
            pass
