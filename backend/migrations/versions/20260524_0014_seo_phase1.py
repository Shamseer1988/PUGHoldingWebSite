"""SEO Configuration phase 1 — seo_settings, seo_verifications,
tracking_integrations.

Adds the three foundational tables that back the Admin → Settings →
SEO Configuration module:

  * ``seo_settings`` — singleton row (matches the existing
    ``site_settings`` shape) that owns canonical URL, default meta
    title / description, feature toggles for sitemap / robots /
    Open Graph / Twitter / JSON-LD / canonical / hreflang /
    breadcrumb-schema.

  * ``seo_verifications`` — one row per domain-verification record
    (Google Search Console, Bing, Meta, Pinterest, Yandex, etc.).
    Supports four verification types: meta tag (name/content),
    pasted full ``<meta>`` snippet, HTML file, or DNS TXT (reference
    only — never rendered publicly).

  * ``tracking_integrations`` — one row per analytics / marketing
    integration (Google Tag Manager, GA4 direct, Meta Pixel,
    Microsoft Clarity, LinkedIn Insight, TikTok Pixel, X Pixel,
    custom). Stores the ID + placement + load behaviour. Phase 1
    rendering only honours rows where ``is_active`` is true.

Existing fields on ``site_settings`` (``seo_default_title``,
``seo_default_description``, ``seo_keywords``, ``social_*_url``) are
deliberately left untouched — they continue to drive whatever
already consumes them. The new ``seo_settings`` row is *additive* and
becomes the authoritative source for the public head injection
component shipped with this phase.

Revision ID: 20260524_0014
Revises: 20260524_0013
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0014"
down_revision: Union[str, None] = "20260524_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # seo_settings (singleton)
    # ------------------------------------------------------------------
    op.create_table(
        "seo_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_name", sa.String(length=255), nullable=True),
        sa.Column("default_meta_title", sa.String(length=255), nullable=True),
        sa.Column("default_meta_description", sa.String(length=500), nullable=True),
        sa.Column("default_meta_keywords", sa.String(length=500), nullable=True),
        sa.Column("canonical_base_url", sa.String(length=500), nullable=True),
        sa.Column("default_language", sa.String(length=16), nullable=True),
        sa.Column("default_country", sa.String(length=16), nullable=True),
        sa.Column("default_og_image", sa.String(length=500), nullable=True),
        sa.Column("default_twitter_image", sa.String(length=500), nullable=True),
        # Feature toggles. All default-on so a fresh install still has
        # a sensible head; admins can opt-out individually.
        sa.Column(
            "enable_sitemap",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "enable_robots",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "enable_open_graph",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "enable_twitter_cards",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "enable_json_ld",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "enable_canonical",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "enable_hreflang",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "enable_breadcrumb_schema",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        # Sitemap defaults (admins can override per-page in Phase 2).
        sa.Column("sitemap_default_changefreq", sa.String(length=20), nullable=True),
        sa.Column("sitemap_default_priority", sa.Float(), nullable=True),
        sa.Column(
            "sitemap_include_static",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "sitemap_include_companies",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "sitemap_include_cms_pages",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "sitemap_include_news",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        # Robots overrides.
        sa.Column(
            "robots_use_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("robots_custom_content", sa.Text(), nullable=True),
        sa.Column("robots_extra_disallows", sa.Text(), nullable=True),
        # Audit columns.
        sa.Column(
            "updated_by_id",
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

    # ------------------------------------------------------------------
    # seo_verifications
    # ------------------------------------------------------------------
    op.create_table(
        "seo_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Provider key — `google`, `bing`, `meta`, `pinterest`,
        # `yandex`, `linkedin`, `tiktok`, `microsoft_ads`, `custom`.
        sa.Column("provider", sa.String(length=40), nullable=False),
        # `meta_tag`, `full_meta_tag`, `html_file`, `dns_txt`.
        sa.Column("verification_type", sa.String(length=20), nullable=False),
        sa.Column("verification_name", sa.String(length=120), nullable=True),
        sa.Column("verification_content", sa.String(length=500), nullable=True),
        sa.Column("full_meta_tag", sa.Text(), nullable=True),
        sa.Column("html_filename", sa.String(length=255), nullable=True),
        sa.Column("html_file_content", sa.Text(), nullable=True),
        sa.Column("dns_txt_value", sa.String(length=500), nullable=True),
        # `pending`, `verified_manually`, `failed`, `dns_required`.
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_id",
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
    # Filename must be unique among active rows so the verification-
    # file route can dispatch by filename without ambiguity. A partial
    # index isn't portable across SQLite + Postgres on Alembic, so we
    # enforce uniqueness in application code instead.
    op.create_index(
        "ix_seo_verifications_html_filename",
        "seo_verifications",
        ["html_filename"],
    )
    op.create_index(
        "ix_seo_verifications_provider",
        "seo_verifications",
        ["provider"],
    )

    # ------------------------------------------------------------------
    # tracking_integrations
    # ------------------------------------------------------------------
    op.create_table(
        "tracking_integrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("tracking_id", sa.String(length=120), nullable=True),
        sa.Column("secondary_id", sa.String(length=120), nullable=True),
        sa.Column(
            "data_layer_name",
            sa.String(length=60),
            nullable=False,
            server_default=sa.text("'dataLayer'"),
        ),
        # `head`, `body_start`, `body_end`.
        sa.Column(
            "placement",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'head'"),
        ),
        sa.Column(
            "enable_noscript",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "consent_mode_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "debug_mode",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_id",
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
        sa.UniqueConstraint("provider", name="uq_tracking_integration_provider"),
    )


def downgrade() -> None:
    op.drop_table("tracking_integrations")
    op.drop_index(
        "ix_seo_verifications_provider", table_name="seo_verifications"
    )
    op.drop_index(
        "ix_seo_verifications_html_filename", table_name="seo_verifications"
    )
    op.drop_table("seo_verifications")
    op.drop_table("seo_settings")
