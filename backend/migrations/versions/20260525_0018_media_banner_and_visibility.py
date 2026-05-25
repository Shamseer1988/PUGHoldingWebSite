"""Add media-page banner URLs + per-asset public-visibility flag.

`site_settings`:
  - media_banner_image_url        Desktop banner for the public /media page.
  - media_banner_mobile_url       Mobile-tuned variant.

`cms_media_assets`:
  - is_public (bool, default true, indexed)
                                  When False the asset is hidden from
                                  the public /media gallery (and per-
                                  company galleries) but stays usable
                                  in hero slides, CMS pages, etc.

All columns are additive and nullable / default-true so existing rows
keep their behaviour after upgrade.

Revision ID: 20260525_0018
Revises: 20260525_0017
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260525_0018"
down_revision: Union[str, None] = "20260525_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.add_column(
            sa.Column("media_banner_image_url", sa.String(length=500), nullable=True)
        )
        batch.add_column(
            sa.Column("media_banner_mobile_url", sa.String(length=500), nullable=True)
        )

    with op.batch_alter_table("cms_media_assets") as batch:
        batch.add_column(
            sa.Column(
                "is_public",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            )
        )
    op.create_index(
        "ix_cms_media_assets_is_public",
        "cms_media_assets",
        ["is_public"],
    )


def downgrade() -> None:
    op.drop_index("ix_cms_media_assets_is_public", table_name="cms_media_assets")
    with op.batch_alter_table("cms_media_assets") as batch:
        batch.drop_column("is_public")

    with op.batch_alter_table("site_settings") as batch:
        batch.drop_column("media_banner_mobile_url")
        batch.drop_column("media_banner_image_url")
