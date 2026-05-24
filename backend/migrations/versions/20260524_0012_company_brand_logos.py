"""Create company_brand_logos table for the Group Companies marquee.

Adds a child table holding one row per uploaded brand / partner logo
attached to a Company. The public Group Companies card on the
homepage renders these as an auto-scrolling logo strip instead of
the text-chip fallback when at least one row exists.

Revision ID: 20260524_0012
Revises: 20260524_0011
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0012"
down_revision: Union[str, None] = "20260524_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_brand_logos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("link_url", sa.String(length=500), nullable=True),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        "ix_company_brand_logos_company_id",
        "company_brand_logos",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_company_brand_logos_company_id", table_name="company_brand_logos"
    )
    op.drop_table("company_brand_logos")
