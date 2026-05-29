"""IMAP relocate (MOVE / COPY+EXPUNGE / auto-create) behaviour.

The poller's ``_move_to`` helper is the file-the-processed-mail
step. Three layered strategies in order:

1. RFC 6851 ``UID MOVE`` — preferred, single round-trip.
2. ``UID COPY`` + ``STORE \\Deleted`` + ``EXPUNGE`` — pre-RFC-6851
   fallback for ancient servers.
3. Auto-create the destination + retry — recovers from the
   common "operator typed the folder name but never created it
   in OWA" mistake.

These tests stub the IMAP client to exercise each branch without
opening a real socket.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call

import imaplib
import pytest

from app.services.contact_inbound import _move_to


class _Recorder:
    """Capture-and-script stub for ``imaplib.IMAP4`` MOVE/COPY/CREATE.

    Each scripted entry is ``(verb, response)``. The fake matches
    incoming calls against the script in order, asserting the verb
    is what the test expected next.
    """

    def __init__(self, script: list[tuple[str, tuple[str, list[Any]]]]) -> None:
        self._script = list(script)
        self.calls: list[str] = []
        self.expunge_called = False

    def uid(self, command: str, *args: Any) -> tuple[str, list[Any]]:
        sig = f"{command.lower()} " + " ".join(
            a.decode() if isinstance(a, (bytes, bytearray)) else str(a)
            for a in args
        )
        self.calls.append(sig)
        if not self._script:
            raise AssertionError(
                f"Unexpected uid call: {sig!r}; ran out of scripted responses"
            )
        expected_prefix, response = self._script.pop(0)
        assert sig.startswith(expected_prefix), (
            f"Expected uid command prefix {expected_prefix!r}, got {sig!r}"
        )
        return response

    def create(self, folder: str) -> tuple[str, list[Any]]:
        sig = f"create {folder}"
        self.calls.append(sig)
        if not self._script:
            raise AssertionError(f"Unexpected create call: {sig!r}")
        expected_prefix, response = self._script.pop(0)
        assert sig.startswith(expected_prefix), (
            f"Expected create prefix {expected_prefix!r}, got {sig!r}"
        )
        return response

    def expunge(self) -> tuple[str, list[Any]]:
        self.expunge_called = True
        return "OK", [b""]


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


class TestMovePreferred:
    def test_rfc6851_move_used_when_server_accepts_it(self):
        client = _Recorder(
            script=[
                # Mark seen first (because mark_seen=True).
                ("store 7 +FLAGS (\\Seen)", ("OK", [b"7 (FLAGS (\\Seen))"])),
                # Then a single MOVE.
                ("move 7 WebContacts", ("OK", [b"[COPYUID 12 7 99]"])),
            ]
        )
        _move_to(client, b"7", "WebContacts", mark_seen=True)

        # No COPY / EXPUNGE — the MOVE atomically handled it.
        assert any(c.startswith("move ") for c in client.calls)
        assert not any(c.startswith("copy ") for c in client.calls)
        assert client.expunge_called is False


class TestCopyFallback:
    def test_falls_back_to_copy_expunge_when_move_refused(self):
        client = _Recorder(
            script=[
                ("store 7 +FLAGS (\\Seen)", ("OK", [b""])),
                # MOVE returns NO — server might not advertise RFC 6851.
                ("move 7 WebContacts", ("NO", [b"command not supported"])),
                # COPY succeeds.
                ("copy 7 WebContacts", ("OK", [b"[COPYUID 12 7 99]"])),
                # Tombstone the original.
                ("store 7 +FLAGS (\\Deleted)", ("OK", [b""])),
            ]
        )
        _move_to(client, b"7", "WebContacts", mark_seen=True)
        assert client.expunge_called is True


# ---------------------------------------------------------------------------
# Auto-create
# ---------------------------------------------------------------------------


class TestAutoCreate:
    def test_create_then_retry_move_when_destination_missing(self):
        client = _Recorder(
            script=[
                ("store 7 +FLAGS (\\Seen)", ("OK", [b""])),
                # MOVE refused — typical M365 [TRYCREATE] response when
                # the destination doesn't exist.
                (
                    "move 7 WebContacts",
                    ("NO", [b"[TRYCREATE] folder does not exist"]),
                ),
                # COPY refused for the same reason.
                (
                    "copy 7 WebContacts",
                    ("NO", [b"[TRYCREATE] folder does not exist"]),
                ),
                # CREATE succeeds.
                ("create WebContacts", ("OK", [b"CREATE completed"])),
                # Retry MOVE — now works.
                ("move 7 WebContacts", ("OK", [b"[COPYUID 12 7 99]"])),
            ]
        )
        _move_to(client, b"7", "WebContacts", mark_seen=True)

        # Final state: one CREATE happened, message relocated via
        # the second MOVE attempt.
        assert any(c == "create WebContacts" for c in client.calls)
        assert sum(1 for c in client.calls if c.startswith("move ")) == 2

    def test_create_already_exists_is_treated_as_success_then_retry(self):
        """Some servers reject CREATE on an existing folder with
        ``NO [ALREADYEXISTS]`` even though the folder is there.
        That means our earlier MOVE/COPY failed for a different
        reason — but the folder is fine to target."""
        client = _Recorder(
            script=[
                ("store 7 +FLAGS (\\Seen)", ("OK", [b""])),
                ("move 7 WebContacts", ("NO", [b"some other failure"])),
                ("copy 7 WebContacts", ("NO", [b"some other failure"])),
                (
                    "create WebContacts",
                    ("NO", [b"[ALREADYEXISTS] Mailbox already exists"]),
                ),
                # Retry MOVE — succeeds (maybe transient).
                ("move 7 WebContacts", ("OK", [b"[COPYUID 12 7 99]"])),
            ]
        )
        _move_to(client, b"7", "WebContacts", mark_seen=True)
        assert sum(1 for c in client.calls if c.startswith("move ")) == 2


# ---------------------------------------------------------------------------
# Total failure — should leave message intact + log loudly
# ---------------------------------------------------------------------------


class TestTotalFailureIsNonFatal:
    def test_does_not_raise_when_every_strategy_fails(
        self, caplog: pytest.LogCaptureFixture
    ):
        client = _Recorder(
            script=[
                ("store 7 +FLAGS (\\Seen)", ("OK", [b""])),
                ("move 7 WebContacts", ("NO", [b"refused"])),
                ("copy 7 WebContacts", ("NO", [b"refused"])),
                ("create WebContacts", ("NO", [b"refused"])),
            ]
        )
        # Must NOT raise — a stuck-in-INBOX message is still
        # workable because the UID watermark moved past it.
        _move_to(client, b"7", "WebContacts", mark_seen=True)

        # The warning must tell the operator what to check —
        # specifically that some mailboxes nest folders under INBOX.
        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "Could not relocate UID=7" in joined
        assert "WebContacts" in joined
        assert "INBOX/" in joined  # hint about nesting


# ---------------------------------------------------------------------------
# Optional mark-seen
# ---------------------------------------------------------------------------


class TestSeenFlag:
    def test_mark_seen_false_skips_the_store(self):
        client = _Recorder(
            script=[
                # No store call expected first — go straight to MOVE.
                ("move 7 WebContacts", ("OK", [b""])),
            ]
        )
        _move_to(client, b"7", "WebContacts", mark_seen=False)
        # Confirm we never tried to set \Seen.
        assert not any("Seen" in c for c in client.calls)

    def test_no_destination_folder_short_circuits(self):
        """A blank Processed folder means 'don't move' — only the
        \\Seen flag gets set so the next UNSEEN scan skips it."""
        client = _Recorder(
            script=[
                ("store 7 +FLAGS (\\Seen)", ("OK", [b""])),
            ]
        )
        _move_to(client, b"7", None, mark_seen=True)
        assert all(
            not c.startswith("move ") and not c.startswith("copy ")
            for c in client.calls
        )
