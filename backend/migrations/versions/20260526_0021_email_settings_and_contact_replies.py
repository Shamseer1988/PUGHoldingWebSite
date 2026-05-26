"""Add email_settings singleton and contact_replies thread.

Two new tables:

* ``email_settings`` (singleton at id=1) — admin-edited SMTP config.
  The ``smtp_password_encrypted`` column holds a Fernet token produced
  by :mod:`app.core.crypto`; the plaintext password is never stored or
  returned through any API.

* ``contact_replies`` — every message in a contact-inbox thread,
  including the original inbound submission. Lets the admin UI render
  the conversation as chat bubbles and tracks per-reply email send
  status (pending / sent / failed) so failed replies can be retried.

Revision ID: 20260526_0021
Revises: 20260525_0020
Create Date: 2026-05-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260526_0021"
down_revision: Union[str, None] = "20260525_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "email_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("smtp_host", sa.String(255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=True),
        sa.Column("smtp_username", sa.String(255), nullable=True),
        sa.Column("smtp_password_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "smtp_use_tls",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "smtp_use_ssl",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("email_from", sa.String(255), nullable=True),
        sa.Column("email_from_name", sa.String(255), nullable=True),
        sa.Column("email_reply_to", sa.String(255), nullable=True),
        sa.Column("test_email_to", sa.String(255), nullable=True),
        sa.Column("notification_email", sa.String(255), nullable=True),
        sa.Column(
            "last_test_status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'never'"),
        ),
        sa.Column("last_test_message", sa.Text(), nullable=True),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
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

    op.create_table(
        "contact_replies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "contact_message_id",
            sa.Integer(),
            sa.ForeignKey("contact_messages.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column(
            "admin_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sender_name", sa.String(255), nullable=True),
        sa.Column("sender_email", sa.String(255), nullable=True),
        sa.Column("recipient_email", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "email_status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("contact_replies")
    op.drop_table("email_settings")
