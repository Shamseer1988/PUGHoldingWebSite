"""Trusted Brands showcase — structured brand table + section knobs.

Replaces the old "logo URLs in a textarea" brand strip on the
homepage with a proper structured model so admins can manage each
brand individually (name, logo, link, category, highlight toggle,
ordering, active flag), and adds section-level settings on
``site_settings`` for the upgraded luxury showcase (enabled,
eyebrow, title, subtitle, animation toggle, layout mode).

The old ``home_brand_logos`` + ``home_brand_strip_title`` columns
are kept untouched for one release so a rollback is safe. The data
migration phase parses any existing logo URLs out of
``home_brand_logos`` and inserts them as ``TrustedBrand`` rows so
the homepage doesn't lose its logos on upgrade.

Revision ID: 20260524_0015
Revises: 20260524_0014
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0015"
down_revision: Union[str, None] = "20260524_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------
    # New ``trusted_brands`` table
    # -------------------------------------------------------------------
    op.create_table(
        "trusted_brands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand_name", sa.String(length=160), nullable=False),
        sa.Column("logo_url", sa.String(length=500), nullable=False),
        sa.Column("logo_url_alt", sa.String(length=500), nullable=True),
        sa.Column("link_url", sa.String(length=500), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column(
            "is_highlight",
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
        "ix_trusted_brands_display_order",
        "trusted_brands",
        ["display_order"],
    )

    # -------------------------------------------------------------------
    # Section-level columns on ``site_settings``
    # -------------------------------------------------------------------
    with op.batch_alter_table("site_settings") as batch:
        batch.add_column(
            sa.Column(
                "home_brand_section_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            )
        )
        batch.add_column(
            sa.Column("home_brand_eyebrow", sa.String(length=120), nullable=True)
        )
        batch.add_column(
            sa.Column("home_brand_title", sa.String(length=255), nullable=True)
        )
        batch.add_column(sa.Column("home_brand_subtitle", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "home_brand_animation_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            )
        )
        batch.add_column(
            sa.Column(
                "home_brand_layout_mode",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'marquee'"),
            )
        )

    # -------------------------------------------------------------------
    # Data migration: lift existing logo URLs into the new table so
    # homepages don't suddenly empty out on first deploy.
    # -------------------------------------------------------------------
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT home_brand_logos, home_brand_strip_title FROM site_settings ORDER BY id LIMIT 1"
        )
    ).fetchone()

    if rows:
        existing_logos = (rows[0] or "").strip()
        existing_title = (rows[1] or "").strip()

        # Lift the title across so the new section preserves whatever
        # the admin already typed on the old strip.
        if existing_title:
            bind.execute(
                sa.text(
                    "UPDATE site_settings SET home_brand_title = :t WHERE id = (SELECT id FROM site_settings ORDER BY id LIMIT 1)"
                ),
                {"t": existing_title},
            )

        if existing_logos:
            order = 0
            for raw in existing_logos.splitlines():
                url = raw.strip()
                if not url:
                    continue
                order += 1
                # Best-effort brand name: derive from the file stem so
                # admins have a starting point they can rename later.
                stem = url.rstrip("/").split("/")[-1]
                if "." in stem:
                    stem = stem.rsplit(".", 1)[0]
                stem = stem.replace("_", " ").replace("-", " ").strip().title()
                brand_name = stem or f"Brand {order}"
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO trusted_brands
                          (brand_name, logo_url, display_order, is_active, is_highlight)
                        VALUES (:n, :u, :o, true, false)
                        """
                    ),
                    {"n": brand_name, "u": url, "o": order},
                )


def downgrade() -> None:
    with op.batch_alter_table("site_settings") as batch:
        batch.drop_column("home_brand_layout_mode")
        batch.drop_column("home_brand_animation_enabled")
        batch.drop_column("home_brand_subtitle")
        batch.drop_column("home_brand_title")
        batch.drop_column("home_brand_eyebrow")
        batch.drop_column("home_brand_section_enabled")
    op.drop_index("ix_trusted_brands_display_order", table_name="trusted_brands")
    op.drop_table("trusted_brands")
