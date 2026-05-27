"""marketing — offer campaigns, catalogues, pages, view events

Revision ID: 20260527_0016
Revises: 20260527_0015
Create Date: 2026-05-27

Bootstraps the Digital Offers & Catalogue module.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260527_0016"
down_revision: str = "20260527_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "offer_campaigns" not in existing_tables:
        op.create_table(
            "offer_campaigns",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(200), nullable=False, unique=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("banner_image_url", sa.String(500), nullable=True),
            sa.Column("theme_color", sa.String(16), nullable=True),
            sa.Column("branch", sa.String(120), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
            sa.Column(
                "is_featured",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "is_killer_offer",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "is_flash_sale",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "sort_order",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("meta_title", sa.String(200), nullable=True),
            sa.Column("meta_description", sa.String(500), nullable=True),
            sa.Column(
                "view_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
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
        op.create_index("ix_offer_campaigns_slug", "offer_campaigns", ["slug"])
        op.create_index("ix_offer_campaigns_branch", "offer_campaigns", ["branch"])
        op.create_index(
            "ix_offer_campaigns_start_date", "offer_campaigns", ["start_date"]
        )
        op.create_index(
            "ix_offer_campaigns_end_date", "offer_campaigns", ["end_date"]
        )
        op.create_index(
            "ix_offer_campaigns_is_active", "offer_campaigns", ["is_active"]
        )
        op.create_index(
            "ix_offer_campaigns_is_featured", "offer_campaigns", ["is_featured"]
        )
        op.create_index(
            "ix_offer_campaigns_created_at", "offer_campaigns", ["created_at"]
        )
        if bind.dialect.name != "sqlite":
            try:
                op.create_foreign_key(
                    "fk_offer_campaigns_created_by",
                    "offer_campaigns",
                    "users",
                    ["created_by_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            except Exception:
                pass

    if "catalogues" not in existing_tables:
        op.create_table(
            "catalogues",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("campaign_id", sa.Integer(), nullable=True),
            sa.Column("slug", sa.String(200), nullable=False, unique=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("pdf_url", sa.String(500), nullable=True),
            sa.Column("pdf_original_filename", sa.String(500), nullable=True),
            sa.Column("file_size_bytes", sa.Integer(), nullable=True),
            sa.Column("cover_image_url", sa.String(500), nullable=True),
            sa.Column(
                "page_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "processing_status",
                sa.String(16),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("processing_error", sa.Text(), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
            sa.Column(
                "is_featured",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "sort_order",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("meta_title", sa.String(200), nullable=True),
            sa.Column("meta_description", sa.String(500), nullable=True),
            sa.Column(
                "view_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "download_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
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
        op.create_index("ix_catalogues_slug", "catalogues", ["slug"])
        op.create_index("ix_catalogues_campaign_id", "catalogues", ["campaign_id"])
        op.create_index(
            "ix_catalogues_processing_status", "catalogues", ["processing_status"]
        )
        op.create_index("ix_catalogues_is_active", "catalogues", ["is_active"])
        op.create_index("ix_catalogues_created_at", "catalogues", ["created_at"])
        if bind.dialect.name != "sqlite":
            try:
                op.create_foreign_key(
                    "fk_catalogues_campaign",
                    "catalogues",
                    "offer_campaigns",
                    ["campaign_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
                op.create_foreign_key(
                    "fk_catalogues_created_by",
                    "catalogues",
                    "users",
                    ["created_by_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            except Exception:
                pass

    if "catalogue_pages" not in existing_tables:
        op.create_table(
            "catalogue_pages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "catalogue_id",
                sa.Integer(),
                sa.ForeignKey("catalogues.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("page_number", sa.Integer(), nullable=False),
            sa.Column("image_url", sa.String(500), nullable=False),
            sa.Column("thumbnail_url", sa.String(500), nullable=False),
            sa.Column("width", sa.Integer(), nullable=False),
            sa.Column("height", sa.Integer(), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "catalogue_id", "page_number", name="uq_catalogue_pages_cat_page"
            ),
        )
        op.create_index(
            "ix_catalogue_pages_catalogue_id",
            "catalogue_pages",
            ["catalogue_id"],
        )

    if "catalogue_view_events" not in existing_tables:
        op.create_table(
            "catalogue_view_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "catalogue_id",
                sa.Integer(),
                sa.ForeignKey("catalogues.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("session_hash", sa.String(64), nullable=True),
            sa.Column("device", sa.String(16), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column(
                "viewed_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_catalogue_view_events_catalogue_id",
            "catalogue_view_events",
            ["catalogue_id"],
        )
        op.create_index(
            "ix_catalogue_view_events_viewed_at",
            "catalogue_view_events",
            ["viewed_at"],
        )


def downgrade() -> None:
    for table in (
        "catalogue_view_events",
        "catalogue_pages",
        "catalogues",
        "offer_campaigns",
    ):
        try:
            op.drop_table(table)
        except Exception:
            pass
