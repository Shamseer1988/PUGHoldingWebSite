"""Add contact_map_embed to site_settings.

Adds a single nullable Text column that holds the admin-pasted map
embed for the public Contact page. Accepts either a bare Google Maps
/ OpenStreetMap embed URL or a full `<iframe>` snippet — the frontend
sanitises the value before rendering and only honours iframes whose
src resolves to a trusted maps host.

Revision ID: 20260524_0013
Revises: 20260524_0012
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0013"
down_revision: Union[str, None] = "20260524_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.add_column(
            sa.Column("contact_map_embed", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.drop_column("contact_map_embed")
