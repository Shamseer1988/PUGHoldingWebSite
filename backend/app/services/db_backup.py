"""PostgreSQL backup + restore helpers.

Thin wrapper around ``pg_dump`` / ``pg_restore`` that:

  * Reads DB connection parameters from the application settings (the
    same ones the SQLAlchemy engine uses).
  * Streams the database password to ``pg_dump`` / ``pg_restore`` via
    the ``PGPASSWORD`` env var, never as a command-line argument
    (so the password never appears in ``ps`` output).
  * Validates uploaded restore files against the pg_dump custom-format
    magic header so a stray text file can't accidentally blow up the DB.
  * Maintains a small server-side directory of automatic "pre-restore
    safety backups" with a 7-day retention so a botched restore can be
    rolled back without losing data.

The endpoint layer (``app/api/endpoints/admin_backup.py``) is what
enforces the superuser guard + audit logging; this module is pure
plumbing and is intentionally agnostic about HTTP.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from app.core.config import get_settings


# pg_dump custom-format files start with the 5-byte magic header
# ``b"PGDMP"`` followed by a version block. We use this to reject
# uploaded files that aren't really pg_dump output before we hand them
# to ``pg_restore``.
PG_DUMP_MAGIC: bytes = b"PGDMP"

# Maximum size we'll accept for an uploaded restore file. Big enough for
# a realistic ATS database (the largest tables here are CV blob refs +
# audit log, both modest), small enough that a hostile upload can't
# fill the disk.
MAX_RESTORE_BYTES: int = 500 * 1024 * 1024  # 500 MB

# Auto-prune safety backups older than this when the endpoint lists or
# creates new ones. Lightweight pseudo-cron via "do it on next request".
SAFETY_BACKUP_RETENTION = timedelta(days=7)

# Timeouts for the subprocess calls. pg_dump on a ~1 GB database
# completes in well under a minute over a local socket; we still give
# generous headroom for very large databases.
PG_DUMP_TIMEOUT_SEC = 1800   # 30 min
PG_RESTORE_TIMEOUT_SEC = 1800  # 30 min


class BackupError(RuntimeError):
    """Raised when pg_dump / pg_restore fail, or validation rejects a file."""


@dataclass(frozen=True)
class DbConnection:
    """Resolved Postgres connection parameters."""

    user: str
    password: Optional[str]
    host: str
    port: str
    database: str


# ---------------------------------------------------------------------------
# Connection + capability probes
# ---------------------------------------------------------------------------


def is_postgres() -> bool:
    """True if the configured database URL points at PostgreSQL."""
    settings = get_settings()
    if settings.database_url:
        return settings.database_url.lower().startswith(
            ("postgres://", "postgresql://", "postgresql+")
        )
    # Falling through to the per-field config means Postgres by definition
    # — the field set only exists for Postgres.
    return True


def tools_available() -> bool:
    """True if pg_dump + pg_restore are on the PATH."""
    return bool(shutil.which("pg_dump") and shutil.which("pg_restore"))


def resolve_connection() -> DbConnection:
    """Build a :class:`DbConnection` from the active settings."""
    settings = get_settings()
    if settings.database_url:
        # SQLAlchemy URLs may include a driver suffix like
        # ``postgresql+psycopg2://`` — strip it before urlparse so the
        # hostname is recognised correctly.
        raw = settings.database_url
        if "+" in raw.split("://", 1)[0]:
            scheme, rest = raw.split("://", 1)
            raw = f"{scheme.split('+', 1)[0]}://{rest}"
        parsed = urlparse(raw)
        if not parsed.hostname or not parsed.path:
            raise BackupError(
                "DATABASE_URL is set but missing host or database path; "
                "cannot determine Postgres connection details."
            )
        return DbConnection(
            user=unquote(parsed.username or ""),
            password=unquote(parsed.password) if parsed.password else None,
            host=parsed.hostname,
            port=str(parsed.port or 5432),
            database=parsed.path.lstrip("/"),
        )
    return DbConnection(
        user=settings.postgres_user,
        password=settings.postgres_password or None,
        host=settings.postgres_host,
        port=str(settings.postgres_port),
        database=settings.postgres_db,
    )


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------


def make_backup_filename(prefix: str = "pug_backup") -> str:
    """Produce a timestamped backup filename of the form
    ``{prefix}_{dbname}_YYYYMMDD_HHMMSS.dump`` (UTC)."""
    cfg = resolve_connection()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{cfg.database}_{ts}.dump"


def safety_backup_dir() -> Path:
    """Directory where automatic pre-restore safety backups are kept."""
    settings = get_settings()
    path = Path(settings.upload_dir) / "_db_safety_backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_safe_safety_filename(name: str) -> bool:
    """Guard against path-traversal when an admin downloads a safety
    backup by filename. We refuse anything containing path separators
    or that resolves outside the safety directory."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return False
    if not name.endswith(".dump"):
        return False
    return True


