"""Pluggable object storage (Phase A-6).

Provides a single ``StorageBackend`` interface that the rest of the
backend uploads against, with two concrete implementations:

* ``R2StorageBackend`` — pushes objects to a Cloudflare R2 bucket via
  the S3-compatible API (boto3). Active when every required ``R2_*``
  env var is set.

* ``LocalStorageBackend`` — writes to the existing
  ``settings.upload_dir`` on disk and returns a relative URL the
  FastAPI ``StaticFiles`` mount already serves. Identical to the
  pre-R2 behaviour, so unconfigured installs (dev, CI, a fresh
  staging environment) keep working without a cloud account.

``get_storage()`` is the factory the API layer calls. It selects the
right backend at process startup and caches the choice — so an
operator who flips ``R2_*`` env vars must restart the process for
the change to take effect, the same as for any other Settings value.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Protocol

from app.core.config import Settings, get_settings
from app.core.logging_config import get_logger


logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class StorageBackend(Protocol):
    """The minimum surface every storage backend must expose.

    Both methods are ``async`` so the API layer can ``await`` without
    blocking the FastAPI event loop. Sync implementations (boto3, the
    local-disk writer) hop to a worker thread internally via
    ``asyncio.to_thread``.
    """

    async def upload(
        self, key: str, data: bytes, content_type: Optional[str]
    ) -> str:
        """Persist ``data`` under ``key`` and return the public URL.

        ``content_type`` is hinted into the storage backend so the
        edge serves a correct ``Content-Type`` header — important for
        images (so browsers render instead of downloading) and PDFs
        (so the inline viewer fires).
        """
        ...

    async def delete(self, key: str) -> None:
        """Remove ``key`` from the backend. No-op on missing keys."""
        ...


# ---------------------------------------------------------------------------
# Local-disk backend (preserved fallback)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LocalStorageBackend:
    """Write to ``settings.upload_dir`` on disk.

    The returned URL is relative (``/api/v1/uploads/<key>``) so the
    existing ``StaticFiles`` mount at ``/api/v1/uploads`` serves the
    file without any further wiring. This is the pre-R2 behaviour
    distilled into the new interface.
    """

    root: Path
    public_url_prefix: str = "/api/v1/uploads"

    async def upload(
        self, key: str, data: bytes, content_type: Optional[str]
    ) -> str:
        return await asyncio.to_thread(self._upload_sync, key, data)

    def _upload_sync(self, key: str, data: bytes) -> str:
        # ``Path("/tmp/x") / "/foo"`` discards the left side because
        # the operand is "absolute" — strip the leading slash before
        # joining or the file lands at the filesystem root instead of
        # under our upload dir.
        clean_key = key.lstrip("/")
        target = self.root / clean_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f"{self.public_url_prefix.rstrip('/')}/{clean_key}"

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._delete_sync, key)

    def _delete_sync(self, key: str) -> None:
        target = self.root / key.lstrip("/")
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover — disk-level rarities
            logger.warning("LocalStorageBackend delete failed", key=key, error=str(exc))


# ---------------------------------------------------------------------------
# Cloudflare R2 backend (S3 over boto3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class R2StorageBackend:
    """Upload to a Cloudflare R2 bucket via the S3-compatible API.

    boto3's ``put_object`` is blocking so we always run it on a
    thread. Construct via :func:`get_storage`; never instantiate
    directly inside a request handler — the boto3 client is
    relatively heavy and is meant to be reused for the lifetime of
    the process.
    """

    bucket: str
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    public_base_url: Optional[str]
    # boto3 client cached on the dataclass via a default-factory
    # property; declared as ``_client`` so the dataclass treats it as
    # part of the structural equality, even though we set it via
    # ``object.__setattr__`` because the dataclass is frozen.
    _client: object = None  # populated in __post_init__

    def __post_init__(self) -> None:
        import boto3  # imported lazily so dev envs without boto3 still import config
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=Config(
                signature_version="s3v4",
                # R2 doesn't use regions in the AWS sense; sticking
                # ``auto`` here keeps boto3 from prepending a
                # location to the URL.
                region_name="auto",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        # Frozen dataclass — set via object.__setattr__.
        object.__setattr__(self, "_client", client)

    # --- public surface -----------------------------------------------------

    async def upload(
        self, key: str, data: bytes, content_type: Optional[str]
    ) -> str:
        await asyncio.to_thread(
            self._client.put_object,  # type: ignore[attr-defined]
            Bucket=self.bucket,
            Key=key.lstrip("/"),
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )
        return self._public_url(key)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object,  # type: ignore[attr-defined]
            Bucket=self.bucket,
            Key=key.lstrip("/"),
        )

    # --- helpers ------------------------------------------------------------

    def _public_url(self, key: str) -> str:
        """Construct the URL the frontend should fetch from.

        Prefers the custom domain the operator wired in step 4 of
        Phase A-5 (``R2_PUBLIC_BASE_URL``). Falls back to the long
        ``<account>.r2.cloudflarestorage.com/<bucket>/<key>`` form
        when no custom domain is set.
        """
        clean_key = key.lstrip("/")
        if self.public_base_url:
            return f"{self.public_base_url.rstrip('/')}/{clean_key}"
        return f"{self.endpoint_url.rstrip('/')}/{self.bucket}/{clean_key}"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _build_storage(settings: Settings) -> StorageBackend:
    """Pure constructor used by the cached factory and by tests."""
    if settings.r2_configured:
        logger.info(
            "Storage backend: R2",
            bucket=settings.r2_bucket_name,
            endpoint=settings.r2_endpoint_url,
            custom_domain=bool(settings.r2_public_base_url),
        )
        return R2StorageBackend(
            bucket=settings.r2_bucket_name,
            # ``r2_configured`` guarantees the three values below are set;
            # the assertions narrow the Optional[str] for type checkers.
            endpoint_url=settings.r2_endpoint_url or "",
            access_key_id=settings.r2_access_key_id or "",
            secret_access_key=settings.r2_secret_access_key or "",
            public_base_url=settings.r2_public_base_url,
        )
    logger.info(
        "Storage backend: local disk",
        upload_dir=settings.upload_dir,
    )
    return LocalStorageBackend(root=Path(settings.upload_dir))


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    """Return the process-wide storage backend, instantiating it once.

    Cached so the (relatively heavy) boto3 client is built exactly
    once per process. An operator who flips R2_* env vars must
    restart the process for the change to take effect — same as
    for any other ``Settings`` value.
    """
    return _build_storage(get_settings())


__all__ = [
    "LocalStorageBackend",
    "R2StorageBackend",
    "StorageBackend",
    "get_storage",
]
