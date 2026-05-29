"""Microsoft 365 OAuth2 IMAP path — token client + XOAUTH2 dispatch.

Microsoft retired Basic Auth IMAP on M365 in 2023, so new tenants must
authenticate via OAuth2 client-credentials. Two surfaces under test:

* ``app.services.m365_oauth.fetch_imap_token`` — the token client we
  hit at every connection (and cache between connections).
* ``app.services.contact_inbound._connect`` — dispatches on
  ``auth_method`` and wraps the token into XOAUTH2.

Every test stubs the network — no real HTTPS to login.microsoft.com,
no real IMAP socket to outlook.office365.com.
"""
from __future__ import annotations

import imaplib
from dataclasses import dataclass
from typing import Any, Callable, Optional

import httpx
import pytest

from app.services import m365_oauth
from app.services.contact_inbound import (
    AUTH_OAUTH2,
    AUTH_PASSWORD,
    ResolvedImapConfig,
    _connect,
    _ImapAuthError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeResponse:
    """Minimal stub of the bits of ``httpx.Response`` we touch."""

    status_code: int
    _json: dict[str, Any] | str
    text_override: str | None = None

    def json(self) -> dict[str, Any]:
        if isinstance(self._json, str):
            raise ValueError("not json")
        return self._json

    @property
    def text(self) -> str:
        if self.text_override is not None:
            return self.text_override
        if isinstance(self._json, str):
            return self._json
        return str(self._json)


@pytest.fixture(autouse=True)
def _reset_token_cache():
    """Every test starts with an empty token cache so cache-hit tests
    don't leak state forward and miss-tests don't get free hits."""
    m365_oauth.clear_cache()
    yield
    m365_oauth.clear_cache()


def _stub_httpx_post(
    monkeypatch: pytest.MonkeyPatch,
    *,
    handler: Callable[[str, dict[str, str]], _FakeResponse],
) -> list[tuple[str, dict[str, str]]]:
    """Replace ``httpx.post`` with a recorder + dispatcher. Returns the
    list of (url, data) tuples observed so tests can assert call shape.
    """
    calls: list[tuple[str, dict[str, str]]] = []

    def _fake_post(
        url: str,
        *,
        data: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> _FakeResponse:
        calls.append((url, dict(data or {})))
        return handler(url, dict(data or {}))

    monkeypatch.setattr(m365_oauth.httpx, "post", _fake_post)
    return calls


# ---------------------------------------------------------------------------
# Token fetch — happy path + cache
# ---------------------------------------------------------------------------


class TestTokenFetch:
    def test_happy_path_returns_access_token_and_caches_it(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        calls = _stub_httpx_post(
            monkeypatch,
            handler=lambda _u, _d: _FakeResponse(
                200, {"access_token": "TOK-A", "expires_in": 3600}
            ),
        )

        first = m365_oauth.fetch_imap_token(
            tenant_id="tenant-guid",
            client_id="client-guid",
            client_secret="shh",
        )
        assert first == "TOK-A"

        # Second call within the validity window must NOT hit the
        # network — operators pay per request to AAD and we want one
        # token per worker per hour, not one per IMAP poll.
        second = m365_oauth.fetch_imap_token(
            tenant_id="tenant-guid",
            client_id="client-guid",
            client_secret="shh",
        )
        assert second == "TOK-A"
        assert len(calls) == 1

    def test_force_refresh_bypasses_cache(self, monkeypatch: pytest.MonkeyPatch):
        responses = iter(
            [
                _FakeResponse(200, {"access_token": "TOK-1", "expires_in": 3600}),
                _FakeResponse(200, {"access_token": "TOK-2", "expires_in": 3600}),
            ]
        )
        calls = _stub_httpx_post(
            monkeypatch, handler=lambda _u, _d: next(responses)
        )

        a = m365_oauth.fetch_imap_token(
            tenant_id="t", client_id="c", client_secret="s"
        )
        b = m365_oauth.fetch_imap_token(
            tenant_id="t", client_id="c", client_secret="s", force_refresh=True
        )
        assert (a, b) == ("TOK-1", "TOK-2")
        assert len(calls) == 2

    def test_expired_cache_refetches_automatically(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # First fetch with a tiny expiry that's already past the buffer.
        responses = iter(
            [
                _FakeResponse(200, {"access_token": "STALE", "expires_in": 30}),
                _FakeResponse(200, {"access_token": "FRESH", "expires_in": 3600}),
            ]
        )
        _stub_httpx_post(
            monkeypatch, handler=lambda _u, _d: next(responses)
        )

        # Pin the clock so we control when "now" passes the refresh-at.
        clock = {"t": 1_000.0}
        monkeypatch.setattr(m365_oauth, "_clock", lambda: clock["t"])

        first = m365_oauth.fetch_imap_token(
            tenant_id="t", client_id="c", client_secret="s"
        )
        assert first == "STALE"

        # Jump past the 30s lifetime; cache should miss and refetch.
        clock["t"] += 120
        second = m365_oauth.fetch_imap_token(
            tenant_id="t", client_id="c", client_secret="s"
        )
        assert second == "FRESH"

    def test_call_shape_targets_tenant_token_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        calls = _stub_httpx_post(
            monkeypatch,
            handler=lambda _u, _d: _FakeResponse(
                200, {"access_token": "T", "expires_in": 3600}
            ),
        )
        m365_oauth.fetch_imap_token(
            tenant_id="acme-tenant",
            client_id="acme-client",
            client_secret="hush",
        )
        url, data = calls[0]
        assert url == (
            "https://login.microsoftonline.com/acme-tenant/oauth2/v2.0/token"
        )
        assert data["grant_type"] == "client_credentials"
        assert data["client_id"] == "acme-client"
        assert data["client_secret"] == "hush"
        # ``/.default`` so AAD returns every consented application
        # permission — most importantly ``IMAP.AccessAsApp``.
        assert data["scope"] == "https://outlook.office365.com/.default"


# ---------------------------------------------------------------------------
# Token fetch — error mapping
# ---------------------------------------------------------------------------


class TestTokenErrorMapping:
    def test_missing_creds_raises_before_network(self):
        """Operators frequently fill two fields and forget the third —
        better to surface that locally than to make AAD do it."""
        with pytest.raises(m365_oauth.M365OAuthError) as exc:
            m365_oauth.fetch_imap_token(
                tenant_id="t", client_id="c", client_secret=""
            )
        assert "tenant ID" in str(exc.value) or "client secret" in str(exc.value)

    def test_invalid_client_secret_yields_friendly_message(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        _stub_httpx_post(
            monkeypatch,
            handler=lambda _u, _d: _FakeResponse(
                401,
                {
                    "error": "invalid_client",
                    "error_description": (
                        "AADSTS7000215: Invalid client secret provided. "
                        "Trace ID: abc"
                    ),
                },
            ),
        )
        with pytest.raises(m365_oauth.M365OAuthError) as exc:
            m365_oauth.fetch_imap_token(
                tenant_id="t", client_id="c", client_secret="wrong"
            )
        msg = str(exc.value)
        assert "AADSTS7000215" in msg
        assert "Secret ID instead of the Value" in msg

    def test_wrong_tenant_guid_yields_friendly_message(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        _stub_httpx_post(
            monkeypatch,
            handler=lambda _u, _d: _FakeResponse(
                400,
                {
                    "error": "invalid_request",
                    "error_description": (
                        "AADSTS90002: Tenant 'foo' not found. Trace ID: x"
                    ),
                },
            ),
        )
        with pytest.raises(m365_oauth.M365OAuthError) as exc:
            m365_oauth.fetch_imap_token(
                tenant_id="foo", client_id="c", client_secret="s"
            )
        msg = str(exc.value)
        assert "AADSTS90002" in msg
        assert "Tenant ID" in msg

    def test_network_failure_surfaces_as_oauth_error(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        def _boom(*_args, **_kwargs):
            raise httpx.ConnectError("getaddrinfo failed")

        monkeypatch.setattr(m365_oauth.httpx, "post", _boom)
        with pytest.raises(m365_oauth.M365OAuthError) as exc:
            m365_oauth.fetch_imap_token(
                tenant_id="t", client_id="c", client_secret="s"
            )
        assert "Could not reach login.microsoftonline.com" in str(exc.value)

    def test_non_json_response_surfaces_friendly_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # AAD returns an HTML 404 page when the tenant path is malformed
        # (e.g. someone pasted "contoso.onmicrosoft.com" instead of the
        # GUID). Make sure we don't blow up on .json() and we hint at
        # the root cause.
        _stub_httpx_post(
            monkeypatch,
            handler=lambda _u, _d: _FakeResponse(
                404, "not-json", text_override="<html>404</html>"
            ),
        )
        with pytest.raises(m365_oauth.M365OAuthError) as exc:
            m365_oauth.fetch_imap_token(
                tenant_id="contoso.onmicrosoft.com",
                client_id="c",
                client_secret="s",
            )
        assert "non-JSON" in str(exc.value)


# ---------------------------------------------------------------------------
# build_xoauth2_payload — RFC 7628 / Microsoft format
# ---------------------------------------------------------------------------


class TestXOAUTH2Payload:
    def test_format_matches_microsoft_documented_shape(self):
        payload = m365_oauth.build_xoauth2_payload(
            "support@example.com", "TOK"
        )
        # The byte 0x01 separates the user / auth / terminator
        # sections in the SASL XOAUTH2 mechanism.
        assert payload == b"user=support@example.com\x01auth=Bearer TOK\x01\x01"


# ---------------------------------------------------------------------------
# contact_inbound._connect — dispatches OAuth2 path
# ---------------------------------------------------------------------------


class _FakeImapClient:
    """Stub that records ``authenticate`` / ``login`` calls so we can
    assert which auth path ran without opening a real socket."""

    def __init__(self) -> None:
        self.authenticated_with: list[str] = []
        self.authobject_payloads: list[bytes] = []
        self.login_calls: list[tuple[str, str]] = []
        self.noop_calls = 0
        self.auth_should_fail = False
        self.welcome = b"* OK fake IMAP ready"

    # Methods imaplib.IMAP4 exposes that contact_inbound exercises
    def authenticate(self, mechanism: str, authobject) -> tuple[str, list]:
        self.authenticated_with.append(mechanism)
        payload = authobject(b"")
        self.authobject_payloads.append(payload)
        if self.auth_should_fail:
            raise imaplib.IMAP4.error("AUTHENTICATE failed.")
        return "OK", [b"auth ok"]

    def login(self, user: str, password: str) -> tuple[str, list]:
        self.login_calls.append((user, password))
        return "OK", [b"login ok"]

    def noop(self) -> tuple[str, list]:
        self.noop_calls += 1
        return "OK", [b""]


def _oauth_config(**overrides) -> ResolvedImapConfig:
    defaults: dict[str, Any] = {
        "enabled": True,
        "host": "outlook.office365.com",
        "port": 993,
        "username": "support@example.com",
        "password": None,
        "use_ssl": True,
        "folder": "INBOX",
        "processed_folder": None,
        "error_folder": None,
        "poll_interval_minutes": 5,
        "create_new_tickets": False,
        "auth_method": AUTH_OAUTH2,
        "oauth_tenant_id": "tenant-guid",
        "oauth_client_id": "client-guid",
        "oauth_client_secret": "secret-value",
    }
    defaults.update(overrides)
    return ResolvedImapConfig(**defaults)


class TestConnectOAuth2Dispatch:
    def test_oauth_method_uses_xoauth2_with_token(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Patch the IMAP socket layer so no real connection is opened.
        fake = _FakeImapClient()
        monkeypatch.setattr(
            "app.services.contact_inbound.imaplib.IMAP4_SSL",
            lambda *a, **k: fake,
        )
        # Patch the token fetcher so the IMAP code never goes to AAD.
        monkeypatch.setattr(
            "app.services.contact_inbound.fetch_imap_token",
            lambda **kwargs: "TOKEN-XYZ",
        )

        client = _connect(_oauth_config())

        assert client is fake
        assert fake.authenticated_with == ["XOAUTH2"]
        assert fake.login_calls == []  # password path NOT taken
        # The SASL payload must carry both the UPN and the bearer token
        # so the IMAP server can route to the right mailbox.
        assert fake.authobject_payloads == [
            b"user=support@example.com\x01auth=Bearer TOKEN-XYZ\x01\x01"
        ]
        # NOOP runs after auth so subsequent SELECTs don't block.
        assert fake.noop_calls == 1

    def test_password_method_still_uses_login(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        fake = _FakeImapClient()
        monkeypatch.setattr(
            "app.services.contact_inbound.imaplib.IMAP4_SSL",
            lambda *a, **k: fake,
        )
        # Sanity — patch the OAuth fetcher to blow up so a regression
        # to the OAuth path would be caught by a clear error here.
        def _should_not_be_called(**_kwargs):
            pytest.fail("OAuth fetcher invoked in password mode")

        monkeypatch.setattr(
            "app.services.contact_inbound.fetch_imap_token",
            _should_not_be_called,
        )

        config = _oauth_config(
            auth_method=AUTH_PASSWORD,
            password="app-password-16ch",
            oauth_tenant_id=None,
            oauth_client_id=None,
            oauth_client_secret=None,
        )
        _connect(config)

        assert fake.login_calls == [("support@example.com", "app-password-16ch")]
        assert fake.authenticated_with == []

    def test_oauth_token_fetch_error_surfaces_as_imap_auth_error(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        fake = _FakeImapClient()
        monkeypatch.setattr(
            "app.services.contact_inbound.imaplib.IMAP4_SSL",
            lambda *a, **k: fake,
        )

        def _boom(**_kwargs):
            raise m365_oauth.M365OAuthError(
                "AADSTS7000215: invalid client secret"
            )

        monkeypatch.setattr(
            "app.services.contact_inbound.fetch_imap_token", _boom
        )

        with pytest.raises(_ImapAuthError) as exc:
            _connect(_oauth_config())
        assert "AADSTS7000215" in str(exc.value)

    def test_token_accepted_but_mailbox_refuses_surfaces_runbook(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Token fetch works (creds are right) but the IMAP AUTHENTICATE
        comes back ``AUTHENTICATE failed.`` — that's nearly always the
        SP-not-registered or mailbox-not-granted case. The error must
        tell the operator exactly which PowerShell commands to run."""
        fake = _FakeImapClient()
        fake.auth_should_fail = True
        monkeypatch.setattr(
            "app.services.contact_inbound.imaplib.IMAP4_SSL",
            lambda *a, **k: fake,
        )
        monkeypatch.setattr(
            "app.services.contact_inbound.fetch_imap_token",
            lambda **kwargs: "TOK",
        )

        with pytest.raises(_ImapAuthError) as exc:
            _connect(_oauth_config())
        msg = str(exc.value)
        assert "New-ServicePrincipal" in msg
        assert "Add-MailboxPermission" in msg


# ---------------------------------------------------------------------------
# ResolvedImapConfig — is_complete handles both modes
# ---------------------------------------------------------------------------


class TestResolvedImapConfigCompleteness:
    def test_password_mode_complete_requires_password(self):
        cfg = _oauth_config(
            auth_method=AUTH_PASSWORD,
            password=None,
            oauth_tenant_id=None,
            oauth_client_id=None,
            oauth_client_secret=None,
        )
        assert cfg.is_complete is False
        cfg = _oauth_config(
            auth_method=AUTH_PASSWORD,
            password="pw",
            oauth_tenant_id=None,
            oauth_client_id=None,
            oauth_client_secret=None,
        )
        assert cfg.is_complete is True

    def test_oauth_mode_complete_requires_all_three_oauth_fields(self):
        cfg = _oauth_config(oauth_client_secret=None)
        assert cfg.is_complete is False
        cfg = _oauth_config()
        assert cfg.is_complete is True

    def test_is_ready_couples_to_enabled_flag(self):
        cfg = _oauth_config(enabled=False)
        assert cfg.is_ready is False
        assert cfg.is_complete is True  # enabled flag is independent
