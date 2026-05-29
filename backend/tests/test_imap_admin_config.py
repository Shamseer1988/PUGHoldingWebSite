"""Admin IMAP configuration — saved on the EmailSetting row,
tested through ``POST /api/v1/admin/email-settings/imap-test``.

We don't hit a real IMAP server; instead we monkeypatch
``imaplib.IMAP4_SSL`` with a fake so the test exercises the full
resolve→connect→login→select→list path and asserts the friendly
error wrapper formats every transport failure as actionable text.
"""
from __future__ import annotations

import imaplib
import socket
import ssl
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from app.models.email_settings import EmailSetting
from app.services import contact_inbound
from app.services.email import EmailService


ADMIN_LOGIN = "/api/v1/admin/auth/login"
SETTINGS_PATH = "/api/v1/admin/email-settings"


def _login_super(client: TestClient, password: str) -> dict[str, str]:
    r = client.post(
        ADMIN_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _save_imap(client: TestClient, headers: dict, **fields) -> dict:
    """PUT a subset of IMAP fields and return the refreshed row."""
    r = client.put(SETTINGS_PATH, json=fields, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Fakes for imaplib.IMAP4_SSL
# ---------------------------------------------------------------------------


class _FakeIMAP:
    """Drop-in replacement for ``imaplib.IMAP4_SSL`` covering just the
    methods the poller + test endpoint call."""

    welcome = b"* OK Fake IMAP ready."

    def __init__(self, *_args, **_kwargs):
        self._login_ok = True
        self._select_ok = True
        self._select_count = 3
        self._folders = [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren) "/" "Processed"',
        ]

    # imaplib API used by our code
    def starttls(self, _ctx):  # pragma: no cover — SSL only test paths
        pass

    def login(self, user, password):
        if not self._login_ok:
            raise imaplib.IMAP4.error("AUTHENTICATE failed.")
        return ("OK", [b"Authenticated"])

    def noop(self):
        return ("OK", [b"NOOP completed."])

    def select(self, folder, readonly=False):
        if not self._select_ok:
            raise imaplib.IMAP4.error(f"NO Mailbox does not exist: {folder}")
        return ("OK", [str(self._select_count).encode()])

    def list(self):
        return ("OK", self._folders)

    def uid(self, *_args, **_kwargs):
        return ("OK", [])

    def close(self):
        pass

    def logout(self):
        return ("BYE", [])


@pytest.fixture
def fake_imap(monkeypatch):
    """Swap the IMAP4_SSL *constructor only* (not the class) so
    ``imaplib.IMAP4.error`` stays resolvable inside the service code's
    ``except`` clauses. Yields a single fake instance whose flags
    individual tests can flip mid-test (login_ok, select_ok, …)."""
    instance = _FakeIMAP()

    def factory(*args, **kwargs):
        return instance

    monkeypatch.setattr(imaplib, "IMAP4_SSL", factory)
    return instance


# ---------------------------------------------------------------------------
# Save flow
# ---------------------------------------------------------------------------


def test_save_imap_fields_persists_to_db(
    client: TestClient, seed_auth, db_session
):
    headers = _login_super(client, seed_auth["password"])

    body = _save_imap(
        client,
        headers,
        imap_enabled=True,
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="support@example.com",
        imap_password="hunter2",
        imap_use_ssl=True,
        imap_folder="INBOX",
        imap_processed_folder="Processed",
        imap_error_folder="Errors",
        imap_poll_interval_minutes=10,
        imap_create_new_tickets=False,
    )

    assert body["imap_enabled"] is True
    assert body["imap_host"] == "imap.example.com"
    assert body["imap_port"] == 993
    assert body["imap_folder"] == "INBOX"
    assert body["imap_processed_folder"] == "Processed"
    assert body["has_imap_password"] is True
    assert body["imap_poll_interval_minutes"] == 10
    # Password is encrypted — never returned in the response.
    assert "imap_password" not in body
    # DB column stores a Fernet token, not the plaintext.
    setting = db_session.get(EmailSetting, 1)
    assert setting.imap_password_encrypted is not None
    assert setting.imap_password_encrypted != "hunter2"


def test_blank_imap_password_keeps_existing_value(
    client: TestClient, seed_auth, db_session
):
    headers = _login_super(client, seed_auth["password"])
    _save_imap(
        client, headers,
        imap_host="imap.example.com",
        imap_username="user@example.com",
        imap_password="initial-pass",
    )

    setting = db_session.get(EmailSetting, 1)
    original_token = setting.imap_password_encrypted
    assert original_token

    # Update something else with an empty password — token must not change.
    body = _save_imap(client, headers, imap_password="", imap_folder="Mail")
    assert body["imap_folder"] == "Mail"
    assert body["has_imap_password"] is True

    db_session.expire_all()
    setting = db_session.get(EmailSetting, 1)
    assert setting.imap_password_encrypted == original_token
    assert setting.imap_folder == "Mail"


# ---------------------------------------------------------------------------
# Test endpoint — happy path
# ---------------------------------------------------------------------------


def test_imap_test_succeeds_with_saved_creds(
    client: TestClient, seed_auth, fake_imap
):
    headers = _login_super(client, seed_auth["password"])
    _save_imap(
        client, headers,
        imap_enabled=True,
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="support@example.com",
        imap_password="pass",
        imap_use_ssl=True,
        imap_folder="INBOX",
    )

    r = client.post(f"{SETTINGS_PATH}/imap-test", json={}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert "INBOX" in body["message"]
    assert body["selected_message_count"] == 3
    # The list() call surfaces sibling folders to help the admin
    # spot typos in their folder name.
    assert "INBOX" in body["folders_sampled"]
    assert "Processed" in body["folders_sampled"]

    # And last_imap_test_* is persisted on the row.
    state = client.get(SETTINGS_PATH, headers=headers).json()
    assert state["last_imap_test_status"] == "success"
    assert state["last_imap_test_at"] is not None


def test_imap_test_uses_override_password_without_saving(
    client: TestClient, seed_auth, fake_imap, db_session
):
    """Admin can verify a freshly-typed password before saving so a
    bad copy/paste doesn't overwrite the working credential."""
    headers = _login_super(client, seed_auth["password"])
    _save_imap(
        client, headers,
        imap_enabled=True,
        imap_host="imap.example.com",
        imap_username="support@example.com",
        imap_password="saved",
        imap_use_ssl=True,
    )
    saved_token = db_session.get(
        EmailSetting, 1
    ).imap_password_encrypted

    r = client.post(
        f"{SETTINGS_PATH}/imap-test",
        json={"imap_password": "typed-but-not-saved"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["success"] is True
    # Stored password is untouched.
    assert (
        db_session.get(EmailSetting, 1).imap_password_encrypted
        == saved_token
    )


# ---------------------------------------------------------------------------
# Test endpoint — failure modes report actionable messages
# ---------------------------------------------------------------------------


def test_imap_test_missing_fields_is_friendly(
    client: TestClient, seed_auth
):
    """No host/username/password → reject before opening a socket."""
    headers = _login_super(client, seed_auth["password"])
    r = client.post(f"{SETTINGS_PATH}/imap-test", json={}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    # Should call out what's missing.
    assert "host" in body["message"].lower()


def test_imap_test_auth_failure_microsoft_message(
    client: TestClient, seed_auth, fake_imap
):
    """Outlook hosts get a Microsoft-specific hint about App Passwords."""
    headers = _login_super(client, seed_auth["password"])
    _save_imap(
        client, headers,
        imap_enabled=True,
        imap_host="outlook.office365.com",
        imap_port=993,
        imap_username="support@example.com",
        imap_password="wrong-pass",
        imap_use_ssl=True,
    )
    # Flip the fake to reject login on this run.
    fake_imap._login_ok = False

    r = client.post(f"{SETTINGS_PATH}/imap-test", json={}, headers=headers)
    body = r.json()
    assert body["success"] is False
    msg = body["message"].lower()
    assert "microsoft 365" in msg
    assert "app password" in msg or "set-casmailbox" in msg


def test_imap_test_auth_failure_generic_provider(
    client: TestClient, seed_auth, fake_imap
):
    """Non-Outlook hosts get a generic but still actionable message."""
    headers = _login_super(client, seed_auth["password"])
    _save_imap(
        client, headers,
        imap_enabled=True,
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_username="support@example.com",
        imap_password="wrong",
        imap_use_ssl=True,
    )
    fake_imap._login_ok = False

    r = client.post(f"{SETTINGS_PATH}/imap-test", json={}, headers=headers)
    body = r.json()
    assert body["success"] is False
    assert "login refused" in body["message"].lower()
    assert "imap.gmail.com" in body["message"]


def test_imap_test_select_failure_lists_available_folders(
    client: TestClient, seed_auth, fake_imap
):
    """If the folder doesn't exist, surface the LIST results so the
    admin can correct the name without re-running the test."""
    headers = _login_super(client, seed_auth["password"])
    _save_imap(
        client, headers,
        imap_enabled=True,
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="support@example.com",
        imap_password="pass",
        imap_use_ssl=True,
        imap_folder="DoesNotExist",
    )
    fake_imap._select_ok = False

    r = client.post(f"{SETTINGS_PATH}/imap-test", json={}, headers=headers)
    body = r.json()
    assert body["success"] is False
    assert "select" in body["message"].lower()
    # Folders from list() are exposed for context.
    assert any("INBOX" in f for f in body["folders_sampled"])


def test_imap_test_dns_failure_is_friendly(
    client: TestClient, seed_auth, monkeypatch
):
    headers = _login_super(client, seed_auth["password"])
    _save_imap(
        client, headers,
        imap_enabled=True,
        imap_host="no-such-host.invalid",
        imap_port=993,
        imap_username="user@example.com",
        imap_password="pass",
        imap_use_ssl=True,
    )

    def boom(*_a, **_kw):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", boom)

    r = client.post(f"{SETTINGS_PATH}/imap-test", json={}, headers=headers)
    body = r.json()
    assert body["success"] is False
    assert "dns" in body["message"].lower()
    assert "no-such-host.invalid" in body["message"]


def test_imap_test_ssl_failure_is_friendly(
    client: TestClient, seed_auth, monkeypatch
):
    headers = _login_super(client, seed_auth["password"])
    _save_imap(
        client, headers,
        imap_enabled=True,
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="user@example.com",
        imap_password="pass",
        imap_use_ssl=True,
    )

    def boom(*_a, **_kw):
        raise ssl.SSLError("WRONG_VERSION_NUMBER")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", boom)

    r = client.post(f"{SETTINGS_PATH}/imap-test", json={}, headers=headers)
    body = r.json()
    assert body["success"] is False
    assert "tls" in body["message"].lower() or "ssl" in body["message"].lower()


# ---------------------------------------------------------------------------
# Resolved config — DB beats env
# ---------------------------------------------------------------------------


def test_resolve_imap_config_db_overrides_env(
    client: TestClient, seed_auth, db_session, monkeypatch
):
    """When both DB and env are populated, DB wins."""
    from app.core import config as core_config

    monkeypatch.setattr(
        core_config.get_settings(),
        "contact_inbound_host",
        "env.example.com",
        raising=False,
    )
    monkeypatch.setattr(
        core_config.get_settings(),
        "contact_inbound_username",
        "env-user",
        raising=False,
    )

    headers = _login_super(client, seed_auth["password"])
    _save_imap(
        client, headers,
        imap_enabled=True,
        imap_host="db.example.com",
        imap_username="db-user",
        imap_password="db-pass",
    )

    cfg = contact_inbound.resolve_imap_config(db_session)
    assert cfg.host == "db.example.com"
    assert cfg.username == "db-user"
    assert cfg.password == "db-pass"


def test_resolve_imap_config_falls_back_to_env(
    client: TestClient, seed_auth, db_session, monkeypatch
):
    """When the row has empty IMAP columns we fall back to env vars
    so an existing env-driven install still works after the migration."""
    from app.core import config as core_config

    monkeypatch.setattr(
        core_config.get_settings(),
        "contact_inbound_host",
        "env.example.com",
        raising=False,
    )
    monkeypatch.setattr(
        core_config.get_settings(),
        "contact_inbound_username",
        "env-user",
        raising=False,
    )
    monkeypatch.setattr(
        core_config.get_settings(),
        "contact_inbound_password",
        "env-pass",
        raising=False,
    )

    # No DB-side save — the row from get_or_create_settings exists but
    # has NULL IMAP columns.
    EmailService.get_or_create_settings(db_session)
    db_session.commit()

    cfg = contact_inbound.resolve_imap_config(db_session)
    assert cfg.host == "env.example.com"
    assert cfg.username == "env-user"
    assert cfg.password == "env-pass"


def test_poll_inbox_reports_friendly_error_when_unset(
    client: TestClient, seed_auth, db_session, monkeypatch
):
    """poll_inbox should surface a specific actionable string when
    IMAP is enabled but credentials are missing — the same string
    the admin sees in the toast after clicking "Check inbox now"."""
    from app.core import config as core_config

    monkeypatch.setattr(
        core_config.get_settings(),
        "contact_inbound_host",
        None,
        raising=False,
    )
    monkeypatch.setattr(
        core_config.get_settings(),
        "contact_inbound_username",
        None,
        raising=False,
    )
    monkeypatch.setattr(
        core_config.get_settings(),
        "contact_inbound_password",
        None,
        raising=False,
    )

    setting = EmailService.get_or_create_settings(db_session)
    setting.imap_enabled = True
    db_session.commit()

    summary = contact_inbound.poll_inbox(db_session)
    assert summary.enabled is True
    assert summary.error is not None
    assert "host" in summary.error.lower()
