"""Tests for the Email Configuration admin page and contact reply flow.

The SMTP transport is monkey-patched via ``EmailService._send`` so the
suite never opens a network connection. Two helpers below stub the
send to either succeed or raise the SMTP error we want to exercise.
"""
from __future__ import annotations

import smtplib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret, encrypt_secret
from app.models.cms import ContactMessage, ContactReply as ContactReplyModel
from app.models.email_settings import EmailSetting, TEST_STATUS_SUCCESS, TEST_STATUS_FAILED


ADMIN_LOGIN = "/api/v1/admin/auth/login"
EMAIL = "/api/v1/admin/email-settings"
CMS = "/api/v1/admin/cms"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login_super(client: TestClient, seed_auth) -> dict[str, str]:
    response = client.post(
        ADMIN_LOGIN,
        json={
            "email": "superadmin@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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


@pytest.fixture
def mock_send(monkeypatch):
    """Patch ``EmailService._send`` to a recorder that succeeds by default."""
    from app.services import email as email_module

    sent: list = []

    def fake_send(msg, config):
        sent.append({"to": msg["To"], "subject": msg["Subject"], "from": msg["From"]})

    monkeypatch.setattr(email_module.EmailService, "_send", staticmethod(fake_send))
    return sent


@pytest.fixture
def mock_send_failure(monkeypatch):
    """Patch ``EmailService._send`` to always raise SMTPAuthenticationError."""
    from app.services import email as email_module

    def boom(msg, config):
        raise smtplib.SMTPAuthenticationError(535, b"Authentication failed")

    monkeypatch.setattr(email_module.EmailService, "_send", staticmethod(boom))


# ---------------------------------------------------------------------------
# Crypto helper
# ---------------------------------------------------------------------------


def test_crypto_roundtrip():
    token = encrypt_secret("super-secret-password-123")
    assert token != "super-secret-password-123"
    assert decrypt_secret(token) == "super-secret-password-123"


def test_crypto_decrypt_empty_returns_none():
    assert decrypt_secret(None) is None
    assert decrypt_secret("") is None


def test_crypto_decrypt_invalid_token_returns_none():
    assert decrypt_secret("not-a-real-fernet-token") is None


# ---------------------------------------------------------------------------
# GET / PUT email-settings
# ---------------------------------------------------------------------------


def test_email_settings_get_creates_singleton(client, seed_auth, db_session: Session):
    headers = _login_super(client, seed_auth)
    response = client.get(EMAIL, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["email_enabled"] is False
    assert data["has_smtp_password"] is False  # env empty, DB empty
    assert "smtp_password" not in data
    assert "smtp_password_encrypted" not in data
    assert data["env_fallback_active"] is True
    assert data["last_test_status"] == "never"


def test_email_settings_requires_system_scope(client, seed_auth):
    """Website-only admin must not be able to read email config."""
    headers = _login_website(client, seed_auth)
    assert client.get(EMAIL, headers=headers).status_code == 403


def test_email_settings_requires_authentication(client, seed_auth):
    assert client.get(EMAIL).status_code == 401


def test_email_settings_update_persists_and_audits(client, seed_auth, db_session: Session):
    headers = _login_super(client, seed_auth)
    payload = {
        "email_enabled": True,
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "noreply@pug.example.com",
        "smtp_password": "Hunter2!",
        "smtp_use_tls": True,
        "smtp_use_ssl": False,
        "email_from": "noreply@pug.example.com",
        "email_from_name": "PUG Holding",
        "email_reply_to": "support@pug.example.com",
        "notification_email": "inbox@pug.example.com",
        "test_email_to": "qa@pug.example.com",
    }
    response = client.put(EMAIL, json=payload, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["email_enabled"] is True
    assert data["smtp_host"] == "smtp.example.com"
    assert data["has_smtp_password"] is True
    assert "smtp_password" not in data
    assert data["env_fallback_active"] is False


def test_email_settings_password_never_returned(client, seed_auth):
    headers = _login_super(client, seed_auth)
    client.put(EMAIL, json={"smtp_password": "Hunter2!"}, headers=headers)
    response = client.get(EMAIL, headers=headers)
    body = response.json()
    # No plaintext or encrypted password should leak in any field.
    assert "Hunter2!" not in response.text
    assert "smtp_password" not in body
    assert "smtp_password_encrypted" not in body
    assert body["has_smtp_password"] is True


def test_email_settings_blank_password_preserves_existing(
    client, seed_auth, db_session: Session
):
    headers = _login_super(client, seed_auth)
    client.put(EMAIL, json={"smtp_password": "OriginalPass!"}, headers=headers)

    setting = db_session.get(EmailSetting, 1)
    db_session.refresh(setting)
    original_token = setting.smtp_password_encrypted
    assert original_token is not None

    # Update something else without sending a new password.
    client.put(
        EMAIL,
        json={"smtp_host": "smtp.new-host.com"},
        headers=headers,
    )
    db_session.refresh(setting)
    assert setting.smtp_password_encrypted == original_token
    assert decrypt_secret(setting.smtp_password_encrypted) == "OriginalPass!"


def test_email_settings_env_fallback(client, seed_auth, db_session: Session, monkeypatch):
    """Empty DB row uses env vars for the resolved config."""
    monkeypatch.setenv("SMTP_HOST", "env-smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "env-user")
    monkeypatch.setenv("SMTP_PASSWORD", "env-pass")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "env@pug.example.com")
    # Clear the lru cache so env changes are visible.
    from app.core.config import get_settings

    get_settings.cache_clear()

    headers = _login_super(client, seed_auth)
    response = client.get(EMAIL, headers=headers)
    data = response.json()
    # The row itself is still blank; resolved env fills in the password
    # so has_smtp_password flips true.
    assert data["has_smtp_password"] is True
    assert data["env_fallback_active"] is True

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# POST test email
# ---------------------------------------------------------------------------


def _seed_send_ready_config(client: TestClient, headers: dict[str, str]) -> None:
    client.put(
        EMAIL,
        json={
            "email_enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "noreply@pug.example.com",
            "smtp_password": "Hunter2!",
            "email_from": "noreply@pug.example.com",
            "email_from_name": "PUG Holding",
        },
        headers=headers,
    )


def test_test_email_success(client, seed_auth, mock_send):
    headers = _login_super(client, seed_auth)
    _seed_send_ready_config(client, headers)

    response = client.post(
        f"{EMAIL}/test",
        json={"to_email": "qa@example.com"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "successfully" in body["message"].lower()
    assert len(mock_send) == 1
    assert mock_send[0]["to"] == "qa@example.com"

    # last_test_* fields stamped.
    after = client.get(EMAIL, headers=headers).json()
    assert after["last_test_status"] == TEST_STATUS_SUCCESS
    assert after["last_test_at"] is not None


def test_test_email_auth_failure_message(client, seed_auth, mock_send_failure):
    headers = _login_super(client, seed_auth)
    _seed_send_ready_config(client, headers)

    response = client.post(
        f"{EMAIL}/test",
        json={"to_email": "qa@example.com"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    # Friendly message — never leaks the SMTP exception class.
    assert "authentication failed" in body["message"].lower()
    assert "SMTPAuthenticationError" not in body["message"]

    after = client.get(EMAIL, headers=headers).json()
    assert after["last_test_status"] == TEST_STATUS_FAILED


def test_test_email_when_disabled_returns_friendly_message(client, seed_auth):
    headers = _login_super(client, seed_auth)
    # email_enabled stays False (default singleton).
    response = client.post(
        f"{EMAIL}/test",
        json={"to_email": "qa@example.com"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "disabled" in body["message"].lower()


# ---------------------------------------------------------------------------
# Contact reply flow (chat thread)
# ---------------------------------------------------------------------------


def _seed_inbound(db_session: Session) -> ContactMessage:
    msg = ContactMessage(
        name="Jane Visitor",
        email="jane@example.com",
        subject="Pricing question",
        message="Hi, what is the price?",
    )
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)
    return msg


def test_contact_detail_returns_inbound_only_for_new_message(
    client, seed_auth, db_session, mock_send
):
    msg = _seed_inbound(db_session)
    headers = _login_website(client, seed_auth)

    response = client.get(f"{CMS}/contact-messages/{msg.id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == msg.id
    assert len(body["replies"]) == 1
    bubble = body["replies"][0]
    assert bubble["direction"] == "inbound"
    assert bubble["sender_email"] == "jane@example.com"
    assert bubble["body"] == "Hi, what is the price?"


def test_admin_reply_sends_email_and_appends_outbound(
    client, seed_auth, db_session, mock_send
):
    msg = _seed_inbound(db_session)
    headers = _login_super(client, seed_auth)
    _seed_send_ready_config(client, headers)

    web_headers = _login_website(client, seed_auth)
    response = client.post(
        f"{CMS}/contact-messages/{msg.id}/reply",
        json={"reply_body": "Hi Jane, our price is $X."},
        headers=web_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_replied"] is True
    assert len(body["replies"]) == 2
    outbound = body["replies"][1]
    assert outbound["direction"] == "outbound"
    assert outbound["email_status"] == "sent"
    assert outbound["sent_at"] is not None
    assert outbound["recipient_email"] == "jane@example.com"
    assert outbound["subject"].lower().startswith("re:")

    # Email was actually attempted with the right recipient + subject.
    assert len(mock_send) == 1
    assert mock_send[0]["to"] == "jane@example.com"
    assert mock_send[0]["subject"].lower().startswith("re:")


def test_admin_reply_failure_keeps_body_and_marks_failed(
    client, seed_auth, db_session, mock_send_failure
):
    msg = _seed_inbound(db_session)
    super_headers = _login_super(client, seed_auth)
    _seed_send_ready_config(client, super_headers)
    headers = _login_website(client, seed_auth)

    response = client.post(
        f"{CMS}/contact-messages/{msg.id}/reply",
        json={"reply_body": "Sorry for the delay — here's the answer."},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    # Message not marked replied because the send failed.
    assert body["is_replied"] is False
    outbound = body["replies"][1]
    assert outbound["email_status"] == "failed"
    assert outbound["body"] == "Sorry for the delay — here's the answer."
    assert "authentication" in (outbound["error_message"] or "").lower()


def test_failed_reply_can_be_retried_successfully(
    client, seed_auth, db_session, monkeypatch
):
    """Retry uses the stored body; on success the message flips to replied."""
    from app.services import email as email_module

    # Phase 1: fail the first attempt.
    def fail(msg, config):
        raise smtplib.SMTPAuthenticationError(535, b"bad auth")

    monkeypatch.setattr(email_module.EmailService, "_send", staticmethod(fail))

    msg = _seed_inbound(db_session)
    super_headers = _login_super(client, seed_auth)
    _seed_send_ready_config(client, super_headers)
    headers = _login_website(client, seed_auth)
    first = client.post(
        f"{CMS}/contact-messages/{msg.id}/reply",
        json={"reply_body": "Original retry body"},
        headers=headers,
    )
    assert first.status_code == 200
    failed_reply_id = first.json()["replies"][1]["id"]

    # Phase 2: swap to a succeeding send and retry.
    sent: list = []

    def succeed(msg, config):
        sent.append(msg["To"])

    monkeypatch.setattr(email_module.EmailService, "_send", staticmethod(succeed))

    retry = client.post(
        f"{CMS}/contact-replies/{failed_reply_id}/retry",
        headers=headers,
    )
    assert retry.status_code == 200, retry.text
    body = retry.json()
    assert body["is_replied"] is True
    bubble = next(r for r in body["replies"] if r["id"] == failed_reply_id)
    assert bubble["email_status"] == "sent"
    assert bubble["error_message"] is None
    assert sent == ["jane@example.com"]


# ---------------------------------------------------------------------------
# Public contact form notification (best-effort)
# ---------------------------------------------------------------------------


def test_contact_form_submit_succeeds_even_when_notify_fails(
    client, seed_auth, monkeypatch
):
    """Visitor submission must still 201 if the admin-notify email errors."""
    super_headers = _login_super(client, seed_auth)
    _seed_send_ready_config(client, super_headers)
    client.put(
        EMAIL,
        json={"notification_email": "inbox@pug.example.com"},
        headers=super_headers,
    )

    from app.services import email as email_module

    def boom(msg, config):
        raise smtplib.SMTPConnectError(421, b"server down")

    monkeypatch.setattr(email_module.EmailService, "_send", staticmethod(boom))

    response = client.post(
        "/api/v1/public/contact",
        json={
            "name": "Visitor",
            "email": "visitor@example.com",
            "department": "sales",
            "subject": "Test",
            "message": "Hello",
        },
    )
    assert response.status_code == 201, response.text


def test_contact_form_notify_sent_when_configured(
    client, seed_auth, db_session, mock_send
):
    super_headers = _login_super(client, seed_auth)
    _seed_send_ready_config(client, super_headers)
    client.put(
        EMAIL,
        json={"notification_email": "inbox@pug.example.com"},
        headers=super_headers,
    )

    response = client.post(
        "/api/v1/public/contact",
        json={
            "name": "Notify Test",
            "email": "ping@example.com",
            "department": "sales",
            "message": "Hello",
        },
    )
    assert response.status_code == 201

    # The admin notification went to the configured address.
    assert any(s["to"] == "inbox@pug.example.com" for s in mock_send)
