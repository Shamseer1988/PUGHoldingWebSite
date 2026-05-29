"""hr — extend interview feedback with strengths / weaknesses / next_action

Revision ID: 20260527_0004
Revises: 20260527_0003
Create Date: 2026-05-27

Phase 4 of the HR overhaul. The interview-feedback form on the master
phase plan asks for three extra free-text inputs HR uses when reading
the recap:

  strengths     - what the candidate did well
  weaknesses    - areas of concern
  next_action   - recommended next step (next round / select / reject)

All three are optional text columns on hr_interview_feedback. Existing
rows get NULLs.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260527_0004"
down_revision: str = "20260527_0003"
branch_labels = None
depends_on = None


NEW_COLS = (
    ("strengths", sa.Text(), True),
    ("weaknesses", sa.Text(), True),
    ("next_action", sa.Text(), True),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("hr_interview_feedback")}

    with op.batch_alter_table("hr_interview_feedback") as batch:
        for name, type_, nullable in NEW_COLS:
            if name in existing:
                continue
            batch.add_column(sa.Column(name, type_, nullable=nullable))


def downgrade() -> None:
    with op.batch_alter_table("hr_interview_feedback") as batch:
        for name, _, _ in NEW_COLS:
            try:
                batch.drop_column(name)
            except Exception:
                pass
