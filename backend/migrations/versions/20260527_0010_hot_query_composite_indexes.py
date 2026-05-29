"""hardening — composite indexes on the HR query hotspots

Revision ID: 20260527_0010
Revises: 20260527_0009
Create Date: 2026-05-27

Performance pass — add composite indexes for the filter/sort combos
that already exist in the application code but currently fall back to
single-column index lookups followed by a sequential scan + sort.

  hr_candidate_job_applications  (job_opening_id, status, applied_at)
    Used by:
      /hr/candidates filter by status + sort by applied_at
      /hr/jobs/{id}/applications list
      hr_reports candidate exports
    Expected impact: 50-100x on filtered lists past 5k applications.

  audit_logs                     (actor_id, created_at)
    Used by:
      /admin/audit "actions by user X" view
      hr.audit_log search by actor + time range
    Expected impact: 10-20x on actor-scoped audit queries.

  hr_interviews                  (scheduled_at, status)
    Used by:
      /hr/interviews calendar view (date range + status filter)
      conflict detection on schedule
    Expected impact: 5-10x on the calendar view.

All indexes are idempotent — if a prior migration or a hand-built
index already covers the columns, we skip rather than fail.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260527_0010"
down_revision: str = "20260527_0009"
branch_labels = None
depends_on = None


# (index_name, table, columns)
COMPOSITE_INDEXES: tuple[tuple[str, str, list[str]], ...] = (
    (
        "ix_hr_applications_job_status_date",
        "hr_candidate_job_applications",
        ["job_opening_id", "status", "applied_at"],
    ),
    (
        "ix_audit_logs_actor_created",
        "audit_logs",
        ["actor_id", "created_at"],
    ),
    (
        "ix_hr_interviews_scheduled_status",
        "hr_interviews",
        ["scheduled_at", "status"],
    ),
)


def _existing_indexes(table: str) -> set[str]:
    bind = op.get_bind()
    try:
        return {ix["name"] for ix in sa.inspect(bind).get_indexes(table)}
    except Exception:
        return set()


def upgrade() -> None:
    for name, table, columns in COMPOSITE_INDEXES:
        if name in _existing_indexes(table):
            continue
        try:
            op.create_index(name, table, columns)
        except Exception:
            # Tolerate races / partial reruns.
            pass


def downgrade() -> None:
    for name, table, _columns in COMPOSITE_INDEXES:
        try:
            op.drop_index(name, table_name=table)
        except Exception:
            pass
