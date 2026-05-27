"""Helpers for the Contact-Us ticket flow.

Two concerns live here:

1. Identity generation — ``generate_ticket_number`` produces the
   human-readable ``PUG-CNT-YYYYMMDD-NNNN`` id that the customer sees
   in the email subject; ``generate_thread_token`` produces the
   secret URL-safe token the IMAP processor uses to match an inbound
   email back to its conversation when the subject has been mangled.

2. Email-header helpers — ``build_outbound_headers`` assembles the
   ``Message-ID`` / ``In-Reply-To`` / ``References`` /
   ``X-PUG-Contact-Thread`` headers we need to keep an SMTP <-> IMAP
   round-trip threaded.

Status-machine transition logic and the IMAP processor itself live
in companion modules (``contact_state.py``, ``contact_inbound.py``)
shipped in later commits — kept separate so each file stays
reviewable.
"""
from __future__ import annotations

import secrets
import socket
import time
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cms import ContactMessage


# ---------------------------------------------------------------------------
# Identity generators
# ---------------------------------------------------------------------------


TICKET_PREFIX = "PUG-CNT"
# Custom email header that lets the IMAP processor match an inbound
# reply to its conversation even if the subject was edited or the
# In-Reply-To header was stripped by an over-eager corporate gateway.
THREAD_HEADER_NAME = "X-PUG-Contact-Thread"


def generate_ticket_number(
    db: Session, *, now: Optional[datetime] = None
) -> str:
    """Return the next ``PUG-CNT-YYYYMMDD-NNNN`` ticket number for today.

    The sequence resets at midnight UTC. We compute the day's count
    from ``contact_messages`` rather than maintaining a counter table
    — collisions are caught by the unique index on ``ticket_number``
    and the caller can retry.
    """
    moment = now or datetime.now(timezone.utc)
    day = moment.strftime("%Y%m%d")
    prefix = f"{TICKET_PREFIX}-{day}-"
    # How many tickets have we already issued today? COUNT on the
    # LIKE prefix is cheap given the unique index on ticket_number.
    existing = db.execute(
        select(func.count())
        .select_from(ContactMessage)
        .where(ContactMessage.ticket_number.like(f"{prefix}%"))
    ).scalar_one()
    seq = int(existing or 0) + 1
    return f"{prefix}{seq:04d}"


def generate_thread_token() -> str:
    """Return a URL-safe random token used as the secret thread id."""
    return secrets.token_urlsafe(24)


# ---------------------------------------------------------------------------
# Email header helpers
# ---------------------------------------------------------------------------


def build_message_id(thread_token: str, *, domain: Optional[str] = None) -> str:
    """Produce a deterministic-prefix Message-ID for an outbound reply.

    Format:  ``<contact-<thread>-<ts>-<rand>@<host>>``

    The thread token prefix lets the IMAP processor parse a Message-ID
    back to its conversation even when In-Reply-To / References get
    stripped. The trailing timestamp + random suffix keeps every
    Message-ID globally unique even if two replies fire in the same
    second.
    """
    host = domain or _suffix_domain()
    ts = int(time.time())
    rand = secrets.token_hex(6)
    return f"<contact-{thread_token}-{ts}-{rand}@{host}>"


def parse_thread_token_from_message_id(message_id: str) -> Optional[str]:
    """Extract the thread token from a Message-ID we previously generated.

    Returns ``None`` for any string that doesn't match the
    ``contact-<token>-…@…`` shape (i.e. anything we didn't write).
    """
    if not message_id:
        return None
    cleaned = message_id.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        cleaned = cleaned[1:-1]
    if not cleaned.startswith("contact-"):
        return None
    # cleaned now looks like: ``contact-<token>-<ts>-<rand>@host``
    body = cleaned[len("contact-") :]
    at_idx = body.rfind("@")
    if at_idx == -1:
        return None
    body = body[:at_idx]
    # The token can contain "-" (token_urlsafe uses [A-Za-z0-9_-]).
    # The trailing two segments are ``<ts>-<rand>``; everything before
    # those is the token. Splitting from the right keeps that robust.
    parts = body.rsplit("-", 2)
    if len(parts) != 3:
        return None
    token = parts[0]
    return token or None


def build_outbound_headers(
    *,
    thread_token: str,
    in_reply_to: Optional[str],
    references: Sequence[str] = (),
    domain: Optional[str] = None,
) -> dict[str, str]:
    """Assemble Message-ID / In-Reply-To / References / X-PUG headers.

    ``in_reply_to`` should be the Message-ID of the last message in
    the thread (the customer's most recent reply, or the previous
    outbound). ``references`` is the chain of every prior Message-ID;
    Outlook + Gmail use it to group threads.
    """
    new_message_id = build_message_id(thread_token, domain=domain)
    headers: dict[str, str] = {
        "Message-ID": new_message_id,
        THREAD_HEADER_NAME: thread_token,
    }
    if in_reply_to:
        headers["In-Reply-To"] = in_reply_to
    ref_chain = [r for r in references if r]
    if in_reply_to and in_reply_to not in ref_chain:
        ref_chain.append(in_reply_to)
    if ref_chain:
        # RFC 5322 References is a whitespace-separated list of msg-ids.
        headers["References"] = " ".join(ref_chain)
    return headers


# ---------------------------------------------------------------------------
# Subject helpers
# ---------------------------------------------------------------------------


def format_reply_subject(original_subject: Optional[str], ticket_number: str) -> str:
    """Return the subject line we put on outbound admin replies.

    Shape: ``Re: <original subject> [PUG-CNT-…]``. If the original
    subject already includes the ticket bracket (e.g. the customer
    replied via email and kept the subject intact), we don't add it
    a second time. If the original starts with ``Re:`` we keep it
    rather than producing ``Re: Re: …``.
    """
    base = (original_subject or "Your enquiry").strip()
    if not base:
        base = "Your enquiry"
    ticket_marker = f"[{ticket_number}]"
    # Strip pre-existing brackets to avoid duplication.
    if ticket_marker.lower() in base.lower():
        body = base
    else:
        body = f"{base} {ticket_marker}"
    if body.lower().startswith("re:"):
        return body
    return f"Re: {body}"


def extract_ticket_from_subject(subject: Optional[str]) -> Optional[str]:
    """Find a ``PUG-CNT-…`` ticket bracket in an inbound email subject."""
    if not subject:
        return None
    import re

    match = re.search(r"\[(PUG-CNT-[A-Z0-9\-]+)\]", subject, re.IGNORECASE)
    return match.group(1).upper() if match else None


def _suffix_domain() -> str:
    """Best-effort hostname for the right-hand side of a Message-ID.

    Tries the configured sender's email domain, then the host's
    FQDN, falling back to ``pug-holding.local`` so we never raise.
    """
    from app.core.config import get_settings

    settings = get_settings()
    if settings.smtp_from_email and "@" in settings.smtp_from_email:
        return settings.smtp_from_email.split("@", 1)[1]
    try:
        return socket.getfqdn() or "pug-holding.local"
    except Exception:  # noqa: BLE001
        return "pug-holding.local"


__all__ = [
    "THREAD_HEADER_NAME",
    "TICKET_PREFIX",
    "build_message_id",
    "build_outbound_headers",
    "extract_ticket_from_subject",
    "format_reply_subject",
    "generate_thread_token",
    "generate_ticket_number",
    "parse_thread_token_from_message_id",
]
