"""Identity + header helpers for the contact ticket flow."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.cms import ContactMessage
from app.services.contact_threading import (
    THREAD_HEADER_NAME,
    build_message_id,
    build_outbound_headers,
    extract_ticket_from_subject,
    format_reply_subject,
    generate_thread_token,
    generate_ticket_number,
    parse_thread_token_from_message_id,
)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class TestTicketNumber:
    def test_first_ticket_of_the_day(self, db_session):
        ticket = generate_ticket_number(
            db_session, now=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        )
        assert ticket == "PUG-CNT-20260601-0001"

    def test_sequence_increments_within_the_day(self, db_session):
        # Seed two existing rows for 2026-06-01 so the next number is 0003.
        for n in (1, 2):
            db_session.add(
                ContactMessage(
                    name=f"Existing {n}",
                    email=f"x{n}@example.com",
                    message="prior",
                    ticket_number=f"PUG-CNT-20260601-{n:04d}",
                    thread_token=generate_thread_token(),
                    last_message_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                )
            )
        db_session.flush()

        ticket = generate_ticket_number(
            db_session, now=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        )
        assert ticket == "PUG-CNT-20260601-0003"

    def test_sequence_resets_per_day(self, db_session):
        # Yesterday's rows shouldn't affect today's counter.
        db_session.add(
            ContactMessage(
                name="Yesterday",
                email="y@example.com",
                message="yesterday",
                ticket_number="PUG-CNT-20260531-0042",
                thread_token=generate_thread_token(),
                last_message_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
            )
        )
        db_session.flush()

        ticket = generate_ticket_number(
            db_session, now=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        )
        assert ticket == "PUG-CNT-20260601-0001"


class TestThreadToken:
    def test_unique_per_call(self):
        seen = {generate_thread_token() for _ in range(20)}
        assert len(seen) == 20

    def test_url_safe_no_padding(self):
        token = generate_thread_token()
        # token_urlsafe never includes /, +, or = padding.
        assert "/" not in token and "+" not in token and "=" not in token
        assert len(token) >= 30


# ---------------------------------------------------------------------------
# Message-ID
# ---------------------------------------------------------------------------


class TestMessageId:
    def test_round_trip_token(self):
        token = "AAA-bbb_ccc"
        msg_id = build_message_id(token, domain="example.com")
        assert msg_id.startswith("<contact-AAA-bbb_ccc-")
        assert msg_id.endswith("@example.com>")
        recovered = parse_thread_token_from_message_id(msg_id)
        assert recovered == token

    def test_external_message_id_returns_none(self):
        assert (
            parse_thread_token_from_message_id("<random-12345@gmail.com>")
            is None
        )
        assert parse_thread_token_from_message_id("") is None
        assert parse_thread_token_from_message_id(None) is None  # type: ignore[arg-type]

    def test_uniqueness_within_same_second(self):
        token = generate_thread_token()
        ids = {build_message_id(token, domain="ex.com") for _ in range(20)}
        assert len(ids) == 20


# ---------------------------------------------------------------------------
# Outbound headers
# ---------------------------------------------------------------------------


class TestOutboundHeaders:
    def test_first_reply_no_in_reply_to(self):
        h = build_outbound_headers(
            thread_token="tok", in_reply_to=None, domain="ex.com"
        )
        assert h["Message-ID"].startswith("<contact-tok-")
        assert h[THREAD_HEADER_NAME] == "tok"
        assert "In-Reply-To" not in h
        assert "References" not in h

    def test_second_reply_chains_references(self):
        h = build_outbound_headers(
            thread_token="tok",
            in_reply_to="<customer-1@gmail.com>",
            references=["<contact-tok-1@pug.local>"],
            domain="ex.com",
        )
        assert h["In-Reply-To"] == "<customer-1@gmail.com>"
        # The chain should include both the existing reference and the
        # in_reply_to value at the end.
        assert h["References"] == (
            "<contact-tok-1@pug.local> <customer-1@gmail.com>"
        )

    def test_in_reply_to_not_duplicated_when_already_in_references(self):
        h = build_outbound_headers(
            thread_token="tok",
            in_reply_to="<a@x>",
            references=["<a@x>"],
            domain="ex.com",
        )
        assert h["References"] == "<a@x>"


# ---------------------------------------------------------------------------
# Subject helpers
# ---------------------------------------------------------------------------


class TestSubject:
    def test_appends_ticket_marker(self):
        assert (
            format_reply_subject("Pricing question", "PUG-CNT-20260601-0001")
            == "Re: Pricing question [PUG-CNT-20260601-0001]"
        )

    def test_doesnt_duplicate_ticket_marker(self):
        s = "Re: Pricing question [PUG-CNT-20260601-0001]"
        assert format_reply_subject(s, "PUG-CNT-20260601-0001") == s

    def test_doesnt_prefix_re_twice(self):
        assert (
            format_reply_subject("Re: hello", "PUG-CNT-20260601-0001")
            == "Re: hello [PUG-CNT-20260601-0001]"
        )

    def test_falls_back_when_subject_empty(self):
        out = format_reply_subject(None, "PUG-CNT-X-1")
        assert "Your enquiry" in out
        assert "[PUG-CNT-X-1]" in out

    @pytest.mark.parametrize(
        "subject,expected",
        [
            ("Re: hi [PUG-CNT-20260601-0001]", "PUG-CNT-20260601-0001"),
            ("[pug-cnt-20260601-0001] Re: hi", "PUG-CNT-20260601-0001"),
            ("plain subject without ticket", None),
            ("", None),
            (None, None),
        ],
    )
    def test_extract_ticket(self, subject, expected):
        assert extract_ticket_from_subject(subject) == expected
