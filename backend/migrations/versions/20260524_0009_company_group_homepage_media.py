"""Add Group Companies homepage video + highlight + stat-line fields.

Surfaces four new nullable columns on `companies` so admins can drive
the homepage Group Companies section without a code deploy:

- `homepage_group_highlight`        — short polished paragraph (160–240
  chars) shown inside the left-side showcase card.
- `homepage_group_stat_line`        — one-line stat strip rendered below
  the card. Example: "500+ Brand Partners · 15,000+ SKUs".
- `homepage_group_video_url`        — optional public URL to a short
  looping video used on the right-side media card on desktop. The
  existing `featured_image_url` is preserved as the poster + fallback.
- `homepage_group_video_poster_url` — optional poster image shown until
  the video has enough metadata to render the first frame.

All columns default to NULL so existing rows keep working — the public
homepage falls back to the existing image + text behaviour when these
fields are empty.

Revision ID: 20260524_0009
Revises: 20260524_0008
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0009"
down_revision: Union[str, None] = "20260524_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("companies") as batch:
        batch.add_column(
            sa.Column("homepage_group_highlight", sa.Text(), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "homepage_group_stat_line", sa.String(length=255), nullable=True
            )
        )
        batch.add_column(
            sa.Column(
                "homepage_group_video_url", sa.String(length=500), nullable=True
            )
        )
        batch.add_column(
            sa.Column(
                "homepage_group_video_poster_url",
                sa.String(length=500),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("companies") as batch:
        batch.drop_column("homepage_group_video_poster_url")
        batch.drop_column("homepage_group_video_url")
        batch.drop_column("homepage_group_stat_line")
        batch.drop_column("homepage_group_highlight")
