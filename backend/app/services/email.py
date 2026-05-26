"""Outbound email service.

Builds an SMTP transport from the singleton ``email_settings`` row
(falling back to the matching env vars when the row is empty) and
sends MIME messages on demand. Every send returns an :class:`EmailResult`
so callers can branch on success/failure and store a friendly error
message without exposing tracebacks or credentials.

Used by:

* the admin "Send test email" button (``EmailService.send_test_email``)
* the contact-inbox reply endpoint (``EmailService.send_contact_reply``)
* the public contact-form handler for the best-effort admin notify
  (``EmailService.send_simple``)

Test infrastructure can monkey-patch ``EmailService._send`` to bypass
the network.
"""
from __future__ import annotations

import logging
import smtplib
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.models.cms import ContactMessage
from app.models.email_settings import (
    EmailSetting,
    TEST_STATUS_FAILED,
    TEST_STATUS_SUCCESS,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resolved config + send result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedEmailConfig:
    """Final SMTP config used for one send. Mix of DB row + env fallback."""

    enabled: bool
    host: Optional[str]
    port: int
    username: Optional[str]
    password: Optional[str]
    use_tls: bool
    use_ssl: bool
    from_email: Optional[str]
    from_name: Optional[str]
    reply_to: Optional[str]
    notification_email: Optional[str]
    timeout_seconds: int = 20
    # True when every field above was sourced from env (DB row empty).
    env_fallback_active: bool = False

    @property
    def has_password(self) -> bool:
        return bool(self.password)

    @property
    def is_send_ready(self) -> bool:
        return bool(self.enabled and self.host and self.from_email)


@dataclass(frozen=True)
class EmailResult:
    success: bool
    message: str
    sent_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EmailService:
    """SMTP send helpers built around a resolved config."""

    @staticmethod
    def get_or_create_settings(db: Session) -> EmailSetting:
        setting = db.get(EmailSetting, 1)
        if setting is None:
            setting = EmailSetting(id=1)
            db.add(setting)
            db.flush()
        return setting

    @classmethod
    def get_config(cls, db: Session) -> ResolvedEmailConfig:
        """Merge the DB row with env-var defaults.

        Each field individually falls back: e.g. an admin can set the
        from-address in the DB while leaving the SMTP password in env.
        """
        env = get_settings()
        row = cls.get_or_create_settings(db)

        db_password = decrypt_secret(row.smtp_password_encrypted)
        password = db_password or env.smtp_password

        # ``env_fallback_active`` flips true when the DB row has no
        # transport config of its own. Admin UI surfaces this so the
        # admin understands where the values came from.
        env_fallback_active = not any(
            [row.smtp_host, row.smtp_username, db_password, row.email_from]
        )

        return ResolvedEmailConfig(
            enabled=row.email_enabled,
            host=row.smtp_host or env.smtp_host,
            port=row.smtp_port or env.smtp_port,
            username=row.smtp_username or env.smtp_username,
            password=password,
            use_tls=row.smtp_use_tls,
            use_ssl=row.smtp_use_ssl,
            from_email=row.email_from or env.smtp_from_email,
            from_name=row.email_from_name,
            reply_to=row.email_reply_to,
            notification_email=row.notification_email,
            env_fallback_active=env_fallback_active,
        )

    # ---------------------------------------------------------------
    # Core send
    # ---------------------------------------------------------------

    @classmethod
    def send_simple(
        cls,
        db: Session,
        *,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> EmailResult:
        """Send one message using the resolved config."""
        config = cls.get_config(db)
        return cls._send_with_config(
            config,
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            reply_to_override=reply_to,
        )

    @classmethod
    def send_test_email(cls, db: Session, *, to_email: str) -> EmailResult:
        """Admin "Send test email" button. Stamps last_test_* on the row."""
        config = cls.get_config(db)
        result = cls._send_with_config(
            config,
            to_email=to_email,
            subject="PUG Holding — test email",
            body_text=(
                "This is a test email from your PUG Holding admin panel.\n\n"
                "If you received this, your SMTP configuration is working "
                "correctly."
            ),
            body_html=(
                "<p>This is a test email from your PUG Holding admin panel.</p>"
                "<p>If you received this, your SMTP configuration is working "
                "correctly.</p>"
            ),
        )

        row = cls.get_or_create_settings(db)
        row.last_test_status = (
            TEST_STATUS_SUCCESS if result.success else TEST_STATUS_FAILED
        )
        row.last_test_message = result.message[:1000]
        row.last_test_at = datetime.now(timezone.utc)
        db.flush()
        return result

    @classmethod
    def send_contact_reply(
        cls,
        db: Session,
        *,
        contact_message: ContactMessage,
        reply_body: str,
    ) -> EmailResult:
        """Email an admin-typed reply back to the original contact sender."""
        config = cls.get_config(db)
        original_subject = (contact_message.subject or "your enquiry").strip()
        subject = (
            original_subject
            if original_subject.lower().startswith("re:")
            else f"Re: {original_subject}"
        )

        original_summary = (
            f"\n\n---\nYour original message on "
            f"{contact_message.created_at:%Y-%m-%d %H:%M UTC}:\n"
            f"{contact_message.message.strip()}"
        )
        body_text = f"{reply_body.strip()}{original_summary}\n\n— Paris United Group Holding"

        body_html = (
            f"<div style=\"font-family:Inter,Arial,sans-serif;color:#17382f;"
            f"max-width:600px;margin:0 auto;padding:24px;\">"
            f"<div style=\"white-space:pre-wrap;line-height:1.55;\">"
            f"{_escape(reply_body.strip())}</div>"
            f"<hr style=\"margin:24px 0;border:0;border-top:1px solid #e4e0d6;\" />"
            f"<p style=\"font-size:12px;color:#61736b;margin:0;\">"
            f"Your original message on "
            f"{contact_message.created_at:%Y-%m-%d %H:%M UTC}:</p>"
            f"<blockquote style=\"margin:8px 0 0;padding:0 0 0 12px;"
            f"border-left:2px solid #e4e0d6;color:#61736b;white-space:pre-wrap;"
            f"font-size:13px;\">{_escape(contact_message.message.strip())}</blockquote>"
            f"<p style=\"font-size:12px;color:#61736b;margin-top:24px;\">"
            f"— Paris United Group Holding</p></div>"
        )

        return cls._send_with_config(
            config,
            to_email=contact_message.email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

    # ---------------------------------------------------------------
    # Internals
    # ---------------------------------------------------------------

    @classmethod
    def _send_with_config(
        cls,
        config: ResolvedEmailConfig,
        *,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        reply_to_override: Optional[str] = None,
    ) -> EmailResult:
        if not config.enabled:
            return EmailResult(success=False, message="Email is disabled in the admin configuration.")
        if not config.host:
            return EmailResult(success=False, message="SMTP host is not configured.")
        if not config.from_email:
            return EmailResult(success=False, message="Sender 'from' address is not configured.")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((config.from_name or "", config.from_email))
        msg["To"] = to_email
        reply_to = reply_to_override or config.reply_to
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.set_content(body_text)
        if body_html:
            msg.add_alternative(body_html, subtype="html")

        try:
            cls._send(msg, config)
        except smtplib.SMTPAuthenticationError:
            return EmailResult(
                success=False,
                message="SMTP authentication failed. Please check the username and password.",
            )
        except smtplib.SMTPConnectError:
            return EmailResult(
                success=False,
                message=f"Could not connect to SMTP server {config.host}:{config.port}.",
            )
        except smtplib.SMTPRecipientsRefused:
            return EmailResult(
                success=False,
                message=f"Recipient {to_email} was refused by the SMTP server.",
            )
        except smtplib.SMTPSenderRefused:
            return EmailResult(
                success=False,
                message=f"Sender {config.from_email} was refused by the SMTP server.",
            )
        except ssl.SSLError as exc:
            return EmailResult(
                success=False,
                message=f"TLS/SSL handshake failed: {exc.reason or exc.strerror or 'unknown SSL error'}.",
            )
        except socket.gaierror:
            return EmailResult(
                success=False,
                message=f"DNS lookup failed for SMTP host {config.host}.",
            )
        except (TimeoutError, socket.timeout):
            return EmailResult(
                success=False,
                message=f"SMTP connection to {config.host}:{config.port} timed out.",
            )
        except smtplib.SMTPException as exc:
            logger.warning("SMTP send failed: %s", exc)
            return EmailResult(
                success=False,
                message=f"SMTP error: {exc.__class__.__name__}.",
            )
        except OSError as exc:
            logger.warning("Network error during SMTP send: %s", exc)
            return EmailResult(
                success=False,
                message=f"Network error contacting SMTP server: {exc.strerror or 'unknown'}.",
            )

        return EmailResult(
            success=True,
            message="Email sent successfully.",
            sent_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _send(msg: EmailMessage, config: ResolvedEmailConfig) -> None:
        """Open an SMTP session and deliver one message.

        Kept as its own staticmethod so the test suite can monkey-patch
        it to record the call without opening a real connection.
        """
        ssl_context = ssl.create_default_context()
        if config.use_ssl:
            with smtplib.SMTP_SSL(
                config.host,  # type: ignore[arg-type]
                config.port,
                timeout=config.timeout_seconds,
                context=ssl_context,
            ) as smtp:
                if config.username:
                    smtp.login(config.username, config.password or "")
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(
                config.host,  # type: ignore[arg-type]
                config.port,
                timeout=config.timeout_seconds,
            ) as smtp:
                smtp.ehlo()
                if config.use_tls:
                    smtp.starttls(context=ssl_context)
                    smtp.ehlo()
                if config.username:
                    smtp.login(config.username, config.password or "")
                smtp.send_message(msg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def store_password(setting: EmailSetting, new_password: Optional[str]) -> bool:
    """Persist a new SMTP password.

    Returns True when the encrypted column was updated. A blank or None
    value is treated as "keep existing" — the column is left untouched.
    """
    if new_password is None or not new_password.strip():
        return False
    setting.smtp_password_encrypted = encrypt_secret(new_password)
    return True


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
