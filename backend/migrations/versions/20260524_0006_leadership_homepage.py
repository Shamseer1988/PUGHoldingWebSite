"""Unified Leadership Messages homepage section.

Adds the per-message fields required by the new homepage card
(role_label, message_paragraph_1/2, highlight_quote, signature_image,
cta, is_homepage_featured) and the section-level fields on
site_settings (enabled, eyebrow, title, subtitle, animation flag).

Data preservation:
- Existing leadership rows keep all their data.
- Chairman + MD rows are flagged `is_homepage_featured = true`.
- Existing short_message → highlight_quote (if quote is empty).
- Existing full_message → message_paragraph_1 (if empty).
- Existing site_settings.home_founder_* (if populated) seed the
  Chairman card's name / role / message — they're kept in the table
  for backwards compatibility but the homepage now reads from the
  Leadership Messages source of truth.
- Section copy defaults are written only when null so admin edits
  are never overwritten.

Revision ID: 20260524_0006
Revises: 20260524_0005
Create Date: 2026-05-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260524_0006"
down_revision: Union[str, None] = "20260524_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_EYEBROW = "Leadership messages"
DEFAULT_TITLE = "Guided by vision, driven by excellence"
DEFAULT_SUBTITLE = "A message from the leadership of Paris United Group Holding."


def upgrade() -> None:
    # ---- leadership_messages additions -------------------------------------
    with op.batch_alter_table("leadership_messages") as batch:
        batch.add_column(sa.Column("role_label", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("message_paragraph_1", sa.Text(), nullable=True))
        batch.add_column(sa.Column("message_paragraph_2", sa.Text(), nullable=True))
        batch.add_column(sa.Column("highlight_quote", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("signature_image_url", sa.String(length=500), nullable=True)
        )
        batch.add_column(sa.Column("cta_label", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("cta_url", sa.String(length=500), nullable=True))
        batch.add_column(
            sa.Column(
                "is_homepage_featured",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
    op.create_index(
        "ix_leadership_messages_is_homepage_featured",
        "leadership_messages",
        ["is_homepage_featured"],
    )

    # ---- site_settings additions ------------------------------------------
    with op.batch_alter_table("site_settings") as batch:
        batch.add_column(
            sa.Column(
                "home_leadership_section_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            )
        )
        batch.add_column(
            sa.Column(
                "home_leadership_section_eyebrow",
                sa.String(length=120),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "home_leadership_section_title",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "home_leadership_section_subtitle",
                sa.Text(),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "home_leadership_animation_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            )
        )

    # ---- data backfill ----------------------------------------------------
    # 1. Flag Chairman + MD rows as homepage-featured.
    op.execute(
        """
        UPDATE leadership_messages
           SET is_homepage_featured = true
         WHERE slug IN ('chairman', 'md')
        """
    )

    # 2. Seed role_label sensibly when empty.
    op.execute(
        """
        UPDATE leadership_messages
           SET role_label = 'CHAIRMAN''S MESSAGE'
         WHERE slug = 'chairman' AND (role_label IS NULL OR role_label = '')
        """
    )
    op.execute(
        """
        UPDATE leadership_messages
           SET role_label = 'MD MESSAGE'
         WHERE slug = 'md' AND (role_label IS NULL OR role_label = '')
        """
    )

    # 3. Copy short_message → highlight_quote / full_message → paragraph 1
    #    only when the new field is still empty.
    op.execute(
        """
        UPDATE leadership_messages
           SET highlight_quote = short_message
         WHERE highlight_quote IS NULL
           AND short_message IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE leadership_messages
           SET message_paragraph_1 = full_message
         WHERE message_paragraph_1 IS NULL
           AND full_message IS NOT NULL
        """
    )

    # 4. Lift the legacy home_founder_* settings into the Chairman row
    #    so the unified card has a sensible starting point — only when
    #    the Chairman row's new fields are empty (don't overwrite edits).
    op.execute(
        """
        UPDATE leadership_messages
           SET message_paragraph_1 = COALESCE(
                 message_paragraph_1,
                 (SELECT home_founder_message
                    FROM site_settings WHERE id = 1)
               )
         WHERE slug = 'chairman'
           AND message_paragraph_1 IS NULL
        """
    )

    # 5. Seed section copy defaults (only when null).
    op.execute(
        f"""
        UPDATE site_settings
           SET home_leadership_section_eyebrow = COALESCE(
                 home_leadership_section_eyebrow,
                 '{DEFAULT_EYEBROW}'
               ),
               home_leadership_section_title = COALESCE(
                 home_leadership_section_title,
                 '{DEFAULT_TITLE}'
               ),
               home_leadership_section_subtitle = COALESCE(
                 home_leadership_section_subtitle,
                 '{DEFAULT_SUBTITLE}'
               )
         WHERE id = 1
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_leadership_messages_is_homepage_featured",
        table_name="leadership_messages",
    )
    with op.batch_alter_table("leadership_messages") as batch:
        batch.drop_column("is_homepage_featured")
        batch.drop_column("cta_url")
        batch.drop_column("cta_label")
        batch.drop_column("signature_image_url")
        batch.drop_column("highlight_quote")
        batch.drop_column("message_paragraph_2")
        batch.drop_column("message_paragraph_1")
        batch.drop_column("role_label")

    with op.batch_alter_table("site_settings") as batch:
        batch.drop_column("home_leadership_animation_enabled")
        batch.drop_column("home_leadership_section_subtitle")
        batch.drop_column("home_leadership_section_title")
        batch.drop_column("home_leadership_section_eyebrow")
        batch.drop_column("home_leadership_section_enabled")
