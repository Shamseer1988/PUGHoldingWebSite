"""Optional Google Calendar / Meet integration (advanced module — phase 6).

The integration is intentionally optional. If the environment isn't
configured (no service-account JSON / no calendar id), the service
returns ``CalendarUnavailable`` and the rest of the interview flow
falls back to manual meeting-link entry.

When configured, the service creates a Calendar event with
``conferenceDataVersion=1`` and ``conferenceData.createRequest`` so
Google auto-generates a Meet link. The link is stored on
``Interview.meeting_link``; the event id is stored on
``Interview.calendar_event_id``.

For testing the service exposes :class:`StubGoogleCalendarBackend` so
tests can avoid hitting Google. In production code we use
:class:`GoogleApiBackend` which lazy-imports the Google client libraries.

NOTE: this module deliberately does **not** add ``google-api-python-client``
as a hard dependency — the import is lazy. If the package is missing
the service returns a clean ``CalendarUnavailable`` rather than
crashing the interview create endpoint.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Protocol


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result + errors
# ---------------------------------------------------------------------------


class CalendarUnavailable(Exception):
    """Raised when Google Calendar integration isn't configured/installed."""


@dataclass(frozen=True)
class MeetEventResult:
    event_id: str
    meet_link: Optional[str]
    html_link: Optional[str] = None


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------


class CalendarBackend(Protocol):
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
# Stub backend used by tests and dev environments without a Google config
# ---------------------------------------------------------------------------


class StubGoogleCalendarBackend:
    """In-memory backend so test code can exercise the flow without Google."""

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
            raise CalendarUnavailable("Stub backend marked as not configured.")
        event_id = f"stub-{uuid.uuid4()}"
        meet_link = (
            f"https://meet.google.com/stub-{event_id[5:13]}"
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
            html_link=f"https://calendar.google.com/event?eid={event_id}",
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
            raise CalendarUnavailable(f"Stub event not found: {event_id}")
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
            html_link=f"https://calendar.google.com/event?eid={event_id}",
        )

    def cancel_event(self, *, event_id: str) -> None:
        self.events.pop(event_id, None)


# ---------------------------------------------------------------------------
# Real backend (lazy-imported)
# ---------------------------------------------------------------------------


class GoogleApiBackend:
    """Production backend that talks to Google Calendar / Meet.

    Lazy-imports the Google client libraries — if they aren't installed,
    :meth:`is_configured` returns False so the interview flow falls back
    cleanly to manual mode.
    """

    def __init__(
        self,
        *,
        calendar_id: str,
        service_account_json_path: str,
        timezone_name: str = "Asia/Qatar",
    ) -> None:
        self.calendar_id = calendar_id
        self.service_account_json_path = service_account_json_path
        self.timezone_name = timezone_name
        self._service = None
        self._error: Optional[str] = None

    def _load(self):  # pragma: no cover — network/external service
        if self._service is not None:
            return self._service
        try:
            from google.oauth2 import service_account  # type: ignore[import-untyped]
            from googleapiclient.discovery import build  # type: ignore[import-untyped]
        except ImportError as exc:
            self._error = f"google-api-python-client not installed: {exc}"
            raise CalendarUnavailable(self._error) from exc

        if not os.path.exists(self.service_account_json_path):
            self._error = (
                f"Service account JSON not found: {self.service_account_json_path}"
            )
            raise CalendarUnavailable(self._error)

        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_json_path,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        self._service = build(
            "calendar", "v3", credentials=credentials, cache_discovery=False
        )
        return self._service

    def is_configured(self) -> bool:
        if not (self.calendar_id and self.service_account_json_path):
            return False
        if self._service is None:
            try:
                self._load()
            except CalendarUnavailable:
                return False
        return True

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
        service = self._load()
        body: Dict[str, Any] = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": _as_iso(start),
                "timeZone": timezone_name or self.timezone_name,
            },
            "end": {
                "dateTime": _as_iso(end),
                "timeZone": timezone_name or self.timezone_name,
            },
            "attendees": [{"email": e} for e in attendees if e],
        }
        if create_meet:
            body["conferenceData"] = {
                "createRequest": {
                    "requestId": f"pug-{uuid.uuid4()}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
        try:
            event = (
                service.events()
                .insert(
                    calendarId=self.calendar_id,
                    body=body,
                    conferenceDataVersion=1 if create_meet else 0,
                    sendUpdates="all",
                )
                .execute()
            )
        except Exception as exc:
            logger.exception("Google Calendar create_event failed")
            raise CalendarUnavailable(f"Google API error: {exc}") from exc

        meet_link = _extract_meet_link(event)
        return MeetEventResult(
            event_id=event["id"],
            meet_link=meet_link,
            html_link=event.get("htmlLink"),
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
        service = self._load()
        body: Dict[str, Any] = {}
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        if start is not None:
            body["start"] = {
                "dateTime": _as_iso(start),
                "timeZone": self.timezone_name,
            }
        if end is not None:
            body["end"] = {
                "dateTime": _as_iso(end),
                "timeZone": self.timezone_name,
            }
        if attendees is not None:
            body["attendees"] = [{"email": e} for e in attendees if e]
        try:
            event = (
                service.events()
                .patch(
                    calendarId=self.calendar_id,
                    eventId=event_id,
                    body=body,
                    sendUpdates="all",
                )
                .execute()
            )
        except Exception as exc:
            logger.exception("Google Calendar update_event failed")
            raise CalendarUnavailable(f"Google API error: {exc}") from exc

        meet_link = _extract_meet_link(event)
        return MeetEventResult(
            event_id=event["id"],
            meet_link=meet_link,
            html_link=event.get("htmlLink"),
        )

    def cancel_event(self, *, event_id: str) -> None:  # pragma: no cover
        service = self._load()
        try:
            service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id,
                sendUpdates="all",
            ).execute()
        except Exception as exc:
            logger.exception("Google Calendar cancel_event failed")
            raise CalendarUnavailable(f"Google API error: {exc}") from exc


def _as_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _extract_meet_link(event: Dict[str, Any]) -> Optional[str]:
    entry_points = (event.get("conferenceData") or {}).get("entryPoints") or []
    for ep in entry_points:
        if ep.get("entryPointType") == "video":
            return ep.get("uri")
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    return None


# ---------------------------------------------------------------------------
# Module-level helper used by endpoints
# ---------------------------------------------------------------------------


_BACKEND_OVERRIDE: Optional[CalendarBackend] = None


def set_backend(backend: Optional[CalendarBackend]) -> None:
    """Tests use this to swap in a StubGoogleCalendarBackend."""
    global _BACKEND_OVERRIDE
    _BACKEND_OVERRIDE = backend


def get_backend() -> CalendarBackend:
    """Resolve the active backend from env / override.

    Order:
    1. Anything set via :func:`set_backend` (tests).
    2. Real :class:`GoogleApiBackend` when env vars are set.
    3. Otherwise a *not-configured* stub so callers can branch cleanly.
    """
    if _BACKEND_OVERRIDE is not None:
        return _BACKEND_OVERRIDE

    enabled = os.getenv("GOOGLE_CALENDAR_ENABLED", "").lower() in {"1", "true", "yes"}
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
    json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")
    tz = os.getenv("GOOGLE_CALENDAR_TIMEZONE", "Asia/Qatar")
    if enabled and calendar_id and json_path:
        return GoogleApiBackend(
            calendar_id=calendar_id,
            service_account_json_path=json_path,
            timezone_name=tz,
        )
    return StubGoogleCalendarBackend(configured=False)


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

    Returns ``None`` (instead of raising) when Google isn't configured —
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
    except CalendarUnavailable:
        return None