def list_safety_backups() -> list[dict]:
    """List all current safety backups, newest first. Auto-prunes any
    file older than :data:`SAFETY_BACKUP_RETENTION`."""
    cutoff = datetime.now(timezone.utc) - SAFETY_BACKUP_RETENTION
    out: list[dict] = []
    for f in sorted(safety_backup_dir().iterdir(), reverse=True):
        if not f.is_file() or not f.name.endswith(".dump"):
            continue
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            try:
                f.unlink()
            except OSError:
                pass
            continue
        out.append(
            {
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "created_at": mtime.isoformat(),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_dump_header(blob: bytes) -> None:
    """Reject anything that isn't a pg_dump custom-format file."""
    if not blob.startswith(PG_DUMP_MAGIC):
        raise BackupError(
            "Uploaded file does not appear to be a pg_dump custom-format "
            "(.dump) file. Refusing to restore so we don't corrupt the "
            "live database."
        )


# ---------------------------------------------------------------------------
# pg_dump / pg_restore wrappers
# ---------------------------------------------------------------------------


def _env_with_pgpassword(cfg: DbConnection) -> dict[str, str]:
    env = os.environ.copy()
    if cfg.password:
        env["PGPASSWORD"] = cfg.password
    return env


def run_pg_dump(target_path: Path) -> None:
    """Run ``pg_dump --format=custom`` and write the result to
    ``target_path``. Raises :class:`BackupError` on any non-zero exit."""
    if not tools_available():
        raise BackupError(
            "pg_dump is not available on the server. Install postgresql-client."
        )
    cfg = resolve_connection()
    cmd = [
        "pg_dump",
        "--host", cfg.host,
        "--port", cfg.port,
        "--username", cfg.user,
        "--dbname", cfg.database,
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file", str(target_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            env=_env_with_pgpassword(cfg),
            capture_output=True,
            timeout=PG_DUMP_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BackupError(
            f"pg_dump timed out after {PG_DUMP_TIMEOUT_SEC}s"
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or b"").decode(errors="replace")[:1500]
        raise BackupError(f"pg_dump failed (rc={result.returncode}): {stderr}")


def run_pg_restore(source_path: Path) -> None:
    """Restore the live DB from a pg_dump custom-format file.

    Uses ``--clean --if-exists`` so a non-empty target is overwritten,
    and ``--single-transaction`` so a partial failure rolls the DB back
    to its pre-restore state instead of leaving it half-applied.

    Sets ``PGOPTIONS=-c lock_timeout=30000`` so if another connection
    (most commonly: our own FastAPI worker's connection pool) is still
    holding locks on the tables we're trying to drop, pg_restore
    surfaces a clean error after 30 seconds instead of blocking
    indefinitely. The caller is expected to dispose the SQLAlchemy
    engine before invoking this — see admin_backup.restore_backup.
    """
    if not tools_available():
        raise BackupError(
            "pg_restore is not available on the server. Install postgresql-client."
        )
    cfg = resolve_connection()
    cmd = [
        "pg_restore",
        "--host", cfg.host,
        "--port", cfg.port,
        "--username", cfg.user,
        "--dbname", cfg.database,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--single-transaction",
        str(source_path),
    ]
    env = _env_with_pgpassword(cfg)
    # 30s lock_timeout — turns "stuck waiting forever" into a fast,
    # diagnosable failure that names the conflicting connection.
    env["PGOPTIONS"] = "-c lock_timeout=30000 -c statement_timeout=0"
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            timeout=PG_RESTORE_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BackupError(
            f"pg_restore timed out after {PG_RESTORE_TIMEOUT_SEC}s"
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or b"").decode(errors="replace")[:1500]
        raise BackupError(
            f"pg_restore failed (rc={result.returncode}): {stderr}"
        )


__all__ = [
    "BackupError",
    "DbConnection",
    "MAX_RESTORE_BYTES",
    "PG_DUMP_MAGIC",
    "SAFETY_BACKUP_RETENTION",
    "is_postgres",
    "is_safe_safety_filename",
    "list_safety_backups",
    "make_backup_filename",
    "resolve_connection",
    "run_pg_dump",
    "run_pg_restore",
    "safety_backup_dir",
    "tools_available",
    "validate_dump_header",
]
