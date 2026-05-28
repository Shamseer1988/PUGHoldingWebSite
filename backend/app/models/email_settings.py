"""Email configuration singleton.

The row at id=1 stores admin-edited SMTP settings (host, port, sender
identity, TLS/SSL choice, and the *encrypted* password). It's queried
by :mod:`app.services.email` on every send; missing columns fall back
to the corresponding ``settings.smtp_*`` env values so a fresh install
keeps working without anyone touching the admin page first.

The password column stores a Fernet token produced by
:mod:`app.core.crypto`. It is never returned to the admin UI.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


TEST_STATUS_NEVER = "never"
TEST_STATUS_SUCCESS = "success"
TEST_STATUS_FAILED = "failed"
TEST_STATUSES = (TEST_STATUS_NEVER, TEST_STATUS_SUCCESS, TEST_STATUS_FAILED)


class EmailSetting(Base):
    __tablename__ = "email_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Master switch — disables every outgoing send when False, even
    # when SMTP host etc. are configured.
    email_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # --- SMTP transport ---
    smtp_host: Mapped[Optional[str]] = mapped_column(String(255))
    smtp_port: Mapped[Optional[int]] = mapped_column(Integer)
    smtp_username: Mapped[Optional[str]] = mapped_column(String(255))
    smtp_password_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    smtp_use_tls: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    smtp_use_ssl: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # --- Sender identity / replies ---
    email_from: Mapped[Optional[str]] = mapped_column(String(255))
    email_from_name: Mapped[Optional[str]] = mapped_column(String(255))
    email_reply_to: Mapped[Optional[str]] = mapped_column(String(255))

    # Default destination for the "send test email" button.
    test_email_to: Mapped[Optional[str]] = mapped_column(String(255))

    # Best-effort admin notification on public contact-form submission.
    notification_email: Mapped[Optional[str]] = mapped_column(String(255))

    # --- HR notification destinations (advanced module) -------------
    # Comma-separated list of HR Manager emails CC'd on job approval
    # events. JSON to keep ordering and allow future per-event lists.
    hr_notification_emails: Mapped[Optional[list]] = mapped_column(JSON)
    candidate_email_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    interview_email_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    job_approval_email_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # Phase 11 — master mute for the full offer email stream
    # (approval-requested, approved, issued, accepted, declined, joined).
    offer_email_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    brand_logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    email_footer_text: Mapped[Optional[str]] = mapped_column(Text)

    # --- Last test diagnostic ---
    last_test_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TEST_STATUS_NEVER, server_default=TEST_STATUS_NEVER
    )
    last_test_message: Mapped[Optional[str]] = mapped_column(Text)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # --- IMAP inbound (contact-ticket poller) -----------------------
    # Mirrors the SMTP block above. ``imap_password_encrypted`` is a
    # Fernet token, never returned to the admin UI. Folder fields use
    # IMAP-friendly names (typically ``INBOX``, ``Processed``,
    # ``Errors``). ``imap_create_new_tickets`` is opt-in because a
    # stray newsletter bounce shouldn't mint a ticket by default.
    imap_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    imap_host: Mapped[Optional[str]] = mapped_column(String(255))
    imap_port: Mapped[Optional[int]] = mapped_column(Integer)
    imap_username: Mapped[Optional[str]] = mapped_column(String(255))
    imap_password_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    imap_use_ssl: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    imap_folder: Mapped[str] = mapped_column(
        String(255), nullable=False, default="INBOX", server_default="INBOX"
    )
    imap_processed_folder: Mapped[Optional[str]] = mapped_column(String(255))
    imap_error_folder: Mapped[Optional[str]] = mapped_column(String(255))
    imap_poll_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    imap_create_new_tickets: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    last_imap_test_status: Mapped[str] = mapped_column(
        String(16), nullable=False,
        default=TEST_STATUS_NEVER, server_default=TEST_STATUS_NEVER,
    )
    last_imap_test_message: Mapped[Optional[str]] = mapped_column(Text)
    last_imap_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    updated_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
