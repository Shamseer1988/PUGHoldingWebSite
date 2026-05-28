"""Contact-ticket IMAP inbound polling.

When a customer replies to an outbound ticket email, the reply lands
in the configured support mailbox. This module pulls those replies via
IMAP, matches each one back to its originating
:class:`app.models.cms.ContactMessage`, and writes a new
:class:`app.models.cms.ContactReply` (direction=``inbound``,
sender_type=``customer``) — flipping the ticket back to
``pending_admin`` so the inbox UI re-surfaces it.

Why a polling design (not push):

* IMAP IDLE would give near-instant delivery but ties up a connection
  per worker. The contact inbox volume is low — a 5-minute poll loop
  is plenty and falls back gracefully when the mail provider is down.
* APScheduler already runs in-process for the report digest job, so
  registering one more interval trigger is cheap.

Matching strategy — tried in order, first hit wins:

  1. ``X-PUG-Contact-Thread`` custom header (our outbound stamps it).
  2. ``In-Reply-To`` header parsed via
     :func:`app.services.contact_threading.parse_thread_token_from_message_id`.
  3. Every ``References`` Message-ID parsed the same way.
  4. ``[PUG-CNT-…]`` ticket bracket in the ``Subject``.
  5. (Optional) Fuzzy match on sender email + recent ticket.

Unmatched messages can either be dropped (default) or used to open a
brand new ticket (``CONTACT_INBOUND_CREATE_NEW=true``). The default is
defensive because we don't want a stray newsletter bounce minting a
ticket.

Idempotency: every processed Message-ID is recorded on the inserted
:class:`ContactReply` row, and the poller checks ``WHERE
email_message_id = …`` before inserting — so even if the IMAP server
hands us the same message twice (we crashed mid-flag, the operator
re-ran the sync) we never double-thread.
"""
from __future__ import annotations

import email
import email.message
import email.policy
import email.utils
import imaplib
import logging
import re
import socket
import ssl
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.models.cms import (
    CONTACT_STATUS_OPEN,
    CONTACT_STATUS_PENDING_ADMIN,
    ContactMessage,
    ContactReply,
    ContactReplyAttachment,
    REPLY_STATUS_RECEIVED,
    SENDER_CUSTOMER,
)
from app.models.email_settings import EmailSetting
from app.services.contact_threading import (
    THREAD_HEADER_NAME,
    extract_ticket_from_subject,
    parse_thread_token_from_message_id,
)


# ---------------------------------------------------------------------------
# Resolved config — merges DB row with env defaults
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedImapConfig:
    """Effective IMAP settings for a single poll cycle.

    DB-backed columns on ``email_settings`` win when set; otherwise we
    fall back to the env vars from ``app.core.config.Settings`` so an
    existing install that ran on env-only config keeps working until
    the admin opens Email Configuration and saves once.
    """

    enabled: bool
    host: Optional[str]
    port: int
    username: Optional[str]
    password: Optional[str]
    use_ssl: bool
    folder: str
    processed_folder: Optional[str]
    error_folder: Optional[str]
    poll_interval_minutes: int
    create_new_tickets: bool

    @property
    def is_ready(self) -> bool:
        return bool(self.enabled and self.host and self.username and self.password)

    @property
    def is_complete(self) -> bool:
        """Same as ``is_ready`` but ignores the enabled flag — useful
        for the test endpoint which lets the admin verify creds before
        flipping the master switch."""
        return bool(self.host and self.username and self.password)


def resolve_imap_config(db: Session) -> ResolvedImapConfig:
    """Build the IMAP config the poller + test endpoint share."""
    env = get_settings()
    row = db.get(EmailSetting, 1)
    db_pwd = (
        decrypt_secret(row.imap_password_encrypted)
        if row and row.imap_password_encrypted
        else None
    )
    return ResolvedImapConfig(
        enabled=(
            row.imap_enabled
            if row and row.imap_enabled
            else bool(env.contact_inbound_enabled)
        ),
        host=(row.imap_host if row else None) or env.contact_inbound_host,
        port=(row.imap_port if row else None) or env.contact_inbound_port or 993,
        username=(row.imap_username if row else None)
        or env.contact_inbound_username,
        password=db_pwd or env.contact_inbound_password,
        use_ssl=(
            row.imap_use_ssl
            if row is not None
            else bool(env.contact_inbound_use_ssl)
        ),
        folder=(row.imap_folder if row else None)
        or env.contact_inbound_folder
        or "INBOX",
        processed_folder=(
            (row.imap_processed_folder if row else None)
            or env.contact_inbound_processed_folder
        ),
        error_folder=(row.imap_error_folder if row else None)
        or env.contact_inbound_error_folder,
        poll_interval_minutes=(
            row.imap_poll_interval_minutes if row else None
        )
        or env.contact_inbound_poll_interval_minutes
        or 5,
        create_new_tickets=(
            row.imap_create_new_tickets
            if row and row.imap_create_new_tickets
            else _create_new_tickets_env()
        ),
    )


