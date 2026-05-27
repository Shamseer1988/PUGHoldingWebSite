"""Database backup + restore endpoints for the admin panel.

Locked behind ``require_superuser`` — these are the only operations in
the API that can wipe the entire database, so they sit above the normal
"system scope" admin tier. Every successful or failed call writes an
audit-log row so we can answer "who ran that restore at 03:00".

UX flow (mirrored in the React page at /admin/backup):

  1. ``GET  /admin/backup/info``     — Lets the UI confirm DB name +
                                        pg_dump availability before
                                        showing the action buttons.
  2. ``POST /admin/backup/download`` — Generates a fresh pg_dump on the
                                        fly and streams it to the client.
                                        Nothing is kept server-side.
  3. ``POST /admin/backup/restore``  — Uploads a .dump file, validates
                                        it, takes a pre-restore safety
                                        backup of the live DB, then runs
                                        pg_restore in a single
                                        transaction.
  4. ``GET  /admin/backup/safety``   — Lists pre-restore safety backups
                                        still on disk (7-day retention).
  5. ``GET  /admin/backup/safety/{name}`` — Download a specific safety
                                            backup so it can be retained
                                            off-server.
  6. ``DELETE /admin/backup/safety/{name}`` — Manually drop a safety
                                              backup once it's no longer
                                              needed.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_superuser
from app.core.database import get_db
from app.core.rate_limit import rate_limit_backup
from app.models.auth import SCOPE_SYSTEM, User
from app.services.audit_log import record_audit
from app.services.db_backup import (
    BackupError,
    MAX_RESTORE_BYTES,
    PG_DUMP_MAGIC,
    is_postgres,
    is_safe_safety_filename,
    list_safety_backups,
    make_backup_filename,
    resolve_connection,
    run_pg_dump,
    run_pg_restore,
    safety_backup_dir,
    tools_available,
    validate_dump_header,
)


router = APIRouter(
    prefix="/admin/backup",
    tags=["Admin - Database Backup"],
    dependencies=[Depends(require_superuser)],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _audit(
    db: Session,
    actor: User,
    request: Request,
    *,
    action: str,
    details: Optional[dict] = None,
) -> None:
    ctx = get_request_context(request)
    target_id: Optional[str] = None
    if is_postgres():
        try:
            target_id = resolve_connection().database
        except BackupError:
            target_id = None
    record_audit(
        db,
        action=action,
        actor_id=actor.id,
        actor_email=actor.email,
        scope=SCOPE_SYSTEM,
        target_type="database",
        target_id=target_id,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details,
        commit=True,
    )


def _require_postgres() -> None:
    """Reject the call if the active DB isn't Postgres (e.g. test SQLite)."""
    if not is_postgres():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Database backup + restore is only available on PostgreSQL. "
                "The active database is not a PostgreSQL instance."
            ),
        )


def _require_tools() -> None:
    if not tools_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "pg_dump / pg_restore are not installed on the server. "
                "Install the PostgreSQL client utilities to use this feature."
            ),
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/info")
def backup_info(
    actor: User = Depends(require_superuser),  # noqa: ARG001 — guard only
) -> dict:
    """Connection + tooling status so the UI knows what to show.

    Never leaks the DB password. The host is returned so the operator
    can sanity-check which environment they're about to back up.
    """
    if not is_postgres():
        return {
            "is_postgres": False,
            "tools_available": False,
            "database_name": None,
            "host": None,
            "port": None,
            "max_restore_mb": MAX_RESTORE_BYTES // (1024 * 1024),
        }
    try:
        cfg = resolve_connection()
    except BackupError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "is_postgres": True,
        "tools_available": tools_available(),
        "database_name": cfg.database,
        "host": cfg.host,
        "port": int(cfg.port),
        "max_restore_mb": MAX_RESTORE_BYTES // (1024 * 1024),
    }


