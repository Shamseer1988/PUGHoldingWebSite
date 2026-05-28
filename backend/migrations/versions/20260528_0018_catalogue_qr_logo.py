"""marketing — add catalogues.qr_logo_url for per-catalogue QR branding

Revision ID: 20260528_0018
Revises: 20260527_0017
Create Date: 2026-05-28

Branches (Lulu, Ansar Gallery, ...) want their own logo stamped in
the centre of the catalogue's share QR. The old endpoint only
honoured a single global ``uploads/brand-logo.png`` file, which
forced every branch to use the same image. Add a nullable
``qr_logo_url`` column so each catalogue can carry its own logo;
when null we still fall back to the global file, then the "PUG"
text monogram.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260528_0018"
down_revision: str = "20260527_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "catalogues",
        sa.Column("qr_logo_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("catalogues", "qr_logo_url")