def _create_new_tickets_env() -> bool:
    """Honour ``CONTACT_INBOUND_CREATE_NEW`` (defaults off)."""
    import os

    return os.getenv("CONTACT_INBOUND_CREATE_NEW", "false").lower() in {
        "1",
        "true",
        "yes",
    }

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class InboundReplyOutcome:
    """One processed message — used by tests + the admin sync response."""

    uid: str
    message_id: Optional[str]
    matched_ticket: Optional[str] = None
    matched_via: Optional[str] = None
    reply_id: Optional[int] = None
    attachments_saved: int = 0
    skipped_reason: Optional[str] = None
    error: Optional[str] = None


@dataclass
class InboundPollSummary:
    """End-of-poll roll-up — what the admin sees on the sync endpoint."""

    enabled: bool
    fetched: int = 0
    processed: int = 0
    matched: int = 0
    new_tickets: int = 0
    skipped: int = 0
    errors: int = 0
    outcomes: List[InboundReplyOutcome] = field(default_factory=list)
    error: Optional[str] = None
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    finished_at: Optional[datetime] = None

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "fetched": self.fetched,
            "processed": self.processed,
            "matched": self.matched,
            "new_tickets": self.new_tickets,
            "skipped": self.skipped,
            "errors": self.errors,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "finished_at": (
                self.finished_at.isoformat() if self.finished_at else None
            ),
        }


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def poll_inbox(db: Session, *, limit: int = 50) -> InboundPollSummary:
    """Pull up to ``limit`` UNSEEN messages and thread them.

    Always returns a summary — IMAP / network failures populate the
    ``error`` field rather than raising so the scheduled job + the
    admin "Check now" endpoint can surface a friendly message instead
    of a 500.
    """
    config = resolve_imap_config(db)
    summary = InboundPollSummary(enabled=config.enabled)
    if not summary.enabled:
        summary.error = (
            "IMAP inbound is disabled. Toggle it on in Email Configuration "
            "→ IMAP inbox (or set CONTACT_INBOUND_ENABLED=true)."
        )
        summary.finished_at = datetime.now(timezone.utc)
        return summary
    if not config.is_ready:
        missing = []
        if not config.host:
            missing.append("host")
        if not config.username:
            missing.append("username")
        if not config.password:
            missing.append("password")
        summary.error = (
            "IMAP inbound is enabled but " + ", ".join(missing) + " is missing. "
            "Open Email Configuration → IMAP inbox to set them."
        )
        summary.finished_at = datetime.now(timezone.utc)
        return summary

    try:
        client = _connect(config)
    except _ImapAuthError as exc:
        summary.error = str(exc)
        summary.finished_at = datetime.now(timezone.utc)
        return summary
    except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
        summary.error = _friendly_connect_error(exc, config)
        summary.finished_at = datetime.now(timezone.utc)
        logger.exception("Contact-inbox IMAP connect failed")
        return summary

    try:
        try:
            _select_folder(client, config.folder)
        except imaplib.IMAP4.error as exc:
            summary.error = (
                f"Could not select folder '{config.folder}': {exc}. "
                f"Check the folder name in Email Configuration."
            )
            summary.finished_at = datetime.now(timezone.utc)
            return summary

        uids = _search_unseen(client, limit)
        summary.fetched = len(uids)
        for uid in uids:
            outcome = _process_one(db, client, uid, config)
            summary.outcomes.append(outcome)
            if outcome.error:
                summary.errors += 1
            elif outcome.skipped_reason:
                summary.skipped += 1
            else:
                summary.processed += 1
                if outcome.matched_ticket:
                    summary.matched += 1
                elif outcome.reply_id is not None:
                    # Reply was written but no matched ticket means we
                    # opened a brand-new conversation for it.
                    summary.new_tickets += 1
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            client.logout()
        except Exception:  # noqa: BLE001
            pass

    summary.finished_at = datetime.now(timezone.utc)
    return summary


