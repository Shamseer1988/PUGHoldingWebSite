"""Microsoft 365 OAuth2 client-credentials helper for IMAP.

Microsoft retired Basic Auth (and App Passwords for some tenants) on
M365 IMAP in 2023. The supported path is OAuth2 client-credentials
("AccessAsApp"):

  1. An Entra ID App Registration grants ``IMAP.AccessAsApp`` (with
     admin consent).
  2. The same SP is registered with Exchange Online via
     ``New-ServicePrincipal`` and granted ``FullAccess`` on the
     specific mailbox.
  3. The backend requests an access token from
     ``login.microsoftonline.com/{tenant}/oauth2/v2.0/token`` with
     scope ``https://outlook.office365.com/.default``.
  4. The token is sent to ``imaplib.IMAP4.authenticate('XOAUTH2', …)``
     as ``user=<upn>\\x01auth=Bearer <token>\\x01\\x01``.

Tokens are valid for ~1 hour. We cache them in-process keyed by
``(tenant_id, client_id)`` with a 60-second pre-expiry refresh window
so a poll that fires right on the boundary doesn't burn the cycle on a
stale token. Multiple workers each maintain their own cache — that's
fine because Microsoft caps token requests at a few thousand/sec per
app and we only ask once per worker per hour.

No new dependency: ``httpx`` is already pulled in by ``fastapi``'s
test client and is the project's standard HTTP client.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Tuple

import httpx


# --- Token endpoint -----------------------------------------------------------

# AAD v2.0 token endpoint. Per-tenant URL (the GUID is embedded in the
# path) — using ``common`` would lose the tenant binding and fail for
# client-credentials grants.
TOKEN_ENDPOINT_TEMPLATE = (
    "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
)

# ``/.default`` says "give me every application permission already
# consented on the app registration". For IMAP we expect that to be
# ``https://outlook.office365.com/IMAP.AccessAsApp``.
IMAP_SCOPE = "https://outlook.office365.com/.default"

# Refresh tokens this many seconds before their stated expiry so a
# poll that starts at minute 59 of the hour still ends with a valid
# token.
_REFRESH_BUFFER_SECONDS = 60


# --- Errors -------------------------------------------------------------------


class M365OAuthError(Exception):
    """Token fetch failed. Message is already operator-friendly so
    the IMAP test endpoint can render it directly."""


# --- Cache --------------------------------------------------------------------


@dataclass(frozen=True)
class _CachedToken:
    access_token: str
    # Monotonic seconds at which this token should be refreshed (real
    # expiry minus the buffer).
    refresh_at: float


_CACHE: Dict[Tuple[str, str], _CachedToken] = {}
_CACHE_LOCK = threading.Lock()


def _clock() -> float:
    """Indirection so tests can fake the clock without touching
    ``time.monotonic`` globally."""
    return time.monotonic()


# --- Public API ---------------------------------------------------------------


def fetch_imap_token(
    *,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    force_refresh: bool = False,
) -> str:
    """Return a usable Bearer token for IMAP XOAUTH2.

    Hits the in-process cache first; misses + forced refreshes go out
    to Entra ID with the client-credentials grant. The returned string
    is the raw ``access_token`` value — callers wrap it into the
    ``user=...\\x01auth=Bearer ...\\x01\\x01`` XOAUTH2 payload at
    ``client.authenticate`` time.

    Raises :class:`M365OAuthError` with a human-readable message when
    the token endpoint refuses the credentials, the tenant GUID is
    wrong, or the network blows up.
    """
    if not (tenant_id and client_id and client_secret):
        raise M365OAuthError(
            "OAuth2 requires tenant ID, client ID, and client secret — "
            "fill all three in Email Configuration → IMAP inbox."
        )

    key = (tenant_id, client_id)
    now = _clock()

    if not force_refresh:
        with _CACHE_LOCK:
            cached = _CACHE.get(key)
        if cached is not None and cached.refresh_at > now:
            return cached.access_token

    token, expires_in = _request_token(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    # Microsoft hands us seconds-from-now; convert to a refresh deadline
    # on the monotonic clock so we don't get tripped up by NTP nudges.
    refresh_at = _clock() + max(0, expires_in - _REFRESH_BUFFER_SECONDS)
    with _CACHE_LOCK:
        _CACHE[key] = _CachedToken(access_token=token, refresh_at=refresh_at)
    return token


def build_xoauth2_payload(username: str, access_token: str) -> bytes:
    """Encode the SASL XOAUTH2 auth string for ``IMAP4.authenticate``.

    imaplib calls our authobject with the server's initial challenge
    (empty bytes for XOAUTH2) and base64-encodes whatever we return
    before sending. The Microsoft-documented payload format is:

        user=<UPN>\\x01auth=Bearer <token>\\x01\\x01
    """
    payload = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
    return payload.encode("ascii")


def clear_cache() -> None:
    """Drop every cached token. Used by tests + the admin "rotate
    secret" path so a freshly-saved secret takes effect immediately."""
    with _CACHE_LOCK:
        _CACHE.clear()


