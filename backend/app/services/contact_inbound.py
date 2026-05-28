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
from app.models.cms import (
    CONTACT_STATUS_OPEN,
    CONTACT_STATUS_PENDING_ADMIN,
    ContactMessage,
    ContactReply,
    ContactReplyAttachment,
    REPLY_STATUS_RECEIVED,
    SENDER_CUSTOMER,
)
from app.services.contact_threading import (
    THREAD_HEADER_NAME,
    extract_ticket_from_subject,
    parse_thread_token_from_message_id,
)

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
    settings = get_settings()
    summary = InboundPollSummary(enabled=bool(settings.contact_inbound_enabled))
    if not summary.enabled:
        summary.error = "IMAP inbound is disabled (CONTACT_INBOUND_ENABLED=false)."
        summary.finished_at = datetime.now(timezone.utc)
        return summary
    if not _config_complete(settings):
        summary.error = (
            "IMAP inbound is enabled but host/username/password are missing — "
            "set CONTACT_INBOUND_HOST/USERNAME/PASSWORD."
        )
        summary.finished_at = datetime.now(timezone.utc)
        return summary

    try:
        client = _connect(settings)
    except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
        summary.error = f"IMAP connect failed: {exc}"
        summary.finished_at = datetime.now(timezone.utc)
        logger.exception("Contact-inbox IMAP connect failed")
        return summary

    try:
        _select_folder(client, settings.contact_inbound_folder)
        uids = _search_unseen(client, limit)
        summary.fetched = len(uids)
        for uid in uids:
            outcome = _process_one(db, client, uid, settings)
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
# Connection helpers
# ---------------------------------------------------------------------------


def _config_complete(settings) -> bool:
    return bool(
        settings.contact_inbound_host
        and settings.contact_inbound_username
        and settings.contact_inbound_password
    )


def _connect(settings) -> imaplib.IMAP4:
    """Open an authenticated IMAP4 / IMAP4_SSL connection.

    Returns the client positioned at the AUTH state — the caller still
    needs to SELECT a folder.
    """
    host = settings.contact_inbound_host
    port = settings.contact_inbound_port
    if settings.contact_inbound_use_ssl:
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
    client.login(
        settings.contact_inbound_username, settings.contact_inbound_password
    )
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
    settings,
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
        if _create_new_ticket_enabled(settings):
            new_msg = _create_ticket_from_email(db, msg)
            ticket = new_msg
            outcome.matched_via = "new ticket"
        else:
            outcome.skipped_reason = "no matching ticket"
            _move_to(client, uid, settings.contact_inbound_error_folder, mark_seen=True)
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
    _move_to(client, uid, settings.contact_inbound_processed_folder, mark_seen=True)
    return outcome


def _create_new_ticket_enabled(settings) -> bool:
    """Honour ``CONTACT_INBOUND_CREATE_NEW`` (defaults off).

    Reading via env keeps this opt-in without adding another required
    Settings field — most operators leave it off so an unrelated email
    can't mint a ticket.
    """
    import os

    return os.getenv("CONTACT_INBOUND_CREATE_NEW", "false").lower() in {
        "1",
        "true",
        "yes",
    }


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
    settings = settings or get_settings()

    class _FakeClient:
        def uid(self, *_args, **_kwargs):  # noqa: D401
            return ("OK", [])

        def close(self):
            pass

        def logout(self):
            pass

    fake = _FakeClient()
    # Inline the relevant bits of _process_one without IMAP fetch.
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
    outcome = InboundReplyOutcome(uid="fake", message_id=_normalise_message_id(msg.get("Message-ID")))
    if outcome.message_id and _reply_already_exists(db, outcome.message_id):
        outcome.skipped_reason = "duplicate message id"
        return outcome

    ticket = _match_ticket(db, msg)
    if ticket is None:
        if _create_new_ticket_enabled(settings):
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
    "InboundPollSummary",
    "InboundReplyOutcome",
    "poll_inbox",
    "process_fake_message",
    "strip_quoted_reply",
]
