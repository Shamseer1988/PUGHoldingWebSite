"""Optional Microsoft Teams meeting integration (replaces phase-6 Google
Meet wiring).

The integration is intentionally optional. If the environment isn't
configured (no Azure AD app registration, no organizer mailbox), the
service returns ``None`` from :func:`create_interview_event` and the
rest of the interview flow falls back to the manually-entered
``location_or_link``.

When configured, the service calls Microsoft Graph
``POST /users/{organizer}/onlineMeetings`` with client-credentials auth
to create a real Teams meeting. The ``joinUrl`` is stored on
``Interview.meeting_link`` and the meeting object id on
``Interview.calendar_event_id`` — the field names stay generic so the
provider can be swapped again later without a schema migration.

Auth model: Azure AD app registration → ``OnlineMeetings.ReadWrite.All``
application permission → admin consent → an Application Access Policy
granted to the organizer mailbox (one-time PowerShell command — see
``docs/HR_OPERATIONAL_GUIDE.md``).

NOTE: HTTP calls go through :mod:`httpx`, which is already a hard
dependency, so there's no separate "is the SDK installed?" branch — if
the env vars are missing we return a not-configured stub backend.
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Protocol


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result + errors
# ---------------------------------------------------------------------------


class TeamsUnavailable(Exception):
    """Raised when Teams integration isn't configured / Graph call failed."""


@dataclass(frozen=True)
class MeetEventResult:
    event_id: str
    meet_link: Optional[str]
    html_link: Optional[str] = None


# ---------------------------------------------------------------------------
# Backend protocol — symmetric to the old GoogleCalendar one so callers
# don't change shape if we ever add a second provider behind the same
# helper.
# ---------------------------------------------------------------------------


class TeamsBackend(Protocol):
    def is_configured(self) -> bool: ...
    def create_event(
        self,
        *,
        summary: str,
        description: str,
        start: datetime,
        end: datetime,
        attendees: Iterable[str],
        create_meet: bool,
        timezone_name: str,
    ) -> MeetEventResult: ...
    def update_event(
        self,
        *,
        event_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        attendees: Optional[Iterable[str]] = None,
    ) -> MeetEventResult: ...
    def cancel_event(self, *, event_id: str) -> None: ...


# ---------------------------------------------------------------------------
# Stub backend used by tests and dev environments without Teams config
# ---------------------------------------------------------------------------


class StubTeamsBackend:
    """In-memory backend so test code can exercise the flow without Graph."""

    def __init__(self, configured: bool = True) -> None:
        self._configured = configured
        self.events: Dict[str, Dict[str, Any]] = {}

    def is_configured(self) -> bool:
        return self._configured

    def create_event(
        self,
        *,
        summary: str,
        description: str,
        start: datetime,
        end: datetime,
        attendees: Iterable[str],
        create_meet: bool,
        timezone_name: str,
    ) -> MeetEventResult:
        if not self._configured:
            raise TeamsUnavailable("Stub backend marked as not configured.")
        event_id = f"stub-{uuid.uuid4()}"
        meet_link = (
            f"https://teams.microsoft.com/l/meetup-join/stub/{event_id[5:13]}"
            if create_meet
            else None
        )
        self.events[event_id] = {
            "summary": summary,
            "description": description,
            "start": start,
            "end": end,
            "attendees": list(attendees),
            "meet_link": meet_link,
            "timezone": timezone_name,
        }
        return MeetEventResult(
            event_id=event_id,
            meet_link=meet_link,
            html_link=meet_link,
        )

    def update_event(
        self,
        *,
        event_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        attendees: Optional[Iterable[str]] = None,
    ) -> MeetEventResult:
        if event_id not in self.events:
            raise TeamsUnavailable(f"Stub event not found: {event_id}")
        evt = self.events[event_id]
        if summary is not None:
            evt["summary"] = summary
        if description is not None:
            evt["description"] = description
        if start is not None:
            evt["start"] = start
        if end is not None:
            evt["end"] = end
        if attendees is not None:
            evt["attendees"] = list(attendees)
        return MeetEventResult(
            event_id=event_id,
            meet_link=evt.get("meet_link"),
            html_link=evt.get("meet_link"),
        )

    def cancel_event(self, *, event_id: str) -> None:
        self.events.pop(event_id, None)


