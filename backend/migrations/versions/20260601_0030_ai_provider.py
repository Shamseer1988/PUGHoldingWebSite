"""ai — add provider + base_url columns to ``hr_ai_settings``

Multi-provider AI: lets a system admin point "live" chat at Azure
OpenAI (the historic default), any OpenAI-compatible server
(vLLM / LM Studio / OpenAI direct), or a local Ollama daemon — at
runtime, without a redeploy.

Two additive, nullable columns:

  * ``provider``  — which backend serves live chat
                    (``azure`` | ``openai_compatible`` | ``ollama``).
                    NULL means "fall back to the AI_PROVIDER env var,
                    then azure", so existing rows keep their exact
                    current behaviour with no backfill.
  * ``base_url``  — the OpenAI-compatible / Ollama base URL. Ignored
                    by the Azure provider. The API key for these
                    providers stays in .env (AI_API_KEY) — never the DB.

Purely additive (nullable, no backfill) per the project's migration
policy.

Revision ID: 20260601_0030
Revises: 20260601_0029
Create Date: 2026-06-01 15:10:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260601_0030"
down_revision: Union[str, Sequence[str], None] = "20260601_0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("hr_ai_settings") as batch:
        batch.add_column(
            sa.Column("provider", sa.String(length=32), nullable=True)
        )
        batch.add_column(
            sa.Column("base_url", sa.String(length=500), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("hr_ai_settings") as batch:
        batch.drop_column("base_url")
        batch.drop_column("provider")
