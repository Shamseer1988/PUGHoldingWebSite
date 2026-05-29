"""email_settings — IMAP UID watermark for M365 robustness

Revision ID: 20260529_0023
Revises: 20260529_0022
Create Date: 2026-05-29

The poller was designed to skip already-inspected messages by
stamping a custom IMAP keyword (``$PUG-Inspected``) — this kept
non-ticket mail in the same Read/Unread state as the user's Outlook
left it. Microsoft 365 silently rejects custom flag keywords, so on
M365 we'd been falling back to a ``UNSEEN`` search. That fallback is
brittle: any Outlook / OWA client with the mailbox open auto-marks
incoming mail as ``\\Seen`` (via the Reading Pane preview) before
the next 5-minute poll runs, so the poller's ``UNSEEN`` search comes
back empty and customer replies vanish.

This migration adds the two columns the new fallback path needs.
The poller (next commit) tracks the highest IMAP UID it has
inspected per folder and resumes from there — UIDs are server-
assigned and immutable, so humans / Outlook clients can't race the
search anymore. ``UIDVALIDITY`` is captured alongside so a rare
folder reset (legal per RFC 3501) discards the stale watermark
rather than silently skipping new mail forever.

Columns added (nullable so existing rows + the env-only fallback
keep working until the first M365 poll runs):

    imap_last_seen_uid              BIGINT NULL
    imap_last_seen_uid_validity     BIGINT NULL
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_0023"
down_revision: str = "20260529_0022"
branch_labels = None
depends_on = None


NEW_COLS = (
    ("imap_last_seen_uid", sa.BigInteger(), None, True),
    ("imap_last_seen_uid_validity", sa.BigInteger(), None, True),
)


def upgrade() -> None:
    bind = op.get_bind()
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
            sa.Column(name, type_, server_default=default, nullable=nullable),
        )


def downgrade() -> None:
    for name, _t, _d, _n in NEW_COLS:
        op.drop_column("email_settings", name)