# ---------------------------------------------------------------------------
# Test connection — used by the Email Configuration admin page
# ---------------------------------------------------------------------------


@dataclass
class ImapTestOutcome:
    """Diagnostic returned by ``test_imap_connection``."""

    success: bool
    message: str
    folders_sampled: List[str] = field(default_factory=list)
    server_greeting: Optional[str] = None
    selected_message_count: Optional[int] = None
    tested_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


def test_imap_connection(
    db: Session,
    *,
    override_password: Optional[str] = None,
) -> ImapTestOutcome:
    """Validate the saved IMAP config by opening a real connection.

    Runs through the same steps the poller does — connect, login,
    SELECT folder, optional LIST so the admin sees a few sibling
    folder names for context — but never fetches a message.

    Accepts an ``override_password`` so the admin can validate
    *just-typed* credentials before saving them (so they don't
    overwrite a working password with a bad one).
    """
    config = resolve_imap_config(db)
    if override_password is not None and override_password.strip():
        # Swap the password while keeping the rest of the resolved
        # config (host/port/SSL/folder).
        config = ResolvedImapConfig(
            enabled=True,
            host=config.host,
            port=config.port,
            username=config.username,
            password=override_password,
            use_ssl=config.use_ssl,
            folder=config.folder,
            processed_folder=config.processed_folder,
            error_folder=config.error_folder,
            poll_interval_minutes=config.poll_interval_minutes,
            create_new_tickets=config.create_new_tickets,
        )

    if not config.is_complete:
        missing = []
        if not config.host:
            missing.append("host")
        if not config.username:
            missing.append("username")
        if not config.password:
            missing.append("password")
        return ImapTestOutcome(
            success=False,
            message=(
                "Fill in " + ", ".join(missing) + " before testing the "
                "connection."
            ),
        )

    try:
        client = _connect(config)
    except _ImapAuthError as exc:
        return ImapTestOutcome(success=False, message=str(exc))
    except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
        return ImapTestOutcome(
            success=False, message=_friendly_connect_error(exc, config)
        )

    folders: List[str] = []
    try:
        try:
            status, count = _select_folder_for_test(client, config.folder)
        except imaplib.IMAP4.error as exc:
            try:
                _, listed = client.list()
                folders = _decode_folder_list(listed or [])
            except Exception:  # noqa: BLE001
                pass
            return ImapTestOutcome(
                success=False,
                message=(
                    f"Connected but could not select '{config.folder}': "
                    f"{exc}. {('Available folders: ' + ', '.join(folders[:8])) if folders else 'List folders failed too.'}"
                ),
                folders_sampled=folders[:12],
            )

        # Best-effort listing for context (Outlook gives a long tree).
        try:
            _, listed = client.list()
            folders = _decode_folder_list(listed or [])
        except Exception:  # noqa: BLE001
            pass

        greeting = (
            client.welcome.decode("ascii", errors="replace")
            if hasattr(client, "welcome") and client.welcome
            else None
        )
        return ImapTestOutcome(
            success=True,
            message=(
                f"Connection OK — {config.username} signed in to "
                f"{config.host}:{config.port}, '{config.folder}' contains "
                f"{count} message(s)."
            ),
            folders_sampled=folders[:12],
            server_greeting=greeting,
            selected_message_count=count,
        )
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            client.logout()
        except Exception:  # noqa: BLE001
            pass


def _select_folder_for_test(
    client: imaplib.IMAP4, folder: str
) -> Tuple[str, int]:
    status, data = client.select(folder, readonly=True)
    if status != "OK":
        raise imaplib.IMAP4.error(
            f"SELECT failed for folder {folder!r}: {data!r}"
        )
    count = 0
    if data and data[0]:
        try:
            count = int(data[0])
        except (TypeError, ValueError):
            count = 0
    return status, count