@router.post("/download", dependencies=[Depends(rate_limit_backup)])
def download_backup(
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_superuser),
) -> StreamingResponse:
    """Run pg_dump and stream the resulting .dump file to the caller.

    The dump is written to a temp file, then streamed back chunk by
    chunk. The temp file is deleted after the response body has been
    fully sent.
    """
    _require_postgres()
    _require_tools()

    tmpdir = Path(tempfile.mkdtemp(prefix="pug_backup_"))
    target = tmpdir / make_backup_filename()
    try:
        run_pg_dump(target)
    except BackupError as exc:
        shutil.rmtree(tmpdir, ignore_errors=True)
        _audit(
            db,
            actor,
            request,
            action="admin.database.backup.failed",
            details={"error": str(exc)[:800]},
        )
        raise HTTPException(status_code=500, detail=str(exc))

    size = target.stat().st_size
    _audit(
        db,
        actor,
        request,
        action="admin.database.backup.download",
        details={"filename": target.name, "size_bytes": size},
    )

    def _iter():
        try:
            with open(target, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return StreamingResponse(
        _iter(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{target.name}"',
            "Content-Length": str(size),
            "X-Backup-Filename": target.name,
            # The backup body is a full snapshot of the live DB; no
            # cache anywhere — proxy, browser, or CDN — should ever
            # hold it.
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            # Disable Nginx's internal proxy buffering so the stream
            # flushes promptly on multi-hundred-MB dumps.
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/restore",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_backup)],
)
def restore_backup(
    request: Request,
    file: UploadFile = File(..., description="pg_dump custom-format (.dump) file"),
    confirm_db_name: str = Form(
        ...,
        description=(
            "Must exactly match the live database name. The UI requires "
            "the operator to type this in before the Restore button is "
            "enabled — this is the final destructive-action gate."
        ),
    ),
    db: Session = Depends(get_db),
    actor: User = Depends(require_superuser),
) -> dict:
    """Restore the active database from an uploaded pg_dump file.

    Order of operations:

      1. Confirm the active DB is Postgres + tools are installed.
      2. Confirm ``confirm_db_name`` matches the live DB name verbatim.
      3. Stream the upload to a temp file, enforcing a hard size cap.
      4. Reject the upload if the magic header isn't ``PGDMP``.
      5. Take an automatic pre-restore safety backup of the live DB,
         saved to ``{upload_dir}/_db_safety_backups/`` so the operator
         can roll back from the /admin/backup UI if needed.
      6. Run ``pg_restore --clean --if-exists --single-transaction``.
         If this fails the DB rolls back to its pre-restore state
         (single-transaction guarantee) and the safety file is still on
         disk as a belt-and-suspenders.
    """
    _require_postgres()
    _require_tools()

    try:
        cfg = resolve_connection()
    except BackupError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Tolerant compare: both sides stripped so a stray trailing space
    # in the confirmation textbox doesn't bounce a legitimate restore.
    if (confirm_db_name or "").strip() != cfg.database.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Confirmation text does not match the live database name "
                f"('{cfg.database}'). Restore aborted."
            ),
        )

    tmpdir = Path(tempfile.mkdtemp(prefix="pug_restore_"))
    upload_path = tmpdir / "upload.dump"
    safety_path = safety_backup_dir() / make_backup_filename(prefix="safety")

    try:
        # --- 1. Stream upload to disk, capped at MAX_RESTORE_BYTES ---
        # We use the synchronous ``file.file`` SpooledTemporaryFile API
        # rather than ``await file.read(...)`` because this endpoint is
        # ``def`` (not async). Running blocking pg_restore on the event
        # loop would freeze every other request for the duration.
        total = 0
        upload_stream = file.file
        with open(upload_path, "wb") as out:
            while True:
                chunk = upload_stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RESTORE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"Uploaded backup exceeds the "
                            f"{MAX_RESTORE_BYTES // (1024 * 1024)} MB limit."
                        ),
                    )
                out.write(chunk)

        if total == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        # --- 2. Magic-header validation ---
        with open(upload_path, "rb") as f:
            head = f.read(len(PG_DUMP_MAGIC))
        try:
            validate_dump_header(head)
        except BackupError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        # --- 3. Pre-restore safety backup ---
        try:
            run_pg_dump(safety_path)
        except BackupError as exc:
            _audit(
                db,
                actor,
                request,
                action="admin.database.restore.failed",
                details={
                    "phase": "pre_restore_safety_backup",
                    "uploaded_size_bytes": total,
                    "uploaded_filename": file.filename,
                    "error": str(exc)[:800],
                },
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "Pre-restore safety backup failed; restore aborted to "
                    f"avoid data loss. Underlying error: {exc}"
                ),
            )

        # --- 4. The actual restore (atomic via --single-transaction) ---
        try:
            run_pg_restore(upload_path)
        except BackupError as exc:
            _audit(
                db,
                actor,
                request,
                action="admin.database.restore.failed",
                details={
                    "phase": "pg_restore",
                    "uploaded_size_bytes": total,
                    "uploaded_filename": file.filename,
                    "safety_backup": safety_path.name,
                    "error": str(exc)[:1200],
                },
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Restore failed and was rolled back. A safety backup of "
                    f"the pre-restore state is available as "
                    f"'{safety_path.name}'. Error: {exc}"
                ),
            )

        _audit(
            db,
            actor,
            request,
            action="admin.database.restore.success",
            details={
                "uploaded_size_bytes": total,
                "uploaded_filename": file.filename,
                "safety_backup": safety_path.name,
            },
        )

        return {
            "ok": True,
            "database_name": cfg.database,
            "uploaded_size_bytes": total,
            "safety_backup_filename": safety_path.name,
            "message": (
                "Restore complete. A safety backup of the prior database "
                f"state was saved as '{safety_path.name}'. Download it "
                "from the Safety backups list below if you want to retain "
                "it off-server."
            ),
        }
    finally:
        # The uploaded file goes; the safety backup stays in the safety
        # directory (its lifecycle is handled by the 7-day pruner).
        shutil.rmtree(tmpdir, ignore_errors=True)


@router.get("/safety")
def safety_list(
    actor: User = Depends(require_superuser),  # noqa: ARG001 — guard only
) -> dict:
    """List safety backups still on disk (auto-prunes anything > 7 days)."""
    return {"backups": list_safety_backups()}


@router.get("/safety/{filename}")
def safety_download(
    filename: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_superuser),
) -> StreamingResponse:
    """Stream a specific safety backup back to the operator."""
    if not is_safe_safety_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid backup filename.")
    path = safety_backup_dir() / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Safety backup not found.")

    size = path.stat().st_size
    _audit(
        db,
        actor,
        request,
        action="admin.database.backup.safety_download",
        details={"filename": filename, "size_bytes": size},
    )

    def _iter():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(64 * 1024)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        _iter(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(size),
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete(
    "/safety/{filename}", status_code=status.HTTP_204_NO_CONTENT
)
def safety_delete(
    filename: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_superuser),
) -> Response:
    """Delete a specific safety backup."""
    if not is_safe_safety_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid backup filename.")
    path = safety_backup_dir() / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Safety backup not found.")
    path.unlink()
    _audit(
        db,
        actor,
        request,
        action="admin.database.backup.safety_delete",
        details={"filename": filename},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
