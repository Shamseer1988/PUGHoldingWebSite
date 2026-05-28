"""Regression tests: the IMAP poller must leave non-ticket mail alone.

The original implementation searched ``UNSEEN`` and stamped
``\\Seen`` on every UID it processed — including ones it couldn't
match to a ticket. That broke the user-visible promise that
non-ticket mail should look "exactly the same as if we weren't
polling" in Outlook / Gmail.

These tests drive ``poll_inbox`` against a fabricated IMAP server
that records every STORE call, then assert:

* The search criterion is ``UNKEYWORD $PUG-Inspected`` (so Read
  vs Unread in Outlook doesn't hide a ticket reply from us).
* A matched ticket reply DOES get ``\\Seen`` (so the support
  mailbox doesn't grow an angry red unread badge) AND gets the
  custom ``$PUG-Inspected`` keyword.
* An unmatched email is touched ONLY by the inspected keyword —
  no ``\\Seen``, no MOVE, no COPY.
* The UNKEYWORD search falls back to ``UNSEEN`` on servers that
  reject custom keywords (defensive — the dedup on Message-ID
  still prevents duplicate ContactReplies).
"""
from __future__ import annotations

import imaplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import List, Optional, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cms import (
    CONTACT_STATUS_PENDING_CUSTOMER,
    ContactMessage,
    ContactReply,
    SENDER_CUSTOMER,
)
from app.models.email_settings import EmailSetting
from app.services.contact_inbound import (
    IMAP_INSPECTED_KEYWORD,
    poll_inbox,
)
from app.services.contact_threading import (
    THREAD_HEADER_NAME,
    generate_thread_token,
    generate_ticket_number,
)


ADMIN_LOGIN = "/api/v1/admin/auth/login"
SETTINGS_PATH = "/api/v1/admin/email-settings"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _StoreCall:
    __slots__ = ("uid", "op", "flags")

    def __init__(self, uid: bytes, op: str, flags: str):
        self.uid = uid
        self.op = op
        self.flags = flags

    def __repr__(self) -> str:  # pragma: no cover — debug helper
        return f"StoreCall({self.uid!r}, {self.op}, {self.flags!r})"


class _FakeIMAPForPoll:
    """Fake IMAP4_SSL covering everything the poller actually calls.

    Exposes ``stores`` (list of recorded STORE invocations) and
    ``searches`` (list of search criteria) so a test can prove
    *which* flag the poller stamped on each UID.
    """

    welcome = b"* OK Fake IMAP ready."

    def __init__(
        self,
        *,
        uids_by_search: dict[str, List[bytes]],
        bodies: dict[bytes, bytes],
        reject_keyword_search: bool = False,
        reject_keyword_store: bool = False,
    ):
        self._uids_by_search = uids_by_search
        self._bodies = bodies
        self._reject_keyword_search = reject_keyword_search
        self._reject_keyword_store = reject_keyword_store
        self.stores: List[_StoreCall] = []
        self.searches: List[str] = []
        self.moves: List[Tuple[bytes, str]] = []
        self.copies: List[Tuple[bytes, str]] = []
        self._login_ok = True
        self._select_ok = True

    # ---- imaplib API used by our code --------------------------------------

    def starttls(self, _ctx):  # pragma: no cover
        pass

    def login(self, user, password):
        if not self._login_ok:
            raise imaplib.IMAP4.error("AUTHENTICATE failed.")
        return ("OK", [b"Authenticated"])

    def noop(self):
        return ("OK", [b"NOOP completed."])

    def select(self, folder, readonly=False):
        if not self._select_ok:
            raise imaplib.IMAP4.error(f"NO Mailbox: {folder}")
        return ("OK", [b"1"])

    def list(self):
        return ("OK", [b'(\\HasNoChildren) "/" "INBOX"'])

    def uid(self, op: str, *args):
        op = op.lower()
        if op == "search":
            # args: (None, criterion) per imaplib signature.
            criterion = " ".join(a for a in args if isinstance(a, str))
            self.searches.append(criterion)
            if (
                self._reject_keyword_search
                and "UNKEYWORD" in criterion.upper()
            ):
                raise imaplib.IMAP4.error("BAD UNKEYWORD not supported")
            uids = self._uids_by_search.get(criterion.strip(), [])
            return ("OK", [b" ".join(uids) if uids else None])
        if op == "fetch":
            uid = args[0] if args and isinstance(args[0], (bytes, bytearray)) else None
            body = self._bodies.get(bytes(uid) if uid else b"")
            if body is None:
                return ("NO", [None])
            # imaplib returns a list of (header_bytes, body_bytes) tuples
            return ("OK", [(b"placeholder", body)])
        if op == "store":
            uid, store_op, flags = args
            if (
                self._reject_keyword_store
                and IMAP_INSPECTED_KEYWORD in flags
            ):
                raise imaplib.IMAP4.error("BAD keyword not supported")
            self.stores.append(_StoreCall(uid, store_op, flags))
            return ("OK", [b"STORE completed."])
        if op == "move":
            uid, dest = args
            self.moves.append((uid, dest))
            return ("OK", [b"MOVE completed."])
        if op == "copy":
            uid, dest = args
            self.copies.append((uid, dest))
            return ("OK", [b"COPY completed."])
        return ("OK", [])

    def expunge(self):
        return ("OK", [])

    def close(self):
        pass

    def logout(self):
        return ("BYE", [])


