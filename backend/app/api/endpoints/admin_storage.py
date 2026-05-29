"""Admin storage health endpoint (Phase A-5).

Companion to ``app/services/storage.py``. Reports which backend is
active (local vs R2), the configured values, and — when R2 is
active — performs a small upload / delete round-trip so an operator
can confirm the credentials match the bucket without dropping into
the AWS CLI.

Gated on ``require_superuser`` so only system admins (the same
people who hold R2 credentials) can run it. The round-trip writes
under a ``_healthcheck/`` prefix that the public-CMS endpoints
never serve, and deletes the test object once read-back succeeds,
so nothing accumulates in the bucket.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import require_superuser
from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.models.auth import User
from app.services.storage import (
    LocalStorageBackend,
    R2StorageBackend,
    get_storage,
)


logger = get_logger(__name__)


router = APIRouter(
    prefix="/admin/storage",
    tags=["Admin - Storage"],
    dependencies=[Depends(require_superuser)],
)


class RoundtripResult(BaseModel):
    ok: bool
    upload_key: Optional[str] = None
    elapsed_ms: Optional[int] = None
    error: Optional[str] = None


class StorageHealthResponse(BaseModel):
    backend: str  # "local" or "r2"
    configured: bool
    bucket: Optional[str] = None
    endpoint_url: Optional[str] = None
    public_base_url: Optional[str] = None
    roundtrip: Optional[RoundtripResult] = None


_PROBE_BODY = b"ok"
_PROBE_CONTENT_TYPE = "text/plain"
_PROBE_PREFIX = "_healthcheck"


def _probe_key() -> str:
    """Per-invocation key so concurrent checks don't race each other."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%f")
    return f"{_PROBE_PREFIX}/{now}.txt"


async def _r2_roundtrip(backend: R2StorageBackend) -> RoundtripResult:
    """Upload → read → delete. Returns a structured result; never raises.

    The boto3 ``head_object`` after upload confirms the object is
    actually visible (a successful PUT alone doesn't prove the
    bucket policy / credentials are correct for reads). ``delete``
    cleans up unconditionally so a failure mid-test doesn't leave
    junk behind.
    """
    key = _probe_key()
    started = time.monotonic()
    try:
        await backend.upload(
            key=key, data=_PROBE_BODY, content_type=_PROBE_CONTENT_TYPE
        )
        # Confirm the object is readable by ``head``-ing it. boto3
        # is blocking so hop to a thread the same way upload does.
        await asyncio.to_thread(
            backend._client.head_object,  # type: ignore[attr-defined]
            Bucket=backend.bucket,
            Key=key,
        )
    except Exception as exc:  # noqa: BLE001 — surface the message
        # Best-effort cleanup even on failure (the PUT may have
        # succeeded before the HEAD blew up).
        try:
            await backend.delete(key)
        except Exception:  # noqa: BLE001
            pass
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.exception("R2 roundtrip failed", key=key, elapsed_ms=elapsed_ms)
        return RoundtripResult(
            ok=False,
            upload_key=key,
            elapsed_ms=elapsed_ms,
            error=str(exc)[:300],
        )

    try:
        await backend.delete(key)
    except Exception as exc:  # noqa: BLE001 — non-fatal
        logger.warning(
            "R2 roundtrip cleanup failed", key=key, error=str(exc)
        )

    elapsed_ms = int((time.monotonic() - started) * 1000)
    logger.info("R2 roundtrip ok", key=key, elapsed_ms=elapsed_ms)
    return RoundtripResult(ok=True, upload_key=key, elapsed_ms=elapsed_ms)


@router.get("/health", response_model=StorageHealthResponse)
async def storage_health(
    _user: User = Depends(require_superuser),
) -> StorageHealthResponse:
    """Storage backend health probe.

    For ``local`` backend: reports the configuration only (a
    write-to-disk probe would just confirm the filesystem works,
    which has its own monitoring).

    For ``r2`` backend: performs an end-to-end ``upload → head →
    delete`` round-trip and returns the result.
    """
    settings = get_settings()
    backend = get_storage()

    if isinstance(backend, R2StorageBackend):
        roundtrip = await _r2_roundtrip(backend)
        return StorageHealthResponse(
            backend="r2",
            configured=True,
            bucket=settings.r2_bucket_name,
            endpoint_url=settings.r2_endpoint_url,
            public_base_url=settings.r2_public_base_url,
            roundtrip=roundtrip,
        )

    # Local backend
    return StorageHealthResponse(
        backend="local",
        configured=settings.r2_configured,
        bucket=None,
        endpoint_url=None,
        public_base_url=None,
        roundtrip=None,
    )
