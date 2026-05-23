"""Phase 5 - create CMS tables.

Revision ID: 20260523_0002
Revises: 20260523_0001
Create Date: 2026-05-23

Tables introduced:
- hero_slides
- companies
- company_services
- leadership_messages
- news_items
- contact_messages
- newsletter_subscribers
- site_settings (single-row)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260523_0002"
down_revision: Union[str, None] = "20260523_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # hero_slides
    op.create_table(
        "hero_slides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("eyebrow", sa.String(length=120), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cta_label", sa.String(length=120), nullable=True),
        sa.Column("cta_href", sa.String(length=255), nullable=True),
        sa.Column("secondary_cta_label", sa.String(length=120), nullable=True),
        sa.Column("secondary_cta_href", sa.String(length=255), nullable=True),
        sa.Column(
            "gradient",
            sa.String(length=255),
            nullable=False,
            server_default="from-pug-green-700 via-pug-green-500 to-pug-gold-500",
        ),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # companies
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("short_description", sa.String(length=500), nullable=True),
        sa.Column("long_description", sa.Text(), nullable=True),
        sa.Column("branches", sa.String(length=255), nullable=True),
        sa.Column(
            "accent",
            sa.String(length=255),
            nullable=False,
            server_default="from-pug-green-500 to-pug-gold-500",
        ),
        sa.Column("initials", sa.String(length=8), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_companies_slug"),
    )
    op.create_index("ix_companies_slug", "companies", ["slug"])
    op.create_index("ix_companies_category", "companies", ["category"])

    # company_services
    op.create_table(
        "company_services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_company_services_company_id", "company_services", ["company_id"])

    # leadership_messages
    op.create_table(
        "leadership_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=255), nullable=False),
        sa.Column("short_message", sa.String(length=500), nullable=True),
        sa.Column("full_message", sa.Text(), nullable=True),
        sa.Column(
            "accent",
            sa.String(length=255),
            nullable=False,
            server_default="from-pug-green-600 to-pug-gold-500",
        ),
        sa.Column("initials", sa.String(length=8), nullable=False),
        sa.Column("signature", sa.String(length=120), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_leadership_slug"),
    )

    # news_items
    op.create_table(
        "news_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=True),
        sa.Column(
            "cover",
            sa.String(length=255),
            nullable=False,
            server_default="from-pug-green-600 to-pug-gold-500",
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_news_slug"),
    )
    op.create_index("ix_news_slug", "news_items", ["slug"])
    op.create_index("ix_news_category", "news_items", ["category"])
    op.create_index("ix_news_published_at", "news_items", ["published_at"])

    # contact_messages
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("department", sa.String(length=64), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_replied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reply_body", sa.Text(), nullable=True),
        sa.Column(
            "replied_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_contact_email", "contact_messages", ["email"])
    op.create_index("ix_contact_is_read", "contact_messages", ["is_read"])
    op.create_index("ix_contact_created_at", "contact_messages", ["created_at"])

    # newsletter_subscribers
    op.create_table(
        "newsletter_subscribers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_newsletter_email"),
    )
    op.create_index("ix_newsletter_email", "newsletter_subscribers", ["email"])

    # site_settings (single row)
    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "site_name",
            sa.String(length=255),
            nullable=False,
            server_default="Paris United Group Holding",
        ),
        sa.Column("tagline", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=40), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_address", sa.String(length=500), nullable=True),
        sa.Column("whatsapp_number", sa.String(length=40), nullable=True),
        sa.Column("social_linkedin", sa.String(length=255), nullable=True),
        sa.Column("social_instagram", sa.String(length=255), nullable=True),
        sa.Column("social_facebook", sa.String(length=255), nullable=True),
        sa.Column("social_youtube", sa.String(length=255), nullable=True),
        sa.Column("seo_default_title", sa.String(length=255), nullable=True),
        sa.Column("seo_default_description", sa.String(length=500), nullable=True),
        sa.Column("seo_keywords", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("site_settings")
    op.drop_index("ix_newsletter_email", table_name="newsletter_subscribers")
    op.drop_table("newsletter_subscribers")
    op.drop_index("ix_contact_created_at", table_name="contact_messages")
    op.drop_index("ix_contact_is_read", table_name="contact_messages")
    op.drop_index("ix_contact_email", table_name="contact_messages")
    op.drop_table("contact_messages")
    op.drop_index("ix_news_published_at", table_name="news_items")
    op.drop_index("ix_news_category", table_name="news_items")
    op.drop_index("ix_news_slug", table_name="news_items")
    op.drop_table("news_items")
    op.drop_table("leadership_messages")
    op.drop_index("ix_company_services_company_id", table_name="company_services")
    op.drop_table("company_services")
    op.drop_index("ix_companies_category", table_name="companies")
    op.drop_index("ix_companies_slug", table_name="companies")
    op.drop_table("companies")
    op.drop_table("hero_slides")