def _decode_folder_list(rows: list) -> List[str]:
    out: List[str] = []
    for row in rows:
        if row is None:
            continue
        line = (
            row.decode("utf-8", errors="replace")
            if isinstance(row, (bytes, bytearray))
            else str(row)
        )
        # ``(\HasNoChildren) "/" "INBOX"`` — peel out the trailing quoted name.
        m = re.search(r'"([^"]+)"\s*$', line)
        if m:
            out.append(m.group(1))
        else:
            parts = line.rsplit(" ", 1)
            if len(parts) == 2 and parts[1]:
                out.append(parts[1].strip('"'))
    return out


# Custom error class so callers can distinguish auth failures from
# generic IMAP4.error exceptions for friendlier messaging.
class _ImapAuthError(Exception):
    pass


def _friendly_connect_error(
    exc: Exception, config: "ResolvedImapConfig"
) -> str:
    """Translate raw imaplib/socket errors into something an admin
    can actually act on."""
    raw = str(exc).strip() or exc.__class__.__name__
    lower = raw.lower()
    if isinstance(exc, socket.gaierror) or "name or service not known" in lower:
        return (
            f"DNS lookup failed for {config.host!r}. Check the host name "
            f"in Email Configuration."
        )
    if isinstance(exc, ConnectionRefusedError) or "refused" in lower:
        return (
            f"Connection refused to {config.host}:{config.port}. The server "
            f"is reachable but not accepting IMAP on that port. Common "
            f"ports: 993 (SSL) or 143 (plain/STARTTLS)."
        )
    if isinstance(exc, ssl.SSLError):
        return (
            f"TLS handshake failed against {config.host}:{config.port}. "
            f"Either the server uses STARTTLS on a plain port (set "
            f"'Use SSL' = off + port 143) or it's serving a bad "
            f"certificate. Raw: {raw}"
        )
    if isinstance(exc, socket.timeout) or "timed out" in lower:
        return (
            f"Timed out connecting to {config.host}:{config.port}. "
            f"Check that the host/port is correct and the network "
            f"allows outbound IMAP."
        )
    return f"IMAP connect failed: {raw}"


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def _connect(config: ResolvedImapConfig) -> imaplib.IMAP4:
    """Open an authenticated IMAP4 / IMAP4_SSL connection.

    Returns the client positioned at the AUTH state — the caller still
    needs to SELECT a folder. Auth failures raise ``_ImapAuthError``
    with a provider-aware message; transport failures keep their
    native exception so the friendly-error mapper can format them.
    """
    host = config.host or ""
    port = config.port
    if config.use_ssl:
        client: imaplib.IMAP4 = imaplib.IMAP4_SSL(
            host, port, timeout=30, ssl_context=ssl.create_default_context()
        )
    else:
        client = imaplib.IMAP4(host, port, timeout=30)
        # STARTTLS upgrade for non-implicit-TLS providers (e.g. on
        # corporate Exchange).
        try:
            client.starttls(ssl.create_default_context())
        except imaplib.IMAP4.error:
            logger.warning(
                "IMAP STARTTLS not advertised by %s:%s — proceeding plaintext",
                host,
                port,
            )

    try:
        client.login(config.username or "", config.password or "")
    except imaplib.IMAP4.error as exc:
        raw = str(exc)
        lower = raw.lower()
        # Microsoft 365 in particular returns
        # "AUTHENTICATE failed." when Basic Auth has been disabled at
        # the tenant level — most operators won't know what that
        # cryptic message means.
        if "outlook.office" in (host or "").lower() or "office365" in lower:
            raise _ImapAuthError(
                "Microsoft 365 rejected the credentials. Microsoft has "
                "disabled Basic Auth for most tenants. Either: (1) "
                "enable MFA on this mailbox and use a 16-character "
                "App Password instead of the regular password, or (2) "
                "ask your tenant admin to run "
                "`Set-CASMailbox -ImapEnabled $true` for this mailbox "
                "+ allow Authenticated SMTP. Server said: " + raw
            )
        if "authenticate" in lower or "authentication" in lower or "login" in lower:
            raise _ImapAuthError(
                f"IMAP login refused by {host}: {raw}. Check the username "
                f"and password — many providers require an App Password "
                f"when MFA is on."
            )
        raise

    try:
        # Detach the client from idle so subsequent SELECTs don't block.
        client.noop()
    except Exception:  # noqa: BLE001
        pass
    return client


