"""Add hr_ai_settings (Phase 13).

Revision ID: 20260524_0004
Revises: 20260524_0003
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0004"
down_revision: Union[str, None] = "20260524_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hr_ai_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "mode",
            sa.String(length=16),
            nullable=False,
            server_default="disabled",
        ),
        sa.Column("azure_endpoint", sa.String(length=500), nullable=True),
        sa.Column("azure_deployment", sa.String(length=120), nullable=True),
        sa.Column("azure_api_version", sa.String(length=40), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column(
            "temperature",
            sa.Float(),
            nullable=False,
            server_default="0.2",
        ),
        sa.Column(
            "max_output_tokens",
            sa.Integer(),
            nullable=False,
            server_default="900",
        ),
        sa.Column(
            "request_timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default="45",
        ),
        sa.Column("extra_system_prompt", sa.Text(), nullable=True),
        sa.Column(
            "updated_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Seed the single-row settings entry so the GET endpoint always
    # finds something to return.
    op.execute(
        """
        INSERT INTO hr_ai_settings (id, mode, temperature, max_output_tokens,
                                    request_timeout_seconds)
        VALUES (1, 'disabled', 0.2, 900, 45)
        """
    )


def downgrade() -> None:
    op.drop_table("hr_ai_settings")
