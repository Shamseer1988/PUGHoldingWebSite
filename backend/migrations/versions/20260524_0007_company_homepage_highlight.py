"""Add homepage highlight description + points to companies.

Surfaces two new nullable Text columns the public homepage Group
Companies section uses to render a "Company Highlight" block below
each panel's CTA. Existing rows are left untouched — when the column
is NULL the homepage falls back to `long_description` (trimmed) and
then `short_description`.

Revision ID: 20260524_0007
Revises: 20260524_0006
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0007"
down_revision: Union[str, None] = "20260524_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("companies") as batch:
        batch.add_column(
            sa.Column("homepage_highlight_description", sa.Text(), nullable=True)
        )
        batch.add_column(
            sa.Column("homepage_highlight_points", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("companies") as batch:
        batch.drop_column("homepage_highlight_points")
        batch.drop_column("homepage_highlight_description")
