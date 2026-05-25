"""Create cms_navigation_items table for admin-controlled menus.

Adds a single self-referential tree table so the public navbar +
mobile menu can be edited from the admin panel instead of being
hard-coded in the frontend. Existing installations get an empty
table on upgrade; the public navigation falls back to the
frontend's compiled-in defaults until an admin populates rows
(or the seed script does it for them).

Revision ID: 20260524_0011
Revises: 20260524_0010
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0011"
down_revision: Union[str, None] = "20260524_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cms_navigation_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("cms_navigation_items.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("href", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("mega_kind", sa.String(length=32), nullable=True),
        sa.Column(
            "open_in_new_tab",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
    op.create_index(
        "ix_cms_navigation_items_parent_id",
        "cms_navigation_items",
        ["parent_id"],
    )
    op.create_index(
        "ix_cms_navigation_items_display_order",
        "cms_navigation_items",
        ["display_order"],
    )
    op.create_index(
        "ix_cms_navigation_items_is_active",
        "cms_navigation_items",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cms_navigation_items_is_active", table_name="cms_navigation_items"
    )
    op.drop_index(
        "ix_cms_navigation_items_display_order",
        table_name="cms_navigation_items",
    )
    op.drop_index(
        "ix_cms_navigation_items_parent_id", table_name="cms_navigation_items"
    )
    op.drop_table("cms_navigation_items")