def _login_super(client: TestClient, password: str) -> dict:
    r = client.post(
        ADMIN_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _enable_imap(client: TestClient, headers: dict) -> None:
    r = client.put(
        SETTINGS_PATH,
        json={
            "imap_enabled": True,
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "imap_username": "support@example.com",
            "imap_password": "pw",
            "imap_use_ssl": True,
            "imap_folder": "INBOX",
            "imap_create_new_tickets": False,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text


def _seed_ticket(db: Session, *, thread_token: str) -> ContactMessage:
    msg = ContactMessage(
        name="Jane Visitor",
        email="jane@example.com",
        subject="Pricing question",
        message="Hi, what does the bundle cost?",
        ticket_number=generate_ticket_number(db),
        thread_token=thread_token,
        status=CONTACT_STATUS_PENDING_CUSTOMER,
        priority="normal",
        source="website_contact",
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def _build_email(
    *,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    extra_headers: Optional[dict] = None,
    message_id: Optional[str] = None,
) -> bytes:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = "Wed, 28 May 2026 09:00:00 +0000"
    msg["Message-ID"] = message_id or "<test-1@customer.example>"
    if extra_headers:
        for k, v in extra_headers.items():
            msg[k] = v
    msg.set_content(body)
    return msg.as_bytes()


def _install_fake(monkeypatch, fake: _FakeIMAPForPoll) -> None:
    def factory(*_a, **_kw):
        return fake

    monkeypatch.setattr(imaplib, "IMAP4_SSL", factory)


# ---------------------------------------------------------------------------
# Tests — the actual behaviour the user asked for
# ---------------------------------------------------------------------------


def test_search_uses_unkeyword_inspected_marker(
    client: TestClient, seed_auth, db_session, monkeypatch
):
    """Read vs Unread in Outlook must not hide ticket replies from
    the poller — so the search criterion is keyword-based, not
    UNSEEN-based."""
    headers = _login_super(client, seed_auth["password"])
    _enable_imap(client, headers)

    fake = _FakeIMAPForPoll(uids_by_search={}, bodies={})
    _install_fake(monkeypatch, fake)

    summary = poll_inbox(db_session)
    assert summary.error is None
    assert summary.fetched == 0
    # The search criterion must be UNKEYWORD $PUG-Inspected.
    assert any(
        f"UNKEYWORD {IMAP_INSPECTED_KEYWORD}" in s for s in fake.searches
    )


def test_non_ticket_mail_is_completely_untouched(
    client: TestClient, seed_auth, db_session, monkeypatch
):
    """A spam / newsletter / random email that doesn't thread to any
    ticket must NOT be marked Seen and must NOT be moved. We only
    stamp the invisible ``$PUG-Inspected`` keyword so we don't
    re-fetch on the next cycle."""
    headers = _login_super(client, seed_auth["password"])
    _enable_imap(client, headers)

    uid = b"42"
    body = _build_email(
        from_addr="newsletter@somewhere.com",
        to_addr="support@example.com",
        subject="Weekly digest",
        body="hi there",
        message_id="<newsletter-1@somewhere.example>",
    )
    fake = _FakeIMAPForPoll(
        uids_by_search={f"UNKEYWORD {IMAP_INSPECTED_KEYWORD}": [uid]},
        bodies={uid: body},
    )
    _install_fake(monkeypatch, fake)

    summary = poll_inbox(db_session)
    assert summary.error is None
    assert summary.fetched == 1
    assert summary.matched == 0
    assert summary.skipped == 1

    # No new ContactReply was created.
    assert (
        db_session.query(ContactReply)
        .filter(ContactReply.sender_type == SENDER_CUSTOMER)
        .count()
        == 0
    )

    # Exactly ONE STORE call: the inspected keyword. No \Seen.
    # No MOVE. No COPY.
    assert len(fake.stores) == 1, fake.stores
    call = fake.stores[0]
    assert call.uid == uid
    assert call.op == "+FLAGS"
    assert IMAP_INSPECTED_KEYWORD in call.flags
    assert "\\Seen" not in call.flags
    assert fake.moves == []
    assert fake.copies == []


def test_matched_ticket_reply_gets_seen_and_inspected(
    client: TestClient, seed_auth, db_session, monkeypatch
):
    """The legitimate customer reply to an existing ticket DOES get
    \\Seen (so the support mailbox isn't perpetually unread) AND
    the inspected keyword (so the next poll skips it cleanly)."""
    headers = _login_super(client, seed_auth["password"])
    _enable_imap(client, headers)

    token = generate_thread_token()
    ticket = _seed_ticket(db_session, thread_token=token)

    uid = b"7"
    body = _build_email(
        from_addr=f"{ticket.name} <{ticket.email}>",
        to_addr="support@example.com",
        subject=f"Re: Pricing question [{ticket.ticket_number}]",
        body="Thanks — yes, please send the catalogue.",
        extra_headers={THREAD_HEADER_NAME: token},
        message_id="<reply-1@customer.example>",
    )
    fake = _FakeIMAPForPoll(
        uids_by_search={f"UNKEYWORD {IMAP_INSPECTED_KEYWORD}": [uid]},
        bodies={uid: body},
    )
    _install_fake(monkeypatch, fake)

    summary = poll_inbox(db_session)
    assert summary.error is None
    assert summary.fetched == 1
    assert summary.matched == 1

    db_session.refresh(ticket)
    assert any(
        r.sender_type == SENDER_CUSTOMER for r in ticket.replies
    )

    # We expect at least one STORE that adds \Seen and another (or
    # the same) that adds the inspected keyword. The mark-Seen path
    # is via _move_to which calls _mark_seen unconditionally.
    flags_stamped = " ".join(c.flags for c in fake.stores)
    assert "\\Seen" in flags_stamped
    assert IMAP_INSPECTED_KEYWORD in flags_stamped


def test_uninspected_search_falls_back_to_unseen_when_unsupported(
    client: TestClient, seed_auth, db_session, monkeypatch
):
    """Defensive: a server that rejects custom keywords still works —
    we degrade to the legacy UNSEEN search. The dedup on
    ``email_message_id`` prevents double-processing."""
    headers = _login_super(client, seed_auth["password"])
    _enable_imap(client, headers)

    uid = b"5"
    body = _build_email(
        from_addr="stranger@somewhere.com",
        to_addr="support@example.com",
        subject="Nothing related",
        body="just an email",
        message_id="<stranger-1@elsewhere>",
    )
    fake = _FakeIMAPForPoll(
        uids_by_search={"UNSEEN": [uid]},
        bodies={uid: body},
        reject_keyword_search=True,
    )
    _install_fake(monkeypatch, fake)

    summary = poll_inbox(db_session)
    assert summary.error is None
    assert summary.fetched == 1
    # Both the UNKEYWORD attempt and the UNSEEN fallback were tried.
    assert any("UNKEYWORD" in s for s in fake.searches)
    assert any(s.strip() == "UNSEEN" for s in fake.searches)


def test_inspected_keyword_failure_is_swallowed(
    client: TestClient, seed_auth, db_session, monkeypatch
):
    """If the server also rejects the keyword STORE, we don't crash —
    we just log + rely on Message-ID dedup so the same message
    won't double-thread next cycle."""
    headers = _login_super(client, seed_auth["password"])
    _enable_imap(client, headers)

    uid = b"9"
    body = _build_email(
        from_addr="stranger@somewhere.com",
        to_addr="support@example.com",
        subject="Random",
        body="hi",
        message_id="<random-1@elsewhere>",
    )
    fake = _FakeIMAPForPoll(
        uids_by_search={"UNSEEN": [uid]},
        bodies={uid: body},
        reject_keyword_search=True,
        reject_keyword_store=True,
    )
    _install_fake(monkeypatch, fake)

    summary = poll_inbox(db_session)
    assert summary.error is None
    assert summary.skipped == 1
    # No ContactReply created, no exception bubbled.
    assert (
        db_session.query(ContactReply)
        .filter(ContactReply.sender_type == SENDER_CUSTOMER)
        .count()
        == 0
    )
