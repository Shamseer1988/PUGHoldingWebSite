"""R2 credentials smoke test (Phase A-5).

Command-line counterpart to ``GET /admin/storage/health``. Runs the
same upload → head → delete round-trip, prints a human-readable
report, exits 0 on success or 1 on failure. Designed to be wired
into deploy-time smoke tests or run ad-hoc by ops.

Usage::

    cd backend
    source .venv/bin/activate           # or .venv\\Scripts\\Activate.ps1 on Windows
    python -m app.scripts.r2_smoke_test

Exits non-zero when R2 is misconfigured or the round-trip fails —
makes it safe to chain into CI step-conditions like::

    python -m app.scripts.r2_smoke_test && systemctl restart backend
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone

from app.core.config import get_settings
from app.services.storage import (
    LocalStorageBackend,
    R2StorageBackend,
    get_storage,
)


PROBE_BODY = b"ok"
PROBE_PREFIX = "_healthcheck"


def _probe_key() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%f")
    return f"{PROBE_PREFIX}/{now}.txt"


async def _run_r2(backend: R2StorageBackend) -> int:
    settings = get_settings()
    print("R2 backend active")
    print(f"  bucket           : {settings.r2_bucket_name}")
    print(f"  endpoint_url     : {settings.r2_endpoint_url}")
    print(
        f"  public_base_url  : {settings.r2_public_base_url or '(unset — using r2.cloudflarestorage.com URLs)'}"
    )

    key = _probe_key()
    print(f"  probe key        : {key}")

    try:
        await backend.upload(key=key, data=PROBE_BODY, content_type="text/plain")
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ upload failed : {exc}")
        return 1

    try:
        await asyncio.to_thread(
            backend._client.head_object,  # type: ignore[attr-defined]
            Bucket=backend.bucket,
            Key=key,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ readback failed (head_object): {exc}")
        try:
            await backend.delete(key)
        except Exception:  # noqa: BLE001
            pass
        return 1

    try:
        await backend.delete(key)
    except Exception as exc:  # noqa: BLE001
        # Non-fatal — print but still report overall success.
        print(f"  ⚠️  cleanup warning : {exc}")

    print("  ✅ roundtrip OK   : upload + head + delete completed")
    return 0


async def _run_local(backend: LocalStorageBackend) -> int:
    settings = get_settings()
    print("Local-disk backend active (R2 not configured)")
    print(f"  upload_dir       : {settings.upload_dir}")
    print(
        f"  r2_configured    : {settings.r2_configured}  "
        "(set the four R2_* env vars + restart to activate)"
    )
    return 0


async def _main() -> int:
    backend = get_storage()
    if isinstance(backend, R2StorageBackend):
        return await _run_r2(backend)
    if isinstance(backend, LocalStorageBackend):
        return await _run_local(backend)
    print(f"Unknown backend type: {type(backend).__name__}", file=sys.stderr)
    return 1


def main() -> None:
    sys.exit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
