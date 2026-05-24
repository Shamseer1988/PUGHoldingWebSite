"""Featured companies section: add columns to companies + site_settings.

Revision ID: 20260524_0002
Revises: 20260524_0001
Create Date: 2026-05-24

Adds:
- companies.featured_image_url, .cta_label, .cta_url, .is_highlighted
- site_settings.featured_companies_* (7 columns)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0002"
down_revision: Union[str, None] = "20260524_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # companies
    with op.batch_alter_table("companies") as batch:
        batch.add_column(sa.Column("featured_image_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("cta_label", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("cta_url", sa.String(length=500), nullable=True))
        batch.add_column(
            sa.Column(
                "is_highlighted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
    op.create_index("ix_companies_is_highlighted", "companies", ["is_highlighted"])

    # site_settings
    with op.batch_alter_table("site_settings") as batch:
        batch.add_column(
            sa.Column(
                "featured_companies_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            )
        )
        batch.add_column(sa.Column("featured_companies_eyebrow", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("featured_companies_title", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("featured_companies_subtitle", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("featured_companies_cta_label", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("featured_companies_cta_url", sa.String(length=500), nullable=True))
        batch.add_column(
            sa.Column(
                "featured_companies_animation_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.drop_column("featured_companies_animation_enabled")
        batch.drop_column("featured_companies_cta_url")
        batch.drop_column("featured_companies_cta_label")
        batch.drop_column("featured_companies_subtitle")
        batch.drop_column("featured_companies_title")
        batch.drop_column("featured_companies_eyebrow")
        batch.drop_column("featured_companies_enabled")

    op.drop_index("ix_companies_is_highlighted", table_name="companies")
    with op.batch_alter_table("companies") as batch:
        batch.drop_column("is_highlighted")
        batch.drop_column("cta_url")
        batch.drop_column("cta_label")
        batch.drop_column("featured_image_url")