# ---------------------------------------------------------------------------
# Real backend — talks to Microsoft Graph via httpx + client_credentials
# ---------------------------------------------------------------------------


# Cache the bearer token in-process so we don't hit the token endpoint
# every time. Tokens are good for ~1 hour; we refresh 60s early.
_TOKEN_CACHE: Dict[str, Any] = {"value": None, "expires_at": 0.0}
_TOKEN_LOCK = threading.Lock()


class GraphApiBackend:
    """Production backend that talks to Microsoft Graph (Teams meetings)."""

    AUTH_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        organizer_user_id: str,
        timezone_name: str = "Asia/Qatar",
        timeout_seconds: float = 15.0,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        # Either UPN (hr@yourdomain.com) or AAD object id (guid).
        self.organizer_user_id = organizer_user_id
        self.timezone_name = timezone_name
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(
            self.tenant_id
            and self.client_id
            and self.client_secret
            and self.organizer_user_id
        )

    # ---- internal: token fetch with simple in-process cache --------------

    def _get_token(self) -> str:  # pragma: no cover - external service
        import httpx

        now = time.time()
        with _TOKEN_LOCK:
            cached = _TOKEN_CACHE.get("value")
            if cached and now < _TOKEN_CACHE.get("expires_at", 0):
                return cached

        url = self.AUTH_URL_TEMPLATE.format(tenant=self.tenant_id)
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        try:
            resp = httpx.post(url, data=data, timeout=self.timeout_seconds)
        except httpx.HTTPError as exc:
            raise TeamsUnavailable(
                f"Failed to reach Microsoft Identity endpoint: {exc}"
            ) from exc
        if resp.status_code != 200:
            raise TeamsUnavailable(
                f"Token request failed ({resp.status_code}): {resp.text[:300]}"
            )
        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            raise TeamsUnavailable("Token response did not contain access_token.")
        expires_in = int(payload.get("expires_in", 3600))
        with _TOKEN_LOCK:
            _TOKEN_CACHE["value"] = token
            _TOKEN_CACHE["expires_at"] = now + max(60, expires_in - 60)
        return token

    def _graph(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:  # pragma: no cover - external service
        import httpx

        token = self._get_token()
        url = f"{self.GRAPH_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            resp = httpx.request(
                method,
                url,
                headers=headers,
                json=body if body is not None else None,
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise TeamsUnavailable(f"Graph request error: {exc}") from exc

        if resp.status_code in (204, 200, 201):
            if resp.status_code == 204 or not resp.content:
                return {}
            return resp.json()

        # 401 with the cached token: invalidate and bubble up — caller
        # will retry on the next call after the cache clears.
        if resp.status_code == 401:
            with _TOKEN_LOCK:
                _TOKEN_CACHE["value"] = None
                _TOKEN_CACHE["expires_at"] = 0

        raise TeamsUnavailable(
            f"Graph {method} {path} failed ({resp.status_code}): "
            f"{resp.text[:500]}"
        )

    # ---- protocol methods -----------------------------------------------

    def create_event(
        self,
        *,
        summary: str,
        description: str,
        start: datetime,
        end: datetime,
        attendees: Iterable[str],
        create_meet: bool,
        timezone_name: str,
    ) -> MeetEventResult:  # pragma: no cover - external service
        # ``attendees`` and ``description`` are ignored for the
        # onlineMeetings endpoint — the API just produces a join URL.
        # The PUG branded email carries date/time/notes/Join button to
        # the candidate; calendar-side attendee invites would need the
        # ``/me/events`` endpoint (out of scope here).
        if not create_meet:
            raise TeamsUnavailable(
                "GraphApiBackend.create_event called with create_meet=False"
            )

        body = {
            "startDateTime": _as_iso_utc(start),
            "endDateTime": _as_iso_utc(end),
            "subject": summary,
        }
        meeting = self._graph(
            "POST",
            f"/users/{self.organizer_user_id}/onlineMeetings",
            body=body,
        )
        meet_link = meeting.get("joinUrl") or meeting.get("joinWebUrl")
        return MeetEventResult(
            event_id=str(meeting.get("id") or ""),
            meet_link=meet_link,
            html_link=meet_link,
        )

    def update_event(
        self,
        *,
        event_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        attendees: Optional[Iterable[str]] = None,
    ) -> MeetEventResult:  # pragma: no cover - external service
        body: Dict[str, Any] = {}
        if summary is not None:
            body["subject"] = summary
        if start is not None:
            body["startDateTime"] = _as_iso_utc(start)
        if end is not None:
            body["endDateTime"] = _as_iso_utc(end)
        if not body:
            # Nothing to update — return the current state.
            meeting = self._graph(
                "GET",
                f"/users/{self.organizer_user_id}/onlineMeetings/{event_id}",
            )
        else:
            meeting = self._graph(
                "PATCH",
                f"/users/{self.organizer_user_id}/onlineMeetings/{event_id}",
                body=body,
            )
            # PATCH returns 204 with no body in some tenants — re-GET so
            # the caller always receives a fresh joinUrl.
            if not meeting:
                meeting = self._graph(
                    "GET",
                    f"/users/{self.organizer_user_id}/onlineMeetings/{event_id}",
                )
        meet_link = meeting.get("joinUrl") or meeting.get("joinWebUrl")
        return MeetEventResult(
            event_id=str(meeting.get("id") or event_id),
            meet_link=meet_link,
            html_link=meet_link,
        )

    def cancel_event(self, *, event_id: str) -> None:  # pragma: no cover
        self._graph(
            "DELETE",
            f"/users/{self.organizer_user_id}/onlineMeetings/{event_id}",
        )


def _as_iso_utc(value: datetime) -> str:
    """Graph wants ISO 8601 UTC strings — coerce naïve to UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Module-level helper used by endpoints (signature kept identical to the
# old google_calendar_service so the endpoint diff stays minimal).
# ---------------------------------------------------------------------------


_BACKEND_OVERRIDE: Optional[TeamsBackend] = None


def set_backend(backend: Optional[TeamsBackend]) -> None:
    """Tests use this to swap in a :class:`StubTeamsBackend`."""
    global _BACKEND_OVERRIDE
    _BACKEND_OVERRIDE = backend


def get_backend() -> TeamsBackend:
    """Resolve the active backend from env / override.

    Order:
    1. Anything set via :func:`set_backend` (tests).
    2. Real :class:`GraphApiBackend` when env vars are set.
    3. Otherwise a *not-configured* stub so callers can branch cleanly.
    """
    if _BACKEND_OVERRIDE is not None:
        return _BACKEND_OVERRIDE

    enabled = os.getenv("MS_TEAMS_ENABLED", "").lower() in {"1", "true", "yes"}
    tenant_id = os.getenv("MS_TENANT_ID")
    client_id = os.getenv("MS_CLIENT_ID")
    client_secret = os.getenv("MS_CLIENT_SECRET")
    organizer = os.getenv("MS_TEAMS_ORGANIZER_USER_ID")
    tz = os.getenv("MS_TEAMS_TIMEZONE", "Asia/Qatar")
    if enabled and tenant_id and client_id and client_secret and organizer:
        return GraphApiBackend(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            organizer_user_id=organizer,
            timezone_name=tz,
        )
    return StubTeamsBackend(configured=False)


def create_interview_event(
    *,
    summary: str,
    description: str,
    start: datetime,
    duration_minutes: int,
    attendees: Iterable[str],
    create_meet: bool,
    timezone_name: str = "Asia/Qatar",
) -> Optional[MeetEventResult]:
    """High-level helper used by the interview endpoint.

    Returns ``None`` (instead of raising) when Teams isn't configured —
    callers fall back to manual ``location_or_link``.
    """
    backend = get_backend()
    if not backend.is_configured():
        return None
    end = start + timedelta(minutes=duration_minutes)
    try:
        return backend.create_event(
            summary=summary,
            description=description,
            start=start,
            end=end,
            attendees=attendees,
            create_meet=create_meet,
            timezone_name=timezone_name,
        )
    except TeamsUnavailable as exc:
        logger.warning("Teams meeting creation skipped: %s", exc)
        return None
