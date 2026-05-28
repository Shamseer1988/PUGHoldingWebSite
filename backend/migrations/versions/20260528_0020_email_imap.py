"""email_settings — IMAP inbound columns + test diagnostics

Revision ID: 20260528_0020
Revises: 20260528_0019
Create Date: 2026-05-28

The IMAP inbound poller was configured exclusively through env vars
(``CONTACT_INBOUND_*``). That's fine for the original ship but
forces an env edit + uvicorn restart whenever an admin rotates
credentials or onboards a new support mailbox. Move the same
settings to the existing ``email_settings`` singleton so the admin
can manage SMTP + IMAP from one Email Configuration page, with a
"Test connection" button for IMAP that mirrors the SMTP test.

Columns added (all nullable so an existing row is valid as soon as
the migration runs; the env fallback in EmailService still wins
for any column left NULL):

    imap_enabled              bool, default false
    imap_host                 varchar(255)
    imap_port                 int (993 by default in the API)
    imap_username             varchar(255)
    imap_password_encrypted   text (Fernet token, same as SMTP)
    imap_use_ssl              bool, default true
    imap_folder               varchar(255) default 'INBOX'
    imap_processed_folder     varchar(255)
    imap_error_folder         varchar(255)
    imap_poll_interval_minutes int default 5
    imap_create_new_tickets   bool default false
    last_imap_test_status     varchar(16) default 'never'
    last_imap_test_message    text
    last_imap_test_at         timestamptz
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260528_0020"
down_revision: str = "20260528_0019"
branch_labels = None
depends_on = None


NEW_COLS = (
    ("imap_enabled", sa.Boolean(), sa.false(), False),
    ("imap_host", sa.String(255), None, True),
    ("imap_port", sa.Integer(), None, True),
    ("imap_username", sa.String(255), None, True),
    ("imap_password_encrypted", sa.Text(), None, True),
    ("imap_use_ssl", sa.Boolean(), sa.true(), False),
    ("imap_folder", sa.String(255), sa.text("'INBOX'"), False),
    ("imap_processed_folder", sa.String(255), None, True),
    ("imap_error_folder", sa.String(255), None, True),
    ("imap_poll_interval_minutes", sa.Integer(), sa.text("5"), False),
    ("imap_create_new_tickets", sa.Boolean(), sa.false(), False),
    ("last_imap_test_status", sa.String(16), sa.text("'never'"), False),
    ("last_imap_test_message", sa.Text(), None, True),
    ("last_imap_test_at", sa.DateTime(timezone=True), None, True),
)


def upgrade() -> None:
    bind = op.get_bind()
    # Defensive — skip columns that somehow already exist (a partial
    # run, a dev DB with a hand-applied patch). Doing this with the
    # information schema means re-running the migration is safe.
    existing_cols = {
        row[0]
        for row in bind.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'email_settings'"
            )
        ).all()
    }
    for name, type_, default, nullable in NEW_COLS:
        if name in existing_cols:
            continue
        op.add_column(
            "email_settings",
            sa.Column(
                name,
                type_,
                server_default=default,
                nullable=nullable,
            ),
        )


def downgrade() -> None:
    for name, _t, _d, _n in NEW_COLS:
        op.drop_column("email_settings", name)
