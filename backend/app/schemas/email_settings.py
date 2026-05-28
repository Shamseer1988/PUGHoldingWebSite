"""Pydantic schemas for the Email Configuration admin page.

Important: the SMTP password is never serialised. ``EmailSettingsRead``
exposes a boolean ``has_smtp_password`` and the API accepts a write-
only ``smtp_password`` on update — blank means "keep the existing
value", non-blank means "encrypt and store this new value".
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.email_settings import TEST_STATUSES


class EmailSettingsRead(BaseModel):
    """Email config as the admin UI sees it. Never includes passwords."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email_enabled: bool
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    # Diagnostic flag — true when either DB column or env has a password set.
    has_smtp_password: bool = False
    smtp_use_tls: bool
    smtp_use_ssl: bool
    email_from: Optional[str] = None
    email_from_name: Optional[str] = None
    email_reply_to: Optional[str] = None
    test_email_to: Optional[str] = None
    notification_email: Optional[str] = None
    # HR notification destinations + feature flags (advanced module)
    hr_notification_emails: Optional[List[str]] = None
    candidate_email_enabled: bool = True
    interview_email_enabled: bool = True
    job_approval_email_enabled: bool = True
    brand_logo_url: Optional[str] = None
    email_footer_text: Optional[str] = None
    last_test_status: str
    last_test_message: Optional[str] = None
    last_test_at: Optional[datetime] = None
    updated_by_id: Optional[int] = None
    updated_at: Optional[datetime] = None
    # Highlights env-only fallback to the admin so they know if the row
    # itself is empty.
    env_fallback_active: bool = False

    # --- IMAP inbound (contact-ticket poller) -----------------------
    imap_enabled: bool = False
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    has_imap_password: bool = False
    imap_use_ssl: bool = True
    imap_folder: Optional[str] = None
    imap_processed_folder: Optional[str] = None
    imap_error_folder: Optional[str] = None
    imap_poll_interval_minutes: Optional[int] = None
    imap_create_new_tickets: bool = False
    last_imap_test_status: str = "never"
    last_imap_test_message: Optional[str] = None
    last_imap_test_at: Optional[datetime] = None
    imap_env_fallback_active: bool = False


class EmailSettingsUpdate(BaseModel):
    """All fields optional — PATCH semantics.

    ``smtp_password`` blank or missing keeps the existing encrypted
    value untouched. Setting it to a non-blank string re-encrypts and
    overwrites.
    """

    email_enabled: Optional[bool] = None
    smtp_host: Optional[str] = Field(default=None, max_length=255)
    smtp_port: Optional[int] = Field(default=None, ge=1, le=65535)
    smtp_username: Optional[str] = Field(default=None, max_length=255)
    smtp_password: Optional[str] = Field(default=None, max_length=500)
    smtp_use_tls: Optional[bool] = None
    smtp_use_ssl: Optional[bool] = None
    email_from: Optional[EmailStr] = None
    email_from_name: Optional[str] = Field(default=None, max_length=255)
    email_reply_to: Optional[EmailStr] = None
    test_email_to: Optional[EmailStr] = None
    notification_email: Optional[EmailStr] = None

    # HR notification fields
    hr_notification_emails: Optional[List[EmailStr]] = None
    candidate_email_enabled: Optional[bool] = None
    interview_email_enabled: Optional[bool] = None
    job_approval_email_enabled: Optional[bool] = None
    brand_logo_url: Optional[str] = Field(default=None, max_length=500)
    email_footer_text: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("smtp_host", "smtp_username", "email_from_name", mode="before")
    @classmethod
    def _strip_str(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    # ----- IMAP fields (mirror SMTP shape) -----
    imap_enabled: Optional[bool] = None
    imap_host: Optional[str] = Field(default=None, max_length=255)
    imap_port: Optional[int] = Field(default=None, ge=1, le=65535)
    imap_username: Optional[str] = Field(default=None, max_length=255)
    imap_password: Optional[str] = Field(default=None, max_length=500)
    imap_use_ssl: Optional[bool] = None
    imap_folder: Optional[str] = Field(default=None, max_length=255)
    imap_processed_folder: Optional[str] = Field(default=None, max_length=255)
    imap_error_folder: Optional[str] = Field(default=None, max_length=255)
    imap_poll_interval_minutes: Optional[int] = Field(
        default=None, ge=1, le=60 * 24
    )
    imap_create_new_tickets: Optional[bool] = None

    @field_validator(
        "imap_host",
        "imap_username",
        "imap_folder",
        "imap_processed_folder",
        "imap_error_folder",
        mode="before",
    )
    @classmethod
    def _strip_imap(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class EmailTestRequest(BaseModel):
    to_email: EmailStr


class EmailTestResult(BaseModel):
    success: bool
    message: str
    sent_at: Optional[datetime] = None


class ImapTestRequest(BaseModel):
    """Optional password override — lets the admin verify a freshly-
    typed password without saving it first (so they can't overwrite a
    working password with a bad one). Blank/missing means "use what's
    already in the DB / env"."""

    imap_password: Optional[str] = Field(default=None, max_length=500)


class ImapTestResult(BaseModel):
    success: bool
    message: str
    folders_sampled: List[str] = []
    server_greeting: Optional[str] = None
    selected_message_count: Optional[int] = None
    tested_at: Optional[datetime] = None


# Validate status when reading from the DB so callers don't pass garbage.
_VALID = set(TEST_STATUSES)
