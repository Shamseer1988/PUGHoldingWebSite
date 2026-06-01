"""offer-letter templates + editable letter body

Revision ID: 20260601_0028
Revises: 20260531_0026
Create Date: 2026-06-01

Adds reusable offer-letter templates and an editable per-offer letter
body. Additive only:

* ``hr_offer_tracking``: ``letter_body`` TEXT (null for legacy offers,
  which keep using the generated prose).
* new ``hr_offer_letter_templates`` table.

Branches from 20260531_0026 (same parent as the assessment field-types
work on its own branch); if both land on main, an ``alembic merge`` will
reconcile the two heads.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260601_0028"
down_revision: str = "20260531_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "hr_offer_tracking",
        sa.Column("letter_body", sa.Text(), nullable=True),
    )

    op.create_table(
        "hr_offer_letter_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
        "ix_hr_offer_letter_templates_name",
        "hr_offer_letter_templates",
        ["name"],
    )


def downgrade() -> None:
    op.drop_index("ix_hr_offer_letter_templates_name")
    op.drop_table("hr_offer_letter_templates")
    op.drop_column("hr_offer_tracking", "letter_body")
