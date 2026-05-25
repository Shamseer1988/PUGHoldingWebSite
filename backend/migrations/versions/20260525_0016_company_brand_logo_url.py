"""Add brand_logo_url column to companies.

Optional uploaded brand-logo image for a company. When set, the
public site renders this logo in place of the gradient `initials`
tile on company cards, the homepage Group Companies showcase,
and the company detail page. Nullable so existing companies keep
showing initials with zero migration data.

Revision ID: 20260525_0016
Revises: 20260524_0015
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260525_0016"
down_revision: Union[str, None] = "20260524_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("companies") as batch:
        batch.add_column(
            sa.Column("brand_logo_url", sa.String(length=500), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("companies") as batch:
        batch.drop_column("brand_logo_url")
