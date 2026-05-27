"""contact tickets — ticket_number, thread_token, status machine, threading headers, attachments

Revision ID: 20260527_0015
Revises: 20260527_0014
Create Date: 2026-05-27

First half of the Contact-Us → ticket-support upgrade. All additive:

* ``contact_messages`` gains the columns the ticket flow needs
  (ticket_number, thread_token, status, priority, source, …)
  plus denormalised "last X at" timestamps and Message-ID columns
  for SMTP/IMAP threading.

* ``contact_replies`` gains sender_type, body_html / clean_body_text,
  email Message-ID / In-Reply-To / References headers, and the
  has_attachments flag.

* New table ``contact_reply_attachments`` for inbound email
  attachments and future admin uploads.

Existing rows are backfilled:
  ticket_number  → "PUG-CNT-LEGACY-{id:06d}"  (clearly marked so
                   support knows these predate the feature)
  thread_token   → secrets.token_urlsafe(24)
  status         → derived from is_archived / is_replied booleans
  sender_type    → 'customer' if direction='inbound' else 'admin'
  last_message_at → max of related-reply created_at, else
                    contact_messages.created_at
"""
from __future__ import annotations

import secrets

import sqlalchemy as sa
from alembic import op


revision: str = "20260527_0015"
down_revision: str = "20260527_0014"
branch_labels = None
depends_on = None


CONTACT_MESSAGES_NEW_COLS = (
    ("ticket_number", sa.String(40), True, None),  # backfilled, then NOT NULL
    ("thread_token", sa.String(80), True, None),
    ("status", sa.String(24), True, None),
    ("priority", sa.String(16), True, None),
    ("source", sa.String(32), True, None),
    ("company_name", sa.String(255), True, None),
    ("assigned_to_user_id", sa.Integer(), True, None),
    ("last_message_at", sa.DateTime(timezone=True), True, None),
    ("last_customer_reply_at", sa.DateTime(timezone=True), True, None),
    ("last_admin_reply_at", sa.DateTime(timezone=True), True, None),
    ("completed_at", sa.DateTime(timezone=True), True, None),
    ("reopened_at", sa.DateTime(timezone=True), True, None),
    # 998 = RFC 5322 max line length for a header; Message-ID lives there.
    ("inbound_email_message_id", sa.String(998), True, None),
    ("outbound_email_message_id", sa.String(998), True, None),
)

CONTACT_REPLIES_NEW_COLS = (
    ("sender_type", sa.String(16), True, None),  # customer | admin | system
    ("body_html", sa.Text(), True, None),
    ("clean_body_text", sa.Text(), True, None),
    ("email_message_id", sa.String(998), True, None),
    ("in_reply_to", sa.String(998), True, None),
    ("references_header", sa.Text(), True, None),
    ("has_attachments", sa.Boolean(), False, "false"),
)


