"""HR real-time notification helpers (Phase C-2).

Thin layer that builds an event payload from a freshly-committed
domain object and broadcasts it to the HR-scope room held by
``app.core.ws_manager``. Lives in ``services/`` so call sites (the
public + admin apply endpoints) import one function instead of
poking ``get_ws_manager()`` directly.

The broadcast is "best effort": a slow / disconnected client can't
roll back the HTTP response that triggered the notification. Errors
are logged but never raised — the upload / apply succeeded; nobody
seeing the live toast is strictly required.
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.logging_config import get_logger
from app.core.ws_manager import get_ws_manager
from app.models.auth import SCOPE_HR


logger = get_logger(__name__)


EVENT_CANDIDATE_APPLICATION_NEW = "candidate.application.new"


async def broadcast_candidate_application_new(
    *,
    candidate_id: int,
    candidate_name: str,
    application_id: int,
    job_title: Optional[str],
    job_slug: Optional[str],
    source: str,
) -> int:
    """Push a new-application event to every connected HR operator.

    Returns the number of sockets the event was sent to (0 when no
    HR operator has a live console open — totally fine, the message
    just doesn't go anywhere).
    """
    payload: dict[str, Any] = {
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "application_id": application_id,
        "job_title": job_title,
        "job_slug": job_slug,
        "source": source,
    }
    try:
        manager = get_ws_manager()
        sent = await manager.broadcast(
            scope=SCOPE_HR,
            event_type=EVENT_CANDIDATE_APPLICATION_NEW,
            payload=payload,
        )
        logger.info(
            "Broadcast candidate.application.new",
            application_id=application_id,
            sockets=sent,
        )
        return sent
    except Exception:  # noqa: BLE001 - never break the apply transaction
        logger.exception(
            "Failed to broadcast candidate.application.new",
            application_id=application_id,
        )
        return 0


__all__ = [
    "EVENT_CANDIDATE_APPLICATION_NEW",
    "broadcast_candidate_application_new",
]
