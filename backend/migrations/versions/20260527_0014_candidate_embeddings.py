"""F5 — candidate semantic-search embeddings

Revision ID: 20260527_0014
Revises: 20260527_0013
Create Date: 2026-05-27

Adds three columns to ``hr_candidate_extracted_data``:

  embedding              JSON list of floats — the candidate's
                         profile vector. Stored as JSON (not pgvector)
                         so the same migration runs on SQLite test
                         envs and bare Postgres deploys without
                         needing the extension.

  embedding_model        Name + version of the model that produced the
                         vector ("text-embedding-3-small@v1"), so the
                         backfill job can detect stale vectors after
                         a model upgrade.

  embedding_updated_at   When the embedding was last refreshed.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260527_0014"
down_revision: str = "20260527_0013"
branch_labels = None
depends_on = None


NEW_COLS = (
    ("embedding", sa.JSON(), True, None),
    ("embedding_model", sa.String(64), True, None),
    ("embedding_updated_at", sa.DateTime(timezone=True), True, None),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {
        c["name"] for c in inspector.get_columns("hr_candidate_extracted_data")
    }
    with op.batch_alter_table("hr_candidate_extracted_data") as batch:
        for name, type_, nullable, default in NEW_COLS:
            if name in existing:
                continue
            kwargs = {"nullable": nullable}
            if default is not None:
                kwargs["server_default"] = default
            batch.add_column(sa.Column(name, type_, **kwargs))


def downgrade() -> None:
    with op.batch_alter_table("hr_candidate_extracted_data") as batch:
        for name, _, _, _ in NEW_COLS:
            try:
                batch.drop_column(name)
            except Exception:
                pass