def _select_folder(client: imaplib.IMAP4, folder: str) -> None:
    status, _ = client.select(folder, readonly=False)
    if status != "OK":
        raise imaplib.IMAP4.error(f"SELECT failed for folder {folder!r}")


def _search_unseen(client: imaplib.IMAP4, limit: int) -> List[bytes]:
    """Return up to ``limit`` UIDs of UNSEEN messages, oldest first."""
    status, data = client.uid("search", None, "UNSEEN")
    if status != "OK" or not data or data[0] is None:
        return []
    uids = data[0].split()
    return uids[:limit]


# ---------------------------------------------------------------------------
# Per-message processing
# ---------------------------------------------------------------------------


def _process_one(
    db: Session,
    client: imaplib.IMAP4,
    uid: bytes,
    config: ResolvedImapConfig,
) -> InboundReplyOutcome:
    """Fetch ⇒ parse ⇒ match ⇒ persist ⇒ flag-as-seen one message."""
    uid_str = uid.decode("ascii", errors="replace")
    outcome = InboundReplyOutcome(uid=uid_str, message_id=None)

    try:
        msg = _fetch_message(client, uid)
    except Exception as exc:  # noqa: BLE001
        outcome.error = f"fetch failed: {exc}"
        logger.exception("IMAP fetch for UID %s failed", uid_str)
        return outcome

    if msg is None:
        outcome.skipped_reason = "fetch returned no body"
        return outcome

    outcome.message_id = _normalise_message_id(msg.get("Message-ID"))

    # Already imported? Skip cleanly — no flag change so the caller
    # can re-flag without duplicates.
    if outcome.message_id and _reply_already_exists(db, outcome.message_id):
        outcome.skipped_reason = "duplicate message id"
        _mark_seen(client, uid)
        return outcome

    ticket = _match_ticket(db, msg)
    if ticket is None:
        if config.create_new_tickets:
            new_msg = _create_ticket_from_email(db, msg)
            ticket = new_msg
            outcome.matched_via = "new ticket"
        else:
            outcome.skipped_reason = "no matching ticket"
            _move_to(client, uid, config.error_folder, mark_seen=True)
            return outcome
    else:
        outcome.matched_ticket = ticket[0]
        outcome.matched_via = ticket[2]
        ticket = ticket[1]

    body_text, body_html = _extract_bodies(msg)
    clean_text = strip_quoted_reply(body_text)

    in_reply_to = _normalise_message_id(msg.get("In-Reply-To"))
    references = _extract_references(msg)

    reply = ContactReply(
        contact_message_id=ticket.id,
        direction="inbound",
        sender_type=SENDER_CUSTOMER,
        sender_name=_decode_header(msg.get("From")) or ticket.name,
        sender_email=_email_address_from_header(msg.get("From")) or ticket.email,
        recipient_email=_email_address_from_header(msg.get("To")),
        subject=_decode_header(msg.get("Subject")),
        body=body_text or "",
        body_html=body_html,
        clean_body_text=clean_text or None,
        email_message_id=outcome.message_id,
        in_reply_to=in_reply_to,
        references_header=" ".join(references) if references else None,
        has_attachments=False,
        email_status=REPLY_STATUS_RECEIVED,
        sent_at=_parse_date_header(msg.get("Date")),
    )
    db.add(reply)
    db.flush()

    attachments = _save_attachments(db, msg, reply.id)
    if attachments:
        reply.has_attachments = True
        outcome.attachments_saved = len(attachments)

    now = datetime.now(timezone.utc)
    ticket.last_customer_reply_at = now
    ticket.last_message_at = now
    ticket.inbound_email_message_id = outcome.message_id
    # State transition: any inbound reply pushes the conversation back
    # into the admin's court (unless the ticket has been explicitly
    # completed — a reply after completion still flips back to OPEN
    # rather than reopened to keep the audit trail tidy).
    if ticket.status not in (CONTACT_STATUS_PENDING_ADMIN,):
        ticket.status = CONTACT_STATUS_PENDING_ADMIN
    # Surface in the legacy "unread" inbox UI too.
    ticket.is_read = False

    db.commit()

    outcome.reply_id = reply.id
    _move_to(client, uid, config.processed_folder, mark_seen=True)
    return outcome