def _add_cols(table: str, cols: tuple) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns(table)}
    with op.batch_alter_table(table) as batch:
        for name, type_, nullable, server_default in cols:
            if name in existing:
                continue
            kwargs: dict = {"nullable": nullable}
            if server_default is not None:
                kwargs["server_default"] = server_default
            batch.add_column(sa.Column(name, type_, **kwargs))


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. Schema additions -------------------------------------------------
    _add_cols("contact_messages", CONTACT_MESSAGES_NEW_COLS)
    _add_cols("contact_replies", CONTACT_REPLIES_NEW_COLS)

    # --- 2. New attachments table -------------------------------------------
    inspector = sa.inspect(bind)
    if "contact_reply_attachments" not in inspector.get_table_names():
        op.create_table(
            "contact_reply_attachments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "contact_reply_id",
                sa.Integer(),
                sa.ForeignKey("contact_replies.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("original_filename", sa.String(500), nullable=False),
            sa.Column("stored_filename", sa.String(500), nullable=False),
            sa.Column("file_path", sa.String(1000), nullable=False),
            sa.Column("mime_type", sa.String(160), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column(
                "uploaded_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    # --- 3. Backfill existing contact_messages ------------------------------
    # Generate ticket_number + thread_token + denormalised timestamps so
    # every row has the new shape immediately. We don't fail on
    # already-populated columns (re-runnable migration).
    rows = bind.execute(
        sa.text(
            "SELECT id, is_archived, is_replied, created_at, ticket_number, "
            "thread_token, status FROM contact_messages ORDER BY id"
        )
    ).fetchall()
    for row in rows:
        msg_id = row[0]
        is_archived = bool(row[1])
        is_replied = bool(row[2])
        existing_ticket = row[4]
        existing_token = row[5]
        existing_status = row[6]

        ticket = existing_ticket or f"PUG-CNT-LEGACY-{msg_id:06d}"
        token = existing_token or secrets.token_urlsafe(24)
        if existing_status:
            status = existing_status
        elif is_archived:
            status = "archived"
        elif is_replied:
            status = "completed"
        else:
            status = "new"

        bind.execute(
            sa.text(
                "UPDATE contact_messages "
                "SET ticket_number = :ticket, "
                "    thread_token = :token, "
                "    status = COALESCE(status, :status), "
                "    priority = COALESCE(priority, 'normal'), "
                "    source = COALESCE(source, 'website_contact'), "
                "    last_message_at = COALESCE(last_message_at, created_at) "
                "WHERE id = :id"
            ),
            {
                "ticket": ticket,
                "token": token,
                "status": status,
                "id": msg_id,
            },
        )

    # --- 4. Backfill contact_replies sender_type + has_attachments default --
    bind.execute(
        sa.text(
            "UPDATE contact_replies "
            "SET sender_type = CASE WHEN direction = 'inbound' "
            "                       THEN 'customer' ELSE 'admin' END "
            "WHERE sender_type IS NULL"
        )
    )

    # --- 5. Refresh last_*_at on contact_messages from contact_replies ------
    # last_customer_reply_at = newest inbound reply (excluding the original
    # submission which is direction=inbound created at the same instant).
    # last_admin_reply_at = newest outbound reply.
    bind.execute(
        sa.text(
            "UPDATE contact_messages cm SET "
            "  last_customer_reply_at = ("
            "    SELECT MAX(cr.created_at) FROM contact_replies cr "
            "    WHERE cr.contact_message_id = cm.id AND cr.direction = 'inbound'"
            "  ), "
            "  last_admin_reply_at = ("
            "    SELECT MAX(cr.created_at) FROM contact_replies cr "
            "    WHERE cr.contact_message_id = cm.id AND cr.direction = 'outbound'"
            "  ) "
            "WHERE EXISTS (SELECT 1 FROM contact_replies cr "
            "              WHERE cr.contact_message_id = cm.id)"
        )
    )

    # --- 6. Add unique indexes (now that every row has values) --------------
    if bind.dialect.name != "sqlite":
        with op.batch_alter_table("contact_messages") as batch:
            try:
                batch.alter_column(
                    "ticket_number", existing_type=sa.String(40), nullable=False
                )
                batch.alter_column(
                    "thread_token", existing_type=sa.String(80), nullable=False
                )
                batch.alter_column(
                    "status", existing_type=sa.String(24), nullable=False
                )
                batch.alter_column(
                    "priority", existing_type=sa.String(16), nullable=False
                )
                batch.alter_column(
                    "source", existing_type=sa.String(32), nullable=False
                )
                batch.alter_column(
                    "last_message_at",
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False,
                )
            except Exception:
                pass

    for ix_name, table, cols, unique in (
        ("ix_contact_messages_ticket_number", "contact_messages", ["ticket_number"], True),
        ("ix_contact_messages_thread_token", "contact_messages", ["thread_token"], True),
        ("ix_contact_messages_status", "contact_messages", ["status"], False),
        ("ix_contact_messages_last_message_at", "contact_messages", ["last_message_at"], False),
        ("ix_contact_messages_assigned_to", "contact_messages", ["assigned_to_user_id"], False),
        ("ix_contact_replies_email_message_id", "contact_replies", ["email_message_id"], False),
        ("ix_contact_replies_sender_type", "contact_replies", ["sender_type"], False),
    ):
        try:
            op.create_index(ix_name, table, cols, unique=unique)
        except Exception:
            pass

    if bind.dialect.name != "sqlite":
        try:
            op.create_foreign_key(
                "fk_contact_messages_assigned_to",
                "contact_messages",
                "users",
                ["assigned_to_user_id"],
                ["id"],
                ondelete="SET NULL",
            )
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        try:
            op.drop_constraint(
                "fk_contact_messages_assigned_to",
                "contact_messages",
                type_="foreignkey",
            )
        except Exception:
            pass
    for ix in (
        "ix_contact_messages_ticket_number",
        "ix_contact_messages_thread_token",
        "ix_contact_messages_status",
        "ix_contact_messages_last_message_at",
        "ix_contact_messages_assigned_to",
        "ix_contact_replies_email_message_id",
        "ix_contact_replies_sender_type",
    ):
        try:
            op.drop_index(ix)
        except Exception:
            pass
    try:
        op.drop_table("contact_reply_attachments")
    except Exception:
        pass
    with op.batch_alter_table("contact_replies") as batch:
        for name, _, _, _ in CONTACT_REPLIES_NEW_COLS:
            try:
                batch.drop_column(name)
            except Exception:
                pass
    with op.batch_alter_table("contact_messages") as batch:
        for name, _, _, _ in CONTACT_MESSAGES_NEW_COLS:
            try:
                batch.drop_column(name)
            except Exception:
                pass
