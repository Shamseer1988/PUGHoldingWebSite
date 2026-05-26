"""Add cms_site_pages — admin-editable hero / banner / sections per route.

Creates a new table keyed by ``page_key`` (about, companies, careers,
contact, news, media), seeds one row per known key with the copy that
was previously hardcoded in the Next.js routes, and copies the
existing ``site_settings.<page>_banner_*`` URLs into the new table so
no banner image goes missing on upgrade.

The old ``site_settings.<page>_banner_*`` columns stay in the DB as a
safety net but the admin UI hides them and the public site reads
banners only from the new table.

Revision ID: 20260525_0019
Revises: 20260525_0018
Create Date: 2026-05-25
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260525_0019"
down_revision: Union[str, None] = "20260525_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default hero + section content seeded into the table. The values are
# the exact copy that lived in frontend/lib/dummy-data/site-content.ts
# and the public page modules so admins start with what the site
# already shows, not blank text.
DEFAULT_PAGES = {
    "about": {
        "hero_eyebrow": "About Paris United Group",
        "hero_title": (
            "A diversified holding group focused on quality, service, "
            "and operational excellence."
        ),
        "hero_description": (
            "Paris United Group Holding operates across retail, "
            "distribution, and services. We are a long-term builder of "
            "trusted, customer-obsessed businesses that serve "
            "communities and commercial partners every day."
        ),
        "sections": {
            "vision": {
                "title": "Our vision",
                "body": (
                    "To be the most trusted diversified group in the GCC "
                    "— delighting customers, partners, and employees "
                    "across every business we operate."
                ),
            },
            "mission": {
                "title": "Our mission",
                "body": (
                    "We bring quality products and dependable services "
                    "to communities and businesses, powered by "
                    "operational excellence, a customer-first culture, "
                    "and a long-term mindset."
                ),
            },
            "history_intro": {
                "body": (
                    "We started with one focused FMCG distribution "
                    "business and grew into a diversified group "
                    "operating across retail, distribution, and "
                    "services — guided by the same values throughout."
                ),
            },
            "leadership_header": {
                "eyebrow": "Leadership",
                "title": "Messages from our leadership",
                "body": "The Chairman, Managing Director, and Executive Directors.",
            },
        },
    },
    "companies": {
        "hero_eyebrow": "Our companies",
        "hero_title": "Explore the Paris United Group",
        "hero_description": (
            "A diversified portfolio of distribution, retail, and "
            "services businesses operating in Qatar and the wider GCC."
        ),
        "sections": {},
    },
    "careers": {
        "hero_eyebrow": "Careers",
        "hero_title": "Build your career with Paris United Group",
        "hero_description": (
            "Roles across retail operations, FMCG sales, engineering, "
            "real estate, services, HR, and group functions."
        ),
        "sections": {},
    },
    "contact": {
        "hero_eyebrow": "Contact",
        "hero_title": "Talk to Paris United Group",
        "hero_description": (
            "Reach the right department fast. Use the form below or any "
            "of the quick actions on the right."
        ),
        "sections": {},
    },
    "news": {
        "hero_eyebrow": "News & events",
        "hero_title": "What's happening at Paris United Group",
        "hero_description": (
            "Store launches, partnerships, CSR initiatives, and updates "
            "from across the group."
        ),
        "sections": {},
    },
    "media": {
        "hero_eyebrow": "Media",
        "hero_title": "Stores, events, team, and campaigns",
        "hero_description": (
            "A glimpse of life at Paris United Group — pick a category "
            "or click a tile to view it larger."
        ),
        "sections": {},
    },
}

# Map page_key → the existing site_settings column to copy banner data
# from. ``None`` means no equivalent column existed (companies + news
# share banners with other places).
BANNER_SOURCES = {
    "about": ("about_banner_image_url", None, "about_banner_video_url"),
    "companies": (None, None, None),
    "careers": ("careers_banner_image_url", "careers_banner_mobile_url", None),
    "contact": ("contact_banner_image_url", "contact_banner_mobile_url", None),
    "news": ("news_banner_image_url", "news_banner_mobile_url", None),
    "media": ("media_banner_image_url", "media_banner_mobile_url", None),
}


def upgrade() -> None:
    op.create_table(
        "cms_site_pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("page_key", sa.String(length=32), nullable=False, unique=True),
        sa.Column("hero_eyebrow", sa.String(length=120), nullable=True),
        sa.Column("hero_title", sa.String(length=255), nullable=True),
        sa.Column("hero_description", sa.Text(), nullable=True),
        sa.Column("banner_image_url", sa.String(length=500), nullable=True),
        sa.Column("banner_mobile_url", sa.String(length=500), nullable=True),
        sa.Column("banner_video_url", sa.String(length=500), nullable=True),
        sa.Column(
            "sections",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("seo_title", sa.String(length=255), nullable=True),
        sa.Column("seo_description", sa.String(length=500), nullable=True),
        sa.Column("seo_keywords", sa.String(length=500), nullable=True),
        sa.Column(
            "updated_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_cms_site_pages_page_key",
        "cms_site_pages",
        ["page_key"],
        unique=True,
    )

    # ---- Seed default rows + copy existing banner URLs --------------- #
    conn = op.get_bind()

    # Read the current site_settings row once (if it exists).
    existing = conn.execute(
        sa.text(
            "SELECT about_banner_image_url, about_banner_video_url, "
            "careers_banner_image_url, careers_banner_mobile_url, "
            "contact_banner_image_url, contact_banner_mobile_url, "
            "news_banner_image_url, news_banner_mobile_url, "
            "media_banner_image_url, media_banner_mobile_url "
            "FROM site_settings WHERE id = 1"
        )
    ).fetchone()

    settings_lookup = {}
    if existing is not None:
        settings_lookup = dict(existing._mapping)

    for page_key, defaults in DEFAULT_PAGES.items():
        image_col, mobile_col, video_col = BANNER_SOURCES[page_key]
        banner_image = settings_lookup.get(image_col) if image_col else None
        banner_mobile = settings_lookup.get(mobile_col) if mobile_col else None
        banner_video = settings_lookup.get(video_col) if video_col else None

        conn.execute(
            sa.text(
                "INSERT INTO cms_site_pages ("
                "  page_key, hero_eyebrow, hero_title, hero_description, "
                "  banner_image_url, banner_mobile_url, banner_video_url, "
                "  sections"
                ") VALUES ("
                "  :page_key, :hero_eyebrow, :hero_title, :hero_description, "
                "  :banner_image_url, :banner_mobile_url, :banner_video_url, "
                "  :sections"
                ")"
            ),
            {
                "page_key": page_key,
                "hero_eyebrow": defaults["hero_eyebrow"],
                "hero_title": defaults["hero_title"],
                "hero_description": defaults["hero_description"],
                "banner_image_url": banner_image,
                "banner_mobile_url": banner_mobile,
                "banner_video_url": banner_video,
                "sections": json.dumps(defaults["sections"]),
            },
        )


def downgrade() -> None:
    op.drop_index("ix_cms_site_pages_page_key", table_name="cms_site_pages")
    op.drop_table("cms_site_pages")
