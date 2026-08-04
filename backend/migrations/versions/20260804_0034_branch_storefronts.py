"""marketing — branch storefront fields + division links on campaigns/catalogues

Revision ID: 20260804_0034
Revises: 20260604_0033
Create Date: 2026-08-04

Turns a division from "a QR owner" into a customer-facing branch:

* ``marketing_divisions`` gains storefront columns — hero image,
  address, phone, email, WhatsApp, opening hours, maps link, six
  social URLs, and ``is_public`` to gate the page.
* ``offer_campaigns.division_id`` — structured branch targeting.
  NULL = all branches. The legacy free-text ``branch`` column is left
  in place so existing rows keep their targeting.
* ``catalogues.division_id`` — a catalogue can name its own branch
  even when its parent campaign runs group-wide (same campaign,
  different flyer per branch).

Strictly additive: no column is dropped or renamed, every new column
is nullable or carries a server default, so a rollback of the app
code keeps working against the new schema.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260804_0034"
down_revision: str = "20260604_0033"
branch_labels = None
depends_on = None


# (column, type) for the storefront block added to marketing_divisions.
DIVISION_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("hero_image_url", sa.String(500)),
    ("address", sa.Text()),
    ("phone", sa.String(64)),
    ("email", sa.String(255)),
    ("whatsapp", sa.String(64)),
    ("opening_hours", sa.Text()),
    ("maps_url", sa.Text()),
    ("facebook_url", sa.Text()),
    ("instagram_url", sa.Text()),
    ("tiktok_url", sa.Text()),
    ("youtube_url", sa.Text()),
    ("snapchat_url", sa.Text()),
    ("x_url", sa.Text()),
)


def _columns(inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # --- Division storefront columns ---------------------------------------
    if "marketing_divisions" in tables:
        existing = _columns(inspector, "marketing_divisions")
        for name, coltype in DIVISION_COLUMNS:
            if name not in existing:
                op.add_column(
                    "marketing_divisions", sa.Column(name, coltype, nullable=True)
                )
        if "is_public" not in existing:
            op.add_column(
                "marketing_divisions",
                sa.Column(
                    "is_public",
                    sa.Boolean(),
                    nullable=False,
                    server_default="true",
                ),
            )
            op.create_index(
                "ix_marketing_divisions_is_public",
                "marketing_divisions",
                ["is_public"],
            )

    # --- offer_campaigns.division_id ---------------------------------------
    if "offer_campaigns" in tables:
        existing = _columns(inspector, "offer_campaigns")
        if "division_id" not in existing:
            op.add_column(
                "offer_campaigns", sa.Column("division_id", sa.Integer(), nullable=True)
            )
            op.create_index(
                "ix_offer_campaigns_division_id", "offer_campaigns", ["division_id"]
            )
            # SQLite can't ALTER a table to add a constraint; batch mode
            # rebuilds it. Postgres takes the plain ALTER path.
            if bind.dialect.name != "sqlite":
                op.create_foreign_key(
                    "fk_offer_campaigns_division_id",
                    "offer_campaigns",
                    "marketing_divisions",
                    ["division_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

    # --- catalogues.division_id --------------------------------------------
    if "catalogues" in tables:
        existing = _columns(inspector, "catalogues")
        if "division_id" not in existing:
            op.add_column(
                "catalogues", sa.Column("division_id", sa.Integer(), nullable=True)
            )
            op.create_index(
                "ix_catalogues_division_id", "catalogues", ["division_id"]
            )
            if bind.dialect.name != "sqlite":
                op.create_foreign_key(
                    "fk_catalogues_division_id",
                    "catalogues",
                    "marketing_divisions",
                    ["division_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

    # --- Backfill division_id from the legacy free-text branch label -------
    # Existing campaigns carry a hand-typed branch ("Al Khor"). Where
    # that text matches a division's name case-insensitively, wire up
    # the FK so old campaigns appear on the right branch page without
    # anyone re-entering them. Non-matching labels are left alone — the
    # public layer still honours the text.
    if "offer_campaigns" in tables and "marketing_divisions" in tables:
        bind.execute(
            sa.text(
                """
                UPDATE offer_campaigns
                   SET division_id = d.id
                  FROM marketing_divisions AS d
                 WHERE offer_campaigns.division_id IS NULL
                   AND offer_campaigns.branch IS NOT NULL
                   AND LOWER(TRIM(offer_campaigns.branch)) = LOWER(TRIM(d.name))
                """
            )
            if bind.dialect.name != "sqlite"
            else sa.text(
                """
                UPDATE offer_campaigns
                   SET division_id = (
                        SELECT d.id FROM marketing_divisions d
                         WHERE LOWER(TRIM(d.name)) = LOWER(TRIM(offer_campaigns.branch))
                         LIMIT 1
                   )
                 WHERE division_id IS NULL AND branch IS NOT NULL
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "catalogues" in tables and "division_id" in _columns(inspector, "catalogues"):
        if bind.dialect.name != "sqlite":
            op.drop_constraint(
                "fk_catalogues_division_id", "catalogues", type_="foreignkey"
            )
        op.drop_index("ix_catalogues_division_id", table_name="catalogues")
        op.drop_column("catalogues", "division_id")

    if "offer_campaigns" in tables and "division_id" in _columns(
        inspector, "offer_campaigns"
    ):
        if bind.dialect.name != "sqlite":
            op.drop_constraint(
                "fk_offer_campaigns_division_id", "offer_campaigns", type_="foreignkey"
            )
        op.drop_index("ix_offer_campaigns_division_id", table_name="offer_campaigns")
        op.drop_column("offer_campaigns", "division_id")

    if "marketing_divisions" in tables:
        existing = _columns(inspector, "marketing_divisions")
        if "is_public" in existing:
            op.drop_index(
                "ix_marketing_divisions_is_public", table_name="marketing_divisions"
            )
            op.drop_column("marketing_divisions", "is_public")
        for name, _coltype in reversed(DIVISION_COLUMNS):
            if name in existing:
                op.drop_column("marketing_divisions", name)
