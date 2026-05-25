"""Add theme settings columns to site_settings.

Adds four optional columns the admin can set to override the brand
palette + fonts without a deploy:

  - theme_primary_hex   — primary brand color (hex string incl. '#')
  - theme_accent_hex    — accent / highlight color
  - theme_heading_font  — display / heading font family
  - theme_body_font     — base body font family

Leaving any column NULL keeps the existing Tailwind tokens so the
default Paris United Group palette continues to render unchanged.

Revision ID: 20260524_0010
Revises: 20260524_0009
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0010"
down_revision: Union[str, None] = "20260524_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.add_column(
            sa.Column("theme_primary_hex", sa.String(length=9), nullable=True)
        )
        batch.add_column(
            sa.Column("theme_accent_hex", sa.String(length=9), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "theme_heading_font", sa.String(length=120), nullable=True
            )
        )
        batch.add_column(
            sa.Column("theme_body_font", sa.String(length=120), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.drop_column("theme_body_font")
        batch.drop_column("theme_heading_font")
        batch.drop_column("theme_accent_hex")
        batch.drop_column("theme_primary_hex")
