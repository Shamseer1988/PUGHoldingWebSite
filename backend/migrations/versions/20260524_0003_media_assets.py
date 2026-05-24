"""Add media URL columns for hero / news / leadership and the site-wide
banner / about / brand fields.

Revision ID: 20260524_0003
Revises: 20260524_0002
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0003"
down_revision: Union[str, None] = "20260524_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("hero_slides") as batch:
        batch.add_column(sa.Column("background_image_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("background_video_url", sa.String(length=500), nullable=True))

    with op.batch_alter_table("news_items") as batch:
        batch.add_column(sa.Column("cover_image_url", sa.String(length=500), nullable=True))

    with op.batch_alter_table("leadership_messages") as batch:
        batch.add_column(sa.Column("photo_url", sa.String(length=500), nullable=True))

    with op.batch_alter_table("site_settings") as batch:
        # Page banners
        batch.add_column(sa.Column("about_banner_image_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("about_banner_video_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("careers_banner_image_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("careers_banner_mobile_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("contact_banner_image_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("contact_banner_mobile_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("news_banner_image_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("news_banner_mobile_url", sa.String(length=500), nullable=True))

        # Homepage extra sections
        batch.add_column(sa.Column("home_about_image_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("home_about_title", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("home_about_body", sa.Text(), nullable=True))
        batch.add_column(sa.Column("home_founder_image_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("home_founder_name", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("home_founder_role", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("home_founder_message", sa.Text(), nullable=True))

        # Trusted brand strip on the homepage. Stored as newline-separated
        # URLs in a single TEXT column to avoid schema explosion.
        batch.add_column(sa.Column("home_brand_logos", sa.Text(), nullable=True))
        batch.add_column(sa.Column("home_brand_strip_title", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.drop_column("home_brand_strip_title")
        batch.drop_column("home_brand_logos")
        batch.drop_column("home_founder_message")
        batch.drop_column("home_founder_role")
        batch.drop_column("home_founder_name")
        batch.drop_column("home_founder_image_url")
        batch.drop_column("home_about_body")
        batch.drop_column("home_about_title")
        batch.drop_column("home_about_image_url")
        batch.drop_column("news_banner_mobile_url")
        batch.drop_column("news_banner_image_url")
        batch.drop_column("contact_banner_mobile_url")
        batch.drop_column("contact_banner_image_url")
        batch.drop_column("careers_banner_mobile_url")
        batch.drop_column("careers_banner_image_url")
        batch.drop_column("about_banner_video_url")
        batch.drop_column("about_banner_image_url")

    with op.batch_alter_table("leadership_messages") as batch:
        batch.drop_column("photo_url")

    with op.batch_alter_table("news_items") as batch:
        batch.drop_column("cover_image_url")

    with op.batch_alter_table("hero_slides") as batch:
        batch.drop_column("background_video_url")
        batch.drop_column("background_image_url")