def _create_ticket_from_email(
    db: Session, msg: email.message.Message
) -> ContactMessage:
    """Open a brand-new ticket for an email that didn't match anything."""
    from app.services.contact_threading import (
        generate_thread_token,
        generate_ticket_number,
    )

    now = datetime.now(timezone.utc)
    sender_name = _decode_header(msg.get("From")) or "Unknown sender"
    sender_email = _email_address_from_header(msg.get("From")) or "unknown@unknown"
    subject = _decode_header(msg.get("Subject")) or "(no subject)"
    body_text, _ = _extract_bodies(msg)
    new = ContactMessage(
        name=sender_name[:255],
        email=sender_email.lower()[:255],
        subject=subject[:255] if subject else None,
        message=body_text or "(empty body)",
        ticket_number=generate_ticket_number(db, now=now),
        thread_token=generate_thread_token(),
        status=CONTACT_STATUS_PENDING_ADMIN,
        priority="normal",
        source="email_reply",
        last_message_at=now,
        last_customer_reply_at=now,
    )
    db.add(new)
    db.flush()
    return new


# ---------------------------------------------------------------------------
# IMAP fetch + flag helpers
# ---------------------------------------------------------------------------


def _fetch_message(
    client: imaplib.IMAP4, uid: bytes
) -> Optional[email.message.Message]:
    status, data = client.uid("fetch", uid, "(RFC822)")
    if status != "OK" or not data:
        return None
    for entry in data:
        if isinstance(entry, tuple) and len(entry) >= 2:
            raw = entry[1]
            return email.message_from_bytes(raw, policy=email.policy.default)
    return None


def _mark_seen(client: imaplib.IMAP4, uid: bytes) -> None:
    try:
        client.uid("store", uid, "+FLAGS", r"(\Seen)")
    except Exception:  # noqa: BLE001
        logger.exception("Failed to flag UID %r as Seen", uid)


def _move_to(
    client: imaplib.IMAP4,
    uid: bytes,
    folder: Optional[str],
    *,
    mark_seen: bool,
) -> None:
    """Best-effort move to ``folder`` (Sent/Processed/Errors).

    Tries IMAP MOVE first (RFC 6851); on servers without the
    extension falls back to COPY + STORE \\Deleted + EXPUNGE so the
    user's inbox doesn't keep growing forever. If everything fails
    we just leave the message in place — the +\\Seen flag still
    keeps it out of the next poll.
    """
    if mark_seen:
        _mark_seen(client, uid)
    if not folder:
        return
    try:
        status, _ = client.uid("move", uid, folder)
        if status == "OK":
            return
    except Exception:  # noqa: BLE001
        pass
    # COPY+delete fallback
    try:
        status, _ = client.uid("copy", uid, folder)
        if status == "OK":
            client.uid("store", uid, "+FLAGS", r"(\Deleted)")
            client.expunge()
    except Exception:  # noqa: BLE001
        logger.exception(
            "Could not relocate UID %r to %s — left in inbox", uid, folder
        )


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _match_ticket(
    db: Session, msg: email.message.Message
) -> Optional[Tuple[str, ContactMessage, str]]:
    """Return ``(ticket_number, message, matched_via)`` or ``None``."""
    # 1. X-PUG-Contact-Thread header
    token = msg.get(THREAD_HEADER_NAME)
    if token:
        ticket = _lookup_by_token(db, token.strip())
        if ticket:
            return ticket.ticket_number, ticket, "x-pug header"

    # 2. In-Reply-To
    in_reply_to = _normalise_message_id(msg.get("In-Reply-To"))
    if in_reply_to:
        token = parse_thread_token_from_message_id(in_reply_to)
        if token:
            ticket = _lookup_by_token(db, token)
            if ticket:
                return ticket.ticket_number, ticket, "in-reply-to"

    # 3. References (chain — try each)
    for ref in _extract_references(msg):
        token = parse_thread_token_from_message_id(ref)
        if not token:
            continue
        ticket = _lookup_by_token(db, token)
        if ticket:
            return ticket.ticket_number, ticket, "references"

    # 4. Subject ticket bracket
    ticket_number = extract_ticket_from_subject(_decode_header(msg.get("Subject")))
    if ticket_number:
        ticket = db.execute(
            select(ContactMessage).where(
                ContactMessage.ticket_number == ticket_number
            )
        ).scalar_one_or_none()
        if ticket:
            return ticket.ticket_number, ticket, "subject bracket"

    return None


