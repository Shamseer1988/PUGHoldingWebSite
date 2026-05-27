"""hr — Phase 8: archive audit fields on jobs and candidates

Revision ID: 20260527_0007
Revises: 20260527_0006
Create Date: 2026-05-27

Phase 8 replaces hard delete with soft archive for the two entities
HR most often "deletes" — jobs and candidates. The audit cluster
matches the existing job-approval pattern:

  is_archived      Boolean  default false  (Candidate already has this;
                                            JobOpening gains it here)
  archived_at      DateTime nullable
  archived_by_id   FK users SET NULL
  archive_reason   Text     nullable

The interview + offer tables intentionally keep hard delete:
interviews are still cheap to recreate, and offers already have a
withdraw lifecycle which is the right "soft delete" for that domain.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260527_0007"
down_revision: str = "20260527_0006"
branch_labels = None
depends_on = None


JOB_NEW_COLS = (
    ("is_archived", sa.Boolean(), False, "false"),
    ("archived_at", sa.DateTime(timezone=True), True, None),
    ("archived_by_id", sa.Integer(), True, None),
    ("archive_reason", sa.Text(), True, None),
)

CAND_NEW_COLS = (
    # Candidate.is_archived already exists from Phase 7.
    ("archived_at", sa.DateTime(timezone=True), True, None),
    ("archived_by_id", sa.Integer(), True, None),
    ("archive_reason", sa.Text(), True, None),
)


def _add_cols(table: str, cols: tuple) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns(table)}
    with op.batch_alter_table(table) as batch:
        for name, type_, nullable, server_default in cols:
            if name in existing:
                continue
            kwargs: dict = {"nullable": nullable}
            if server_default is not None:
                kwargs["server_default"] = server_default
            batch.add_column(sa.Column(name, type_, **kwargs))


def _drop_cols(table: str, cols: tuple) -> None:
    with op.batch_alter_table(table) as batch:
        for name, _, _, _ in cols:
            try:
                batch.drop_column(name)
            except Exception:
                pass


def upgrade() -> None:
    _add_cols("hr_job_openings", JOB_NEW_COLS)
    _add_cols("hr_candidates", CAND_NEW_COLS)

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        with op.batch_alter_table("hr_job_openings") as batch:
            try:
                batch.create_foreign_key(
                    "fk_job_openings_archived_by",
                    "users",
                    ["archived_by_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            except Exception:
                pass
        with op.batch_alter_table("hr_candidates") as batch:
            try:
                batch.create_foreign_key(
                    "fk_hr_candidates_archived_by",
                    "users",
                    ["archived_by_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            except Exception:
                pass


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        with op.batch_alter_table("hr_job_openings") as batch:
            try:
                batch.drop_constraint(
                    "fk_job_openings_archived_by", type_="foreignkey"
                )
            except Exception:
                pass
        with op.batch_alter_table("hr_candidates") as batch:
            try:
                batch.drop_constraint(
                    "fk_hr_candidates_archived_by", type_="foreignkey"
                )
            except Exception:
                pass
    _drop_cols("hr_candidates", CAND_NEW_COLS)
    _drop_cols("hr_job_openings", JOB_NEW_COLS)
