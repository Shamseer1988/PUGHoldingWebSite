"""IMAP UID watermark fallback for Microsoft 365.

The poller's primary strategy is the ``UNKEYWORD $PUG-Inspected``
search — non-destructive and works on every IMAP server compliant
with RFC 3501 custom flag keywords. Exchange Online silently
rejects custom keywords, so the poller falls back to UID watermark
tracking.

This file pins the fallback contract:

* When the keyword search succeeds, no watermark is touched.
* When it fails and no watermark exists yet, the next search is
  ``UNSEEN`` and the highest processed UID becomes the new
  watermark.
* On subsequent polls the search criterion is ``UID > last+1:*``
  — completely decoupled from ``\\Seen`` state so Outlook clients
  reading the mailbox can't race the poller.
* ``UIDVALIDITY`` is captured alongside the UID; if the server
  reports a different value (folder reset) we discard the
  watermark rather than silently skipping new mail forever.
* ``_fetch_message`` uses ``BODY.PEEK[]`` so the poller never
  auto-marks messages as Seen during inspection.
"""
from __future__ import annotations

import imaplib
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.email_settings import EmailSetting
from app.services import contact_inbound
from app.services.contact_inbound import (
    AUTH_PASSWORD,
    IMAP_INSPECTED_KEYWORD,
    ResolvedImapConfig,
    _fetch_message,
    _get_uidvalidity,
    _persist_uid_watermark,
    _search_uninspected,
    _STRATEGY_KEYWORD,
    _STRATEGY_UID,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(folder: str = "INBOX") -> ResolvedImapConfig:
    """Minimal in-memory config for the search helpers."""
    return ResolvedImapConfig(
        enabled=True,
        host="outlook.office365.com",
        port=993,
        username="noreply@example.com",
        password="ignored",
        use_ssl=True,
        folder=folder,
        processed_folder=None,
        error_folder=None,
        poll_interval_minutes=5,
        create_new_tickets=False,
        auth_method=AUTH_PASSWORD,
    )


class _FakeImap:
    """Capture-and-replay stub for the slice of ``imaplib.IMAP4``
    the search helpers touch.

    Each ``script`` entry is a ``(command_signature, response)``
    tuple where the signature is the search criterion the test
    expects the poller to send next.
    """

    def __init__(
        self,
        *,
        uid_search_responses: list[tuple[str, tuple[str, list]]],
        untagged_uidvalidity: bytes | None = None,
    ) -> None:
        self._uid_search_responses = list(uid_search_responses)
        self.uid_searches_received: list[str] = []
        self.untagged_responses: dict[str, list[bytes]] = {}
        if untagged_uidvalidity is not None:
            self.untagged_responses["UIDVALIDITY"] = [untagged_uidvalidity]

    def uid(self, command: str, *args: Any) -> tuple[str, list]:
        if command.lower() == "search":
            criterion = " ".join(
                a.decode() if isinstance(a, (bytes, bytearray)) else str(a)
                for a in args
                if a is not None
            )
            self.uid_searches_received.append(criterion)
            if not self._uid_search_responses:
                raise AssertionError(
                    f"Unexpected uid search: {criterion!r}; "
                    "the test ran out of scripted responses."
                )
            expected_criterion, response = self._uid_search_responses.pop(0)
            assert expected_criterion in criterion, (
                f"Search criterion mismatch: expected {expected_criterion!r}, "
                f"got {criterion!r}"
            )
            return response
        raise NotImplementedError(f"Unexpected uid command: {command!r}")


# ---------------------------------------------------------------------------
# Strategy 1 — keyword path
# ---------------------------------------------------------------------------


class TestKeywordStrategy:
    def test_keyword_search_used_when_server_accepts_it(
        self, db_session: Session
    ):
        client = _FakeImap(
            uid_search_responses=[
                (f"UNKEYWORD {IMAP_INSPECTED_KEYWORD}", ("OK", [b"5 6 7"])),
            ]
        )

        uids, strategy, uidvalidity = _search_uninspected(
            db_session, client, _config(), limit=50
        )

        assert strategy == _STRATEGY_KEYWORD
        # No UIDVALIDITY needed on the keyword path — caller skips
        # the watermark persist when ``strategy != _STRATEGY_UID``.
        assert uidvalidity is None
        assert uids == [b"5", b"6", b"7"]

    def test_keyword_path_does_not_touch_watermark_columns(
        self, db_session: Session
    ):
        row = db_session.get(EmailSetting, 1) or EmailSetting()
        row.imap_last_seen_uid = None
        row.imap_last_seen_uid_validity = None
        db_session.add(row)
        db_session.commit()

        client = _FakeImap(
            uid_search_responses=[
                (f"UNKEYWORD {IMAP_INSPECTED_KEYWORD}", ("OK", [b"100"])),
            ]
        )
        _search_uninspected(db_session, client, _config(), limit=50)

        db_session.refresh(row)
        assert row.imap_last_seen_uid is None
        assert row.imap_last_seen_uid_validity is None


# ---------------------------------------------------------------------------
# Strategy 2 — UID watermark path (Microsoft 365)
# ---------------------------------------------------------------------------


class TestUidWatermarkStrategy:
    def test_keyword_failure_falls_through_to_unseen_on_first_poll(
        self, db_session: Session
    ):
        """First M365 poll: no watermark yet → UNSEEN backfill,
        then snap a watermark for next cycle."""
        row = db_session.get(EmailSetting, 1) or EmailSetting()
        row.imap_last_seen_uid = None
        row.imap_last_seen_uid_validity = None
        db_session.add(row)
        db_session.commit()

        client = _FakeImap(
            uid_search_responses=[
                # Keyword rejected by server.
                (
                    f"UNKEYWORD {IMAP_INSPECTED_KEYWORD}",
                    ("BAD", [b"keyword not supported"]),
                ),
                # Fallback to UNSEEN — picks up 12 and 9 unread.
                ("UNSEEN", ("OK", [b"12 9"])),
            ],
            untagged_uidvalidity=b"987654321",
        )

        uids, strategy, uidvalidity = _search_uninspected(
            db_session, client, _config(), limit=50
        )

        assert strategy == _STRATEGY_UID
        assert uidvalidity == 987654321
        # Sorted ascending so the watermark advances monotonically.
        assert uids == [b"9", b"12"]

    def test_subsequent_polls_use_uid_greater_than_watermark(
        self, db_session: Session
    ):
        """The whole point of this fix — once a watermark exists,
        the search criterion stops depending on \\Seen entirely."""
        row = db_session.get(EmailSetting, 1) or EmailSetting()
        row.imap_last_seen_uid = 42
        row.imap_last_seen_uid_validity = 100
        db_session.add(row)
        db_session.commit()

        client = _FakeImap(
            uid_search_responses=[
                (
                    f"UNKEYWORD {IMAP_INSPECTED_KEYWORD}",
                    ("BAD", [b"keyword not supported"]),
                ),
                # Watermark is 42 — search must look for UID 43:*.
                ("UID 43:*", ("OK", [b"55 50 60"])),
            ],
            untagged_uidvalidity=b"100",
        )

        uids, strategy, uidvalidity = _search_uninspected(
            db_session, client, _config(), limit=50
        )

        assert strategy == _STRATEGY_UID
        assert uidvalidity == 100
        # Ascending — watermark advances oldest-first.
        assert uids == [b"50", b"55", b"60"]

    def test_uidvalidity_change_resets_watermark_for_one_cycle(
        self, db_session: Session
    ):
        """RFC 3501 § 2.3.1.1 — UIDVALIDITY change means every UID
        is now meaningless. Fall back to UNSEEN once."""
        row = db_session.get(EmailSetting, 1) or EmailSetting()
        row.imap_last_seen_uid = 999
        row.imap_last_seen_uid_validity = 100
        db_session.add(row)
        db_session.commit()

        client = _FakeImap(
            uid_search_responses=[
                (
                    f"UNKEYWORD {IMAP_INSPECTED_KEYWORD}",
                    ("BAD", [b"nope"]),
                ),
                # New UIDVALIDITY (200 != stored 100). The stored UID
                # 999 is meaningless against the new sequence, so we
                # MUST fall back to UNSEEN rather than send
                # ``UID 1000:*``.
                ("UNSEEN", ("OK", [b"1"])),
            ],
            untagged_uidvalidity=b"200",
        )

        uids, strategy, uidvalidity = _search_uninspected(
            db_session, client, _config(), limit=50
        )

        assert strategy == _STRATEGY_UID
        assert uidvalidity == 200
        assert uids == [b"1"]

    def test_empty_search_returns_empty_list_with_strategy_intact(
        self, db_session: Session
    ):
        """``fetched=0`` is normal when there's no new mail. The
        strategy + UIDVALIDITY still get returned so the caller can
        persist the current state if it wants to."""
        row = db_session.get(EmailSetting, 1) or EmailSetting()
        row.imap_last_seen_uid = 100
        row.imap_last_seen_uid_validity = 50
        db_session.add(row)
        db_session.commit()

        client = _FakeImap(
            uid_search_responses=[
                (
                    f"UNKEYWORD {IMAP_INSPECTED_KEYWORD}",
                    ("BAD", [b""]),
                ),
                ("UID 101:*", ("OK", [None])),
            ],
            untagged_uidvalidity=b"50",
        )

        uids, strategy, _ = _search_uninspected(
            db_session, client, _config(), limit=50
        )
        assert uids == []
        assert strategy == _STRATEGY_UID

    def test_limit_caps_a_huge_backfill_but_returns_oldest_first(
        self, db_session: Session
    ):
        """Watermark advances monotonically — the next poll will
        pick up where this one stops."""
        row = db_session.get(EmailSetting, 1) or EmailSetting()
        row.imap_last_seen_uid = None
        row.imap_last_seen_uid_validity = None
        db_session.add(row)
        db_session.commit()

        # Server returns 200 UIDs in arbitrary order.
        big_uids = b" ".join(
            str(u).encode() for u in [50, 1, 200, 100, 2, 3, 150, 75]
        )
        client = _FakeImap(
            uid_search_responses=[
                (f"UNKEYWORD {IMAP_INSPECTED_KEYWORD}", ("BAD", [b""])),
                ("UNSEEN", ("OK", [big_uids])),
            ],
            untagged_uidvalidity=b"7",
        )

        uids, _strategy, _validity = _search_uninspected(
            db_session, client, _config(), limit=3
        )
        # Oldest-first cap of 3 — so 1, 2, 3 (not 50, 75, 100).
        assert uids == [b"1", b"2", b"3"]


# ---------------------------------------------------------------------------
# UIDVALIDITY parsing
# ---------------------------------------------------------------------------


class TestUidvalidityRead:
    def test_reads_integer_from_select_untagged_responses(self):
        client = _FakeImap(uid_search_responses=[])
        client.untagged_responses["UIDVALIDITY"] = [b"123456789"]
        assert _get_uidvalidity(client) == 123456789

    def test_returns_none_when_server_omitted_uidvalidity(self):
        client = _FakeImap(uid_search_responses=[])
        assert _get_uidvalidity(client) is None

    def test_returns_none_on_garbage_value(self):
        client = _FakeImap(uid_search_responses=[])
        client.untagged_responses["UIDVALIDITY"] = [b"not-an-int"]
        assert _get_uidvalidity(client) is None


# ---------------------------------------------------------------------------
# Watermark persistence
# ---------------------------------------------------------------------------


class TestWatermarkPersistence:
    def test_writes_both_columns_when_changed(self, db_session: Session):
        row = db_session.get(EmailSetting, 1) or EmailSetting()
        row.imap_last_seen_uid = None
        row.imap_last_seen_uid_validity = None
        db_session.add(row)
        db_session.commit()

        _persist_uid_watermark(db_session, max_uid=42, uidvalidity=7)

        db_session.refresh(row)
        assert row.imap_last_seen_uid == 42
        assert row.imap_last_seen_uid_validity == 7

    def test_uidvalidity_none_does_not_clear_existing_value(
        self, db_session: Session
    ):
        """Edge case — server that omitted UIDVALIDITY on one
        cycle shouldn't wipe a previously-good value."""
        row = db_session.get(EmailSetting, 1) or EmailSetting()
        row.imap_last_seen_uid = 5
        row.imap_last_seen_uid_validity = 100
        db_session.add(row)
        db_session.commit()

        _persist_uid_watermark(db_session, max_uid=10, uidvalidity=None)

        db_session.refresh(row)
        assert row.imap_last_seen_uid == 10
        assert row.imap_last_seen_uid_validity == 100


# ---------------------------------------------------------------------------
# Non-destructive fetch
# ---------------------------------------------------------------------------


class TestFetchUsesBodyPeek:
    def test_fetch_message_uses_body_peek_not_rfc822(self):
        """``BODY.PEEK[]`` is the non-destructive variant — explicitly
        spelled out in RFC 3501 § 6.4.5. ``RFC822`` would set
        ``\\Seen`` as a side-effect, defeating the whole point of
        keeping non-ticket mail in its original Read/Unread state."""
        client = MagicMock()
        client.uid.return_value = (
            "OK",
            [(b"1 (UID 1 BODY[] {3}", b"hi\n"), b")"],
        )

        msg = _fetch_message(client, b"1")
        assert msg is not None

        # The single call to ``uid`` must have used BODY.PEEK[],
        # not RFC822. This pins the contract so a future "small
        # refactor" can't accidentally re-introduce the auto-Seen
        # side-effect.
        client.uid.assert_called_once()
        args = client.uid.call_args.args
        assert args[0] == "fetch"
        assert args[1] == b"1"
        assert "BODY.PEEK[]" in args[2]
        assert "RFC822" not in args[2]