def _lookup_by_token(db: Session, token: str) -> Optional[ContactMessage]:
    if not token:
        return None
    return db.execute(
        select(ContactMessage).where(ContactMessage.thread_token == token)
    ).scalar_one_or_none()


def _reply_already_exists(db: Session, message_id: str) -> bool:
    if not message_id:
        return False
    return (
        db.execute(
            select(ContactReply.id).where(
                ContactReply.email_message_id == message_id
            )
        ).first()
        is not None
    )


# ---------------------------------------------------------------------------
# Body + attachment extraction
# ---------------------------------------------------------------------------


def _extract_bodies(
    msg: email.message.Message,
) -> Tuple[Optional[str], Optional[str]]:
    """Return (plain text body, html body). Either may be ``None``."""
    text: Optional[str] = None
    html: Optional[str] = None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            if ctype == "text/plain" and text is None:
                text = _decode_part(part)
            elif ctype == "text/html" and html is None:
                html = _decode_part(part)
            if text and html:
                break
    else:
        payload = _decode_part(msg)
        if msg.get_content_type() == "text/html":
            html = payload
        else:
            text = payload
    return text, html


def _decode_part(part: email.message.Message) -> Optional[str]:
    try:
        payload = part.get_payload(decode=True)
    except Exception:  # noqa: BLE001
        return None
    if payload is None:
        return None
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return payload.decode("utf-8", errors="replace")


def _save_attachments(
    db: Session, msg: email.message.Message, reply_id: int
) -> List[ContactReplyAttachment]:
    """Walk the message, save every attachment under uploads/."""
    if not msg.is_multipart():
        return []

    settings = get_settings()
    cap_bytes = (settings.max_upload_size_mb or 20) * 1024 * 1024
    base = Path(settings.upload_dir) / "contact-attachments" / str(reply_id)
    base.mkdir(parents=True, exist_ok=True)

    saved: List[ContactReplyAttachment] = []
    total_bytes = 0
    for part in msg.walk():
        disp = (part.get("Content-Disposition") or "").lower()
        if "attachment" not in disp and not part.get_filename():
            continue
        try:
            payload = part.get_payload(decode=True)
        except Exception:  # noqa: BLE001
            continue
        if not payload:
            continue
        size = len(payload)
        if total_bytes + size > cap_bytes:
            logger.warning(
                "Dropping attachment for reply %s — would exceed %s MB cap",
                reply_id,
                settings.max_upload_size_mb,
            )
            continue
        total_bytes += size
        original = _decode_header(part.get_filename()) or "attachment.bin"
        safe_name = _safe_filename(original)
        stored = f"{uuid.uuid4().hex}-{safe_name}"
        path = base / stored
        path.write_bytes(payload)
        row = ContactReplyAttachment(
            contact_reply_id=reply_id,
            original_filename=original[:500],
            stored_filename=stored[:500],
            file_path=str(path)[:1000],
            mime_type=(part.get_content_type() or "")[:160] or None,
            file_size=size,
        )
        db.add(row)
        saved.append(row)
    if saved:
        db.flush()
    return saved


# ---------------------------------------------------------------------------
# Header / text utilities
# ---------------------------------------------------------------------------


_MESSAGE_ID_RE = re.compile(r"<[^>]+>")


def _normalise_message_id(value: Optional[str]) -> Optional[str]:
    """Return the first ``<…>`` token in the header, lowercased domain."""
    if not value:
        return None
    match = _MESSAGE_ID_RE.search(value)
    if not match:
        # Some clients drop the angle brackets — accept that too.
        candidate = value.strip()
        if "@" in candidate:
            return f"<{candidate}>"
        return None
    return match.group(0)


def _extract_references(msg: email.message.Message) -> List[str]:
    raw = msg.get("References")
    if not raw:
        return []
    return _MESSAGE_ID_RE.findall(raw)


def _decode_header(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        decoded = email.header.decode_header(value)
    except Exception:  # noqa: BLE001
        return str(value)
    parts: List[str] = []
    for chunk, charset in decoded:
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts).strip()


