"""Tests for the contact-ticket IMAP inbound poller + state machine.

The poller is exercised via :func:`app.services.contact_inbound.process_fake_message`
so we don't need an IMAP server in the test loop — we feed it raw RFC
5322 bytes and assert that the matching, threading and state
transitions land where we expect.

The state-machine endpoints (/complete, /reopen, /unarchive) are
driven through the FastAPI ``client`` fixture so the audit-log path
+ permission check are covered alongside the model writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cms import (
    CONTACT_STATUS_COMPLETED,
    CONTACT_STATUS_OPEN,
    CONTACT_STATUS_PENDING_ADMIN,
    CONTACT_STATUS_PENDING_CUSTOMER,
    ContactMessage,
    ContactReply,
    SENDER_ADMIN,
    SENDER_CUSTOMER,
    SENDER_SYSTEM,
)
from app.services.contact_inbound import (
    process_fake_message,
    strip_quoted_reply,
)
from app.services.contact_threading import (
    THREAD_HEADER_NAME,
    build_message_id,
    generate_thread_token,
    generate_ticket_number,
)


ADMIN_LOGIN = "/api/v1/admin/auth/login"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login_website(client: TestClient, seed_auth) -> dict[str, str]:
    response = client.post(
        ADMIN_LOGIN,
        json={
            "email": "webadmin@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_ticket(
    db_session: Session,
    *,
    thread_token: Optional[str] = None,
    status: str = CONTACT_STATUS_PENDING_CUSTOMER,
) -> ContactMessage:
    """Create a contact ticket already-replied (the admin has sent
    one outbound and is now waiting for the customer)."""
    msg = ContactMessage(
        name="Jane Visitor",
        email="jane@example.com",
        subject="Pricing question",
        message="Hi, what does the bundle cost?",
        ticket_number=generate_ticket_number(db_session),
        thread_token=thread_token or generate_thread_token(),
        status=status,
        priority="normal",
        source="website_contact",
        last_message_at=datetime.now(timezone.utc),
    )
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)
    return msg


def _build_inbound_email(
    *,
    ticket: ContactMessage,
    body: str = "Thanks — yes, please send the catalogue!",
    in_reply_to: Optional[str] = None,
    references: Optional[list[str]] = None,
    include_thread_header: bool = False,
    subject: Optional[str] = None,
    message_id: Optional[str] = None,
) -> bytes:
    """Compose a customer-reply RFC 5322 message as bytes."""
    msg = EmailMessage()
    msg["From"] = f"{ticket.name} <{ticket.email}>"
    msg["To"] = "support@parisunited.example"
    msg["Subject"] = (
        subject
        if subject is not None
        else f"Re: {ticket.subject} [{ticket.ticket_number}]"
    )
    msg["Date"] = "Wed, 28 May 2026 09:00:00 +0000"
    msg["Message-ID"] = message_id or build_message_id(
        generate_thread_token(), domain="customer.example"
    )
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = " ".join(references)
    if include_thread_header:
        msg[THREAD_HEADER_NAME] = ticket.thread_token
    msg.set_content(body)
    return msg.as_bytes()


# ---------------------------------------------------------------------------
# strip_quoted_reply
# ---------------------------------------------------------------------------


def test_strip_quoted_reply_handles_outlook_style():
    body = (
        "Thanks, that works for me.\n"
        "\n"
        "From: Support <support@example.com>\n"
        "Sent: Wednesday, May 27, 2026 5:00 PM\n"
        "To: Jane <jane@example.com>\n"
        "Subject: Re: Your enquiry\n"
        "\n"
        "Hi Jane, here's the catalogue …\n"
    )
    assert strip_quoted_reply(body) == "Thanks, that works for me."


def test_strip_quoted_reply_handles_gmail_on_wrote():
    body = (
        "Sounds good — Tuesday works.\n"
        "\n"
        "On Wed, May 27, 2026 at 5:00 PM Support <s@example.com> wrote:\n"
        "> hello\n"
        "> world\n"
    )
    assert strip_quoted_reply(body) == "Sounds good — Tuesday works."


def test_strip_quoted_reply_handles_plain_caret_quote():
    body = "Replying inline\n\n> previous text\n> more"
    assert strip_quoted_reply(body) == "Replying inline"


def test_strip_quoted_reply_returns_none_for_empty():
    assert strip_quoted_reply("") is None
    assert strip_quoted_reply(None) is None


# ---------------------------------------------------------------------------
# IMAP matching
# ---------------------------------------------------------------------------


def test_inbound_matches_by_x_pug_thread_header(db_session: Session):
    ticket = _seed_ticket(db_session)
    raw = _build_inbound_email(
        ticket=ticket,
        include_thread_header=True,
        subject="Re: Pricing question",  # no bracket — header should still match
    )
    outcome = process_fake_message(db_session, raw)
    assert outcome.error is None
    assert outcome.matched_via == "x-pug header"
    assert outcome.matched_ticket == ticket.ticket_number

    db_session.refresh(ticket)
    assert ticket.status == CONTACT_STATUS_PENDING_ADMIN
    assert ticket.last_customer_reply_at is not None
    assert any(r.sender_type == SENDER_CUSTOMER for r in ticket.replies)


def test_inbound_matches_by_in_reply_to(db_session: Session):
    ticket = _seed_ticket(db_session)
    our_outbound_id = build_message_id(
        ticket.thread_token, domain="pug.example"
    )
    raw = _build_inbound_email(
        ticket=ticket,
        in_reply_to=our_outbound_id,
        subject="Re: completely different subject",
    )
    outcome = process_fake_message(db_session, raw)
    assert outcome.matched_via == "in-reply-to"
    assert outcome.matched_ticket == ticket.ticket_number


def test_inbound_matches_by_references_chain(db_session: Session):
    ticket = _seed_ticket(db_session)
    older = build_message_id(generate_thread_token(), domain="other.example")
    ours = build_message_id(ticket.thread_token, domain="pug.example")
    raw = _build_inbound_email(
        ticket=ticket,
        references=[older, ours],
        subject="something else",
    )
    outcome = process_fake_message(db_session, raw)
    assert outcome.matched_via == "references"
    assert outcome.matched_ticket == ticket.ticket_number


def test_inbound_matches_by_subject_bracket(db_session: Session):
    ticket = _seed_ticket(db_session)
    # No header, no In-Reply-To, no References — only the [PUG-CNT-…]
    # subject bracket survives.
    raw = _build_inbound_email(
        ticket=ticket,
        subject=f"Random subject [{ticket.ticket_number}]",
    )
    outcome = process_fake_message(db_session, raw)
    assert outcome.matched_via == "subject bracket"
    assert outcome.matched_ticket == ticket.ticket_number


def test_inbound_unknown_message_is_skipped_when_create_new_disabled(
    db_session: Session, monkeypatch
):
    monkeypatch.delenv("CONTACT_INBOUND_CREATE_NEW", raising=False)
    msg = EmailMessage()
    msg["From"] = "stranger@example.com"
    msg["To"] = "support@parisunited.example"
    msg["Subject"] = "Some unrelated email"
    msg["Date"] = "Wed, 28 May 2026 09:00:00 +0000"
    msg["Message-ID"] = "<stranger-1@elsewhere>"
    msg.set_content("hello")
    outcome = process_fake_message(db_session, msg.as_bytes())
    assert outcome.skipped_reason == "no matching ticket"
    assert outcome.reply_id is None


def test_inbound_unknown_message_opens_ticket_when_enabled(
    db_session: Session, monkeypatch
):
    monkeypatch.setenv("CONTACT_INBOUND_CREATE_NEW", "true")
    msg = EmailMessage()
    msg["From"] = "Stranger <stranger@example.com>"
    msg["To"] = "support@parisunited.example"
    msg["Subject"] = "Wholesale enquiry"
    msg["Date"] = "Wed, 28 May 2026 09:00:00 +0000"
    msg["Message-ID"] = "<stranger-2@elsewhere>"
    msg.set_content("Hi, do you sell wholesale?")
    outcome = process_fake_message(db_session, msg.as_bytes())
    assert outcome.reply_id is not None
    assert outcome.matched_ticket  # ticket number assigned
    new_ticket = db_session.query(ContactMessage).filter_by(
        email="stranger@example.com"
    ).one()
    assert new_ticket.source == "email_reply"
    assert new_ticket.status == CONTACT_STATUS_PENDING_ADMIN


def test_inbound_duplicate_message_id_is_idempotent(db_session: Session):
    ticket = _seed_ticket(db_session)
    mid = build_message_id(generate_thread_token(), domain="customer.example")
    raw = _build_inbound_email(
        ticket=ticket,
        include_thread_header=True,
        message_id=mid,
    )
    first = process_fake_message(db_session, raw)
    assert first.reply_id is not None

    second = process_fake_message(db_session, raw)
    assert second.skipped_reason == "duplicate message id"
    assert second.reply_id is None
    # Only one customer reply on the ticket — duplicate didn't double up.
    customer_replies = [
        r for r in ticket.replies if r.sender_type == SENDER_CUSTOMER
    ]
    assert len(customer_replies) == 1


# ---------------------------------------------------------------------------
# State-machine endpoints
# ---------------------------------------------------------------------------


def test_complete_flips_status_and_adds_system_bubble(
    client: TestClient, seed_auth, db_session: Session
):
    ticket = _seed_ticket(db_session)
    headers = _login_website(client, seed_auth)
    resp = client.post(
        f"/api/v1/admin/cms/contact-messages/{ticket.id}/complete",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == CONTACT_STATUS_COMPLETED
    assert payload["completed_at"] is not None
    # System bubble appended
    assert any(
        b["sender_type"] == SENDER_SYSTEM
        and "completed" in b["body"].lower()
        for b in payload["replies"]
    )


def test_reopen_clears_completed_and_unarchives(
    client: TestClient, seed_auth, db_session: Session
):
    ticket = _seed_ticket(db_session, status=CONTACT_STATUS_COMPLETED)
    ticket.completed_at = datetime.now(timezone.utc)
    ticket.is_archived = True
    db_session.commit()

    headers = _login_website(client, seed_auth)
    resp = client.post(
        f"/api/v1/admin/cms/contact-messages/{ticket.id}/reopen",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == CONTACT_STATUS_PENDING_ADMIN
    assert payload["completed_at"] is None
    assert payload["is_archived"] is False
    assert payload["reopened_at"] is not None


def test_unarchive_clears_archive_flag_without_touching_status(
    client: TestClient, seed_auth, db_session: Session
):
    ticket = _seed_ticket(db_session, status=CONTACT_STATUS_COMPLETED)
    ticket.is_archived = True
    db_session.commit()

    headers = _login_website(client, seed_auth)
    resp = client.post(
        f"/api/v1/admin/cms/contact-messages/{ticket.id}/unarchive",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["is_archived"] is False
    assert payload["status"] == CONTACT_STATUS_COMPLETED  # unchanged


def test_state_machine_endpoints_require_website_admin(
    client: TestClient, seed_auth, db_session: Session
):
    ticket = _seed_ticket(db_session)
    # No bearer — every endpoint rejects.
    for path in ("complete", "reopen", "unarchive"):
        resp = client.post(
            f"/api/v1/admin/cms/contact-messages/{ticket.id}/{path}"
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# List filter
# ---------------------------------------------------------------------------


def test_list_filters_by_status(
    client: TestClient, seed_auth, db_session: Session
):
    pending = _seed_ticket(db_session, status=CONTACT_STATUS_PENDING_ADMIN)
    open_ticket = _seed_ticket(db_session, status=CONTACT_STATUS_OPEN)
    completed = _seed_ticket(db_session, status=CONTACT_STATUS_COMPLETED)

    headers = _login_website(client, seed_auth)

    # Single status
    r = client.get(
        "/api/v1/admin/cms/contact-messages?status=pending_admin",
        headers=headers,
    )
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()}
    assert pending.id in ids
    assert open_ticket.id not in ids
    assert completed.id not in ids

    # Multi
    r = client.get(
        "/api/v1/admin/cms/contact-messages?status=pending_admin,open",
        headers=headers,
    )
    ids = {row["id"] for row in r.json()}
    assert pending.id in ids
    assert open_ticket.id in ids
    assert completed.id not in ids


# ---------------------------------------------------------------------------
# Manual poll endpoint
# ---------------------------------------------------------------------------


def test_manual_poll_when_disabled_returns_friendly_payload(
    client: TestClient, seed_auth, monkeypatch
):
    """Polling with IMAP disabled should return 200 + ``enabled=false``.

    The admin UI should be able to render a one-line "enable IMAP in
    env" message without dealing with an error toast.
    """
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(
        settings, "contact_inbound_enabled", False, raising=False
    )

    headers = _login_website(client, seed_auth)
    resp = client.post(
        "/api/v1/admin/cms/contact-inbox/poll", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is False
    assert body["fetched"] == 0
    assert body["error"]
