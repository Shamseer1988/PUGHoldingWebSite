"""Add `variants` JSON to cms_media_assets for responsive image URLs.

Image uploads now generate WebP + JPEG variants at three widths
(thumb / medium / large) so public pages serve a 1/3 - 1/10 sized
payload instead of the original full-resolution file. The variant
URL map is stored on the asset row.

Backfilling existing rows is handled out-of-band by
``app.scripts.backfill_image_variants`` — running it is optional;
rows without ``variants`` continue to serve the original URL via
the ``ResponsiveImage`` frontend fallback.

Revision ID: 20260525_0020
Revises: 20260525_0019
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260525_0020"
down_revision: Union[str, None] = "20260525_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cms_media_assets") as batch:
        batch.add_column(sa.Column("variants", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cms_media_assets") as batch:
        batch.drop_column("variants")