def _email_address_from_header(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    name, addr = email.utils.parseaddr(value)
    return addr.lower() or None


def _parse_date_header(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


_QUOTE_HEADER_RE = re.compile(
    r"""^\s*(
        (On\s.+wrote:\s*$)             # "On <date>, <person> wrote:"
        |(From:\s.+$)                  # Outlook "From:" boundary
        |(-----\s*Original\s+Message\s*-----)
        |(_{5,})                       # 5+ underscores divider
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def strip_quoted_reply(body: Optional[str]) -> Optional[str]:
    """Best-effort trim of the quoted "previous email" block.

    Walks the body line by line, keeping content until we hit a quote
    header (Gmail / Outlook style) or a string of ``>`` quote markers,
    then stops. Imperfect but good enough for the chat-preview line.
    """
    if not body:
        return None
    lines = body.splitlines()
    keep: List[str] = []
    for line in lines:
        if _QUOTE_HEADER_RE.match(line):
            break
        if line.lstrip().startswith(">"):
            break
        keep.append(line)
    out = "\n".join(keep).strip()
    return out or None


_UNSAFE_FN = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name: str) -> str:
    cleaned = _UNSAFE_FN.sub("_", name).strip("._-")
    if not cleaned:
        cleaned = "attachment.bin"
    return cleaned[:200]


# ---------------------------------------------------------------------------
# Test seam — production code uses :func:`poll_inbox` but unit tests
# need to drive the per-message processor with a fabricated message.
# ---------------------------------------------------------------------------


def process_fake_message(
    db: Session,
    raw_bytes: bytes,
    *,
    settings=None,
) -> InboundReplyOutcome:
    """Run :func:`_process_one` against an in-memory message.

    Used by the IMAP unit tests so they can validate matching +
    threading without bringing up an IMAP server.
    """
    # Backwards-compatible: the existing tests sometimes pass an env-
    # only ``settings`` (the test seam was historically env-driven).
    # We just need the ``create_new_tickets`` flag here — read from
    # env when no settings overrride is given.
    create_new = _create_new_tickets_env()

    # Inline the relevant bits of _process_one without IMAP fetch.
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
    outcome = InboundReplyOutcome(uid="fake", message_id=_normalise_message_id(msg.get("Message-ID")))
    if outcome.message_id and _reply_already_exists(db, outcome.message_id):
        outcome.skipped_reason = "duplicate message id"
        return outcome

    ticket = _match_ticket(db, msg)
    if ticket is None:
        if create_new:
            ticket_obj = _create_ticket_from_email(db, msg)
            ticket = (ticket_obj.ticket_number, ticket_obj, "new ticket")
        else:
            outcome.skipped_reason = "no matching ticket"
            return outcome

    outcome.matched_ticket = ticket[0]
    outcome.matched_via = ticket[2]
    ticket_obj = ticket[1]

    body_text, body_html = _extract_bodies(msg)
    in_reply_to = _normalise_message_id(msg.get("In-Reply-To"))
    references = _extract_references(msg)

    reply = ContactReply(
        contact_message_id=ticket_obj.id,
        direction="inbound",
        sender_type=SENDER_CUSTOMER,
        sender_name=_decode_header(msg.get("From")) or ticket_obj.name,
        sender_email=_email_address_from_header(msg.get("From"))
        or ticket_obj.email,
        recipient_email=_email_address_from_header(msg.get("To")),
        subject=_decode_header(msg.get("Subject")),
        body=body_text or "",
        body_html=body_html,
        clean_body_text=strip_quoted_reply(body_text),
        email_message_id=outcome.message_id,
        in_reply_to=in_reply_to,
        references_header=" ".join(references) if references else None,
        email_status=REPLY_STATUS_RECEIVED,
        sent_at=_parse_date_header(msg.get("Date")),
    )
    db.add(reply)
    db.flush()

    now = datetime.now(timezone.utc)
    ticket_obj.last_customer_reply_at = now
    ticket_obj.last_message_at = now
    ticket_obj.inbound_email_message_id = outcome.message_id
    ticket_obj.status = CONTACT_STATUS_PENDING_ADMIN
    ticket_obj.is_read = False
    db.commit()
    outcome.reply_id = reply.id
    return outcome


__all__ = [
    "ImapTestOutcome",
    "InboundPollSummary",
    "InboundReplyOutcome",
    "ResolvedImapConfig",
    "poll_inbox",
    "process_fake_message",
    "resolve_imap_config",
    "strip_quoted_reply",
    "test_imap_connection",
]
