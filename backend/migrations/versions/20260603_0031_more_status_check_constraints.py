"""hr — CHECK constraints on the remaining enum status columns

Revision ID: 20260603_0031
Revises: 20260601_0030
Create Date: 2026-06-03

Phase 0 (recruitment overhaul) DB-integrity follow-up to
``20260527_0009_status_check_constraints``. That migration predates the
Advanced HR module, so several later enum-bearing columns never got a
CHECK constraint. This bolts named constraints onto the ones whose value
set is a stable, app-controlled enum (verified: every write-site uses the
named constants):

  hr_offer_tracking          joining_status   (pending/joined/not_joined)
  hr_job_revisions           status           (pending/approved/rejected)
  hr_email_logs              status           (pending/sent/failed)
  hr_job_approval_history     action           (created/submitted/.../unpublished)
  hr_candidate_auto_reviews   decision         (auto_shortlisted/.../selected)
  hr_scheduled_reports        last_run_status  (pending/success/failed)

Deliberately left unconstrained: ``hr_candidate_ai_reviews.recommendation``
(LLM-generated — a CHECK could reject a valid-but-unlisted model output)
and ``hr_interviews.email_delivery_status`` (only ever holds "sent" today;
reserved for future delivery states).

Safety: on Postgres the constraints are added ``NOT VALID`` so the
migration never scans / can never fail on pre-existing rows — it only
enforces values written from here on. Run ``VALIDATE CONSTRAINT`` later
(after auditing legacy rows) to extend the check backwards if desired. On
SQLite (the test path) this is a no-op: the models already declare these
constraints, so ``create_all`` builds them in.
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260603_0031"
down_revision = "20260601_0030"
branch_labels = None
depends_on = None


# Mirror the enum tuples from app.models.hr_ats — duplicated here so the
# migration stays stable even if the model file is refactored later.
# Update both sides if a state is ever added.
OFFER_JOINING_STATUSES = ("pending", "joined", "not_joined")
REVISION_STATUSES = ("pending", "approved", "rejected")
EMAIL_LOG_STATUSES = ("pending", "sent", "failed")
APPROVAL_ACTIONS = (
    "created",
    "submitted",
    "approved",
    "rejected",
    "revision_requested",
    "revision_submitted",
    "published",
    "unpublished",
)
AUTO_REVIEW_DECISIONS = (
    "auto_shortlisted",
    "hr_review_pending",
    "auto_rejected",
    "duplicate",
    "selected",
)
SCHEDULED_REPORT_STATUSES = ("pending", "success", "failed")


# (table, constraint_name, column, allowed_values)
CONSTRAINTS = (
    (
        "hr_offer_tracking",
        "ck_hr_offers_joining_status",
        "joining_status",
        OFFER_JOINING_STATUSES,
    ),
    ("hr_job_revisions", "ck_hr_job_revisions_status", "status", REVISION_STATUSES),
    ("hr_email_logs", "ck_hr_email_logs_status", "status", EMAIL_LOG_STATUSES),
    (
        "hr_job_approval_history",
        "ck_hr_job_approval_history_action",
        "action",
        APPROVAL_ACTIONS,
    ),
    (
        "hr_candidate_auto_reviews",
        "ck_hr_candidate_auto_reviews_decision",
        "decision",
        AUTO_REVIEW_DECISIONS,
    ),
    (
        "hr_scheduled_reports",
        "ck_hr_scheduled_reports_last_run_status",
        "last_run_status",
        SCHEDULED_REPORT_STATUSES,
    ),
)


def _in_clause(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite can't ALTER TABLE ADD CONSTRAINT; the models carry these
        # constraints so a fresh sqlite DB (the test path) already has them.
        return
    for table, name, column, values in CONSTRAINTS:
        # DROP IF EXISTS first so a rerun on a partially-migrated DB is a
        # clean no-op. NOT VALID: enforce new writes without scanning or
        # failing on any pre-existing row.
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
        op.execute(
            f"ALTER TABLE {table} "
            f"ADD CONSTRAINT {name} CHECK ({_in_clause(column, values)}) NOT VALID"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    for table, name, _column, _values in CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
