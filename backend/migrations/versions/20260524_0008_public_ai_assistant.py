"""Public Ask-PUG-AI assistant — settings + query log.

Adds two fields to hr_ai_settings (public_enabled, public_extra_system_prompt)
and a new public_ai_queries table for the chat usage log.

Revision ID: 20260524_0008
Revises: 20260524_0007
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0008"
down_revision: Union[str, None] = "20260524_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("hr_ai_settings") as batch:
        batch.add_column(
            sa.Column(
                "public_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            )
        )
        batch.add_column(
            sa.Column(
                "public_extra_system_prompt", sa.Text(), nullable=True
            )
        )

    op.create_table(
        "public_ai_queries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "was_fallback",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_public_ai_queries_session_id",
        "public_ai_queries",
        ["session_id"],
    )
    op.create_index(
        "ix_public_ai_queries_was_fallback",
        "public_ai_queries",
        ["was_fallback"],
    )
    op.create_index(
        "ix_public_ai_queries_created_at",
        "public_ai_queries",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_public_ai_queries_created_at", table_name="public_ai_queries"
    )
    op.drop_index(
        "ix_public_ai_queries_was_fallback", table_name="public_ai_queries"
    )
    op.drop_index(
        "ix_public_ai_queries_session_id", table_name="public_ai_queries"
    )
    op.drop_table("public_ai_queries")
    with op.batch_alter_table("hr_ai_settings") as batch:
        batch.drop_column("public_extra_system_prompt")
        batch.drop_column("public_enabled")
