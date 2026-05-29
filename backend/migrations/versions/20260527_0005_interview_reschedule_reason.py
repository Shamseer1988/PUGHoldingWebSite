"""hr — add reschedule_reason column to hr_interviews

Revision ID: 20260527_0005
Revises: 20260527_0004
Create Date: 2026-05-27

Phase 5 — Interview reschedule system. The master plan asks for a
reason captured every time HR moves the schedule. Currently the
audit_logs row captures the *change*, but not the human reason. This
adds the column directly on the interview row so the candidate-facing
email + the UI can display "Rescheduled because <reason>" without a
join.

Existing rows keep NULL.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260527_0005"
down_revision: str = "20260527_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("hr_interviews")}
    if "reschedule_reason" in existing:
        return
    with op.batch_alter_table("hr_interviews") as batch:
        batch.add_column(sa.Column("reschedule_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("hr_interviews") as batch:
        try:
            batch.drop_column("reschedule_reason")
        except Exception:
            pass
