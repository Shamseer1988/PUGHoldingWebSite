"""hr jobs — add explicit changes_requested + published denormalised audit columns

Revision ID: 20260527_0002
Revises: 20260527_0001
Create Date: 2026-05-27

Phase 2 of the HR module overhaul. The ``job_openings`` row already
links to a ``hr_job_approval_history`` audit table, but the master
phase plan also wants five denormalised columns on the job itself so
queries like "every job published in May" or "every job currently
in changes_requested state" don't need a join:

  changes_requested_by_id   FK users  nullable
  changes_requested_at      datetime  nullable
  changes_requested_notes   text      nullable
  published_by_id           FK users  nullable
  published_at              datetime  nullable

The columns are populated by the endpoint handlers — see Phase 2
edits to app/api/endpoints/hr_jobs.py and app/services/job_approval.py.
Existing history rows are NOT backfilled; jobs that transitioned
before this migration keep nulls in the new columns until their next
transition.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260527_0002"
down_revision: str = "20260527_0001"
branch_labels = None
depends_on = None


NEW_COLS = (
    ("changes_requested_by_id", sa.Integer(), True),
    ("changes_requested_at", sa.DateTime(timezone=True), True),
    ("changes_requested_notes", sa.Text(), True),
    ("published_by_id", sa.Integer(), True),
    ("published_at", sa.DateTime(timezone=True), True),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("job_openings")}

    with op.batch_alter_table("job_openings") as batch:
        for name, type_, nullable in NEW_COLS:
            if name in existing:
                continue
            batch.add_column(sa.Column(name, type_, nullable=nullable))

    # Foreign keys for the *_by_id columns. SQLite (used in tests) can't
    # add FKs after the fact via plain ALTER, so we skip FK creation when
    # the dialect doesn't support it — the columns still work as
    # nullable ints; production Postgres adds the FKs properly.
    if bind.dialect.name != "sqlite":
        with op.batch_alter_table("job_openings") as batch:
            batch.create_foreign_key(
                "fk_job_openings_changes_requested_by",
                "users",
                ["changes_requested_by_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_foreign_key(
                "fk_job_openings_published_by",
                "users",
                ["published_by_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name != "sqlite":
        with op.batch_alter_table("job_openings") as batch:
            for name in ("fk_job_openings_changes_requested_by", "fk_job_openings_published_by"):
                try:
                    batch.drop_constraint(name, type_="foreignkey")
                except Exception:
                    pass

    with op.batch_alter_table("job_openings") as batch:
        for name, _, _ in NEW_COLS:
            try:
                batch.drop_column(name)
            except Exception:
                pass
