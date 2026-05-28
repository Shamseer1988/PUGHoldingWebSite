"""C-4 — Postgres full-text search on candidate CV body

Revision ID: 20260528_0021
Revises: 20260528_0020
Create Date: 2026-05-28

Adds a ``tsvector`` column + GIN index on
``hr_candidate_extracted_data.full_text`` so the HR candidate search
can match against the CV body, not just the candidate's name /
email / mobile.

The column is a ``GENERATED ALWAYS AS ... STORED`` derivation —
Postgres keeps it in sync with ``full_text`` automatically, no
trigger needed (Postgres 12+ supports generated tsvector columns
natively).

SQLite test path: this migration is a no-op on SQLite. The
candidate_search code branches on dialect — Postgres uses the
indexed tsvector + ``@@`` operator; SQLite falls back to ``ILIKE``
on the same ``full_text`` column. Same observable behaviour in
tests, dramatically faster on the production engine that actually
hosts the corpus.

The ``'simple'`` dictionary is intentional: CVs are multilingual
(English, Arabic, French, etc.) and the language-specific stemmers
collapse meaningful tokens in surprising ways. ``simple`` is
case-insensitive, accent-stripping (when paired with the
``unaccent`` ext — if installed) and language-agnostic, which is
what HR actually wants when looking for "java", "RabbitMQ",
"كاتب", or proper nouns.
"""
from __future__ import annotations

from alembic import op


revision: str = "20260528_0021"
down_revision: str = "20260528_0020"
branch_labels = None
depends_on = None


_COL_NAME = "search_vector"
_INDEX_NAME = "ix_hr_candidate_extracted_data_search_vector"
_TABLE = "hr_candidate_extracted_data"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite test environments and any other non-Postgres backend
        # skip the FTS column entirely. The application code branches
        # on dialect — see ``app/services/candidate_search.py``.
        return

    # ``IF NOT EXISTS`` so re-running the migration after a failed
    # partial upgrade is safe. ``STORED`` keeps the tsvector on disk
    # so the GIN index can reference it.
    op.execute(
        f"""
        ALTER TABLE {_TABLE}
        ADD COLUMN IF NOT EXISTS {_COL_NAME} tsvector
        GENERATED ALWAYS AS (
            to_tsvector('simple', coalesce(full_text, ''))
        ) STORED
        """
    )
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS {_INDEX_NAME}
        ON {_TABLE} USING GIN ({_COL_NAME})
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(f"DROP INDEX IF EXISTS {_INDEX_NAME}")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS {_COL_NAME}")