# --- HTTP plumbing ------------------------------------------------------------


def _request_token(
    *, tenant_id: str, client_id: str, client_secret: str
) -> Tuple[str, int]:
    """POST to the AAD v2 token endpoint. Returns (access_token,
    expires_in_seconds). Raises :class:`M365OAuthError` with friendly
    copy on every failure path."""
    url = TOKEN_ENDPOINT_TEMPLATE.format(tenant=tenant_id)
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": IMAP_SCOPE,
    }
    try:
        response = httpx.post(url, data=data, timeout=15.0)
    except httpx.HTTPError as exc:
        raise M365OAuthError(
            f"Could not reach login.microsoftonline.com: {exc}. Check "
            f"the server's outbound network access and the tenant GUID."
        ) from exc

    if response.status_code >= 500:
        raise M365OAuthError(
            f"Microsoft token endpoint returned {response.status_code}. "
            f"This is usually transient — retry in a minute."
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise M365OAuthError(
            "Token endpoint returned a non-JSON response — check that "
            "the tenant GUID is correct (not the tenant domain)."
        ) from exc

    if response.status_code >= 400:
        # AAD error shape: {"error": "...", "error_description": "..."}
        code = body.get("error") or f"http_{response.status_code}"
        desc = body.get("error_description") or response.text
        raise M365OAuthError(_format_aad_error(code, desc))

    token = body.get("access_token")
    expires_in = body.get("expires_in")
    if not token or not isinstance(expires_in, (int, float)):
        raise M365OAuthError(
            "Token endpoint accepted the request but did not return an "
            "access_token / expires_in pair. Check that the app "
            "registration has IMAP.AccessAsApp granted with admin "
            "consent."
        )
    return token, int(expires_in)


def _format_aad_error(code: str, description: str) -> str:
    """Translate the common AAD error codes into something an admin
    can act on. Unknown codes fall through with the raw description."""
    # Strip newlines + trace IDs that AAD likes to append.
    short = description.split("Trace ID")[0].strip()
    if "AADSTS7000215" in description:
        return (
            "Microsoft rejected the client secret (AADSTS7000215). The "
            "secret value is wrong, expired, or you pasted the Secret "
            "ID instead of the Value. Generate a new secret in App "
            "registration → Certificates & secrets and copy the Value "
            "column."
        )
    if "AADSTS70011" in description or "AADSTS900023" in description:
        return (
            "Microsoft rejected the requested scope (AADSTS70011 / "
            "900023). The app registration is missing IMAP.AccessAsApp "
            "or admin consent hasn't been granted. Re-run the "
            "Microsoft Graph PowerShell consent step."
        )
    if "AADSTS700016" in description or "was not found in the directory" in description:
        return (
            "Microsoft can't find this client_id in the tenant "
            "(AADSTS700016). Double-check the App Registration ID and "
            "make sure you're using the correct tenant GUID."
        )
    if "AADSTS90002" in description:
        return (
            "Tenant GUID not recognised (AADSTS90002). Use the Tenant "
            "ID from Entra ID → Overview (a GUID), not the domain name."
        )
    if "invalid_client" in code:
        return (
            "Microsoft rejected the client credentials (invalid_client): "
            f"{short}"
        )
    return f"OAuth token request failed ({code}): {short}"


__all__ = [
    "M365OAuthError",
    "build_xoauth2_payload",
    "clear_cache",
    "fetch_imap_token",
]
