"""email_settings — IMAP OAuth2 (Microsoft 365) credentials

Revision ID: 20260529_0022
Revises: 20260528_0021
Create Date: 2026-05-29

Microsoft 365 permanently retired Basic Auth (and App Passwords on
many tenants) for IMAP in 2023. New tenants can't even toggle them on
anymore — the only supported path is OAuth2 client-credentials
("AccessAsApp") against an Entra ID App Registration that's been
granted the ``IMAP.AccessAsApp`` permission and registered with
Exchange Online via ``New-ServicePrincipal``.

This migration adds the four columns the OAuth path needs, all
nullable so existing rows (using a saved App Password) keep working
unchanged. The discriminator column ``imap_auth_method`` defaults to
``'password'`` so previously-saved rows resolve to the old behaviour
without any backfill.

Columns added:

    imap_auth_method                   varchar(16) default 'password'
                                       ('password' | 'oauth2')
    imap_oauth_tenant_id               varchar(64) — Entra ID tenant GUID
    imap_oauth_client_id               varchar(64) — App registration ID
    imap_oauth_client_secret_encrypted text        — Fernet-encrypted secret
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_0022"
down_revision: str = "20260528_0021"
branch_labels = None
depends_on = None


NEW_COLS = (
    ("imap_auth_method", sa.String(16), sa.text("'password'"), False),
    ("imap_oauth_tenant_id", sa.String(64), None, True),
    ("imap_oauth_client_id", sa.String(64), None, True),
    ("imap_oauth_client_secret_encrypted", sa.Text(), None, True),
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
