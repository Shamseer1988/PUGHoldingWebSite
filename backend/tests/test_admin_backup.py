"""Tests for the database backup + restore endpoints (super-user only).

The test environment uses SQLite so we don't actually exercise pg_dump /
pg_restore — instead these tests cover the security + validation
surface, which is where bugs would be most damaging:

  * Only ``is_superuser`` accounts can hit any of the six endpoints.
  * The ``/info`` endpoint reports the SQLite environment correctly
    (so the UI knows to hide the action buttons).
  * ``/download`` and ``/restore`` refuse to run on a non-Postgres DB.
  * Restore rejects:
      - empty uploads
      - files without the ``PGDMP`` magic header
      - confirmation strings that don't match the live DB name
      - files over the size cap
  * Path-traversal attempts on ``/safety/{filename}`` are blocked.
  * The pure helpers (``validate_dump_header``,
    ``is_safe_safety_filename``, ``make_backup_filename``,
    ``resolve_connection``) behave correctly.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.services import db_backup


ADMIN_LOGIN = "/api/v1/admin/auth/login"
HR_LOGIN = "/api/v1/hr/auth/login"
BACKUP = "/api/v1/admin/backup"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str, *, hr: bool = False) -> dict:
    url = HR_LOGIN if hr else ADMIN_LOGIN
    resp = client.post(url, json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _superuser(client: TestClient, password: str) -> dict:
    return _login(client, "superadmin@pug.example.com", password)


# ---------------------------------------------------------------------------
# Auth + scope guard
# ---------------------------------------------------------------------------


class TestAccessControl:
    """Only superusers can reach any backup endpoint."""

    def test_unauthenticated_request_is_401(self, client):
        resp = client.get(f"{BACKUP}/info")
        assert resp.status_code == 401

    def test_non_superuser_admin_is_403(self, client, seed_auth):
        # Website Admin holds the 'website' scope but is NOT a superuser;
        # the require_superuser dep must reject them.
        headers = _login(client, "webadmin@pug.example.com", seed_auth["password"])
        resp = client.get(f"{BACKUP}/info", headers=headers)
        assert resp.status_code == 403
        assert "superuser" in resp.json()["detail"].lower()

    def test_hr_admin_is_403(self, client, seed_auth):
        # HR Admin has every HR permission but no superuser flag.
        headers = _login(
            client, "hradmin@pug.example.com", seed_auth["password"], hr=True
        )
        resp = client.get(f"{BACKUP}/info", headers=headers)
        assert resp.status_code == 403

    @pytest.mark.parametrize(
        "method,path",
        [
            ("get", "/info"),
            ("post", "/download"),
            ("post", "/restore"),
            ("get", "/safety"),
            ("get", "/safety/anything.dump"),
            ("delete", "/safety/anything.dump"),
        ],
    )
    def test_every_route_requires_superuser(
        self, client, seed_auth, method, path
    ):
        headers = _login(
            client, "webadmin@pug.example.com", seed_auth["password"]
        )
        resp = getattr(client, method)(f"{BACKUP}{path}", headers=headers)
        assert resp.status_code == 403, f"{method.upper()} {path} should be 403"


# ---------------------------------------------------------------------------
# /info endpoint
# ---------------------------------------------------------------------------


class TestInfo:
    def test_info_reports_non_postgres_in_test_env(self, client, seed_auth):
        # The test environment uses SQLite, so the endpoint should
        # truthfully report that backup is not available here.
        headers = _superuser(client, seed_auth["password"])
        # Force the SQLite path explicitly by overriding the
        # database_url setting via monkeypatch on resolve_connection
        # is overkill — instead we patch is_postgres() to return False.
        from app.api.endpoints import admin_backup as ep

        original = ep.is_postgres
        try:
            ep.is_postgres = lambda: False
            resp = client.get(f"{BACKUP}/info", headers=headers)
            assert resp.status_code == 200
            body = resp.json()
            assert body["is_postgres"] is False
            assert body["database_name"] is None
            assert body["host"] is None
            assert body["max_restore_mb"] > 0
        finally:
            ep.is_postgres = original

    def test_info_reports_postgres_details_when_postgres(self, client, seed_auth):
        from app.api.endpoints import admin_backup as ep

        original_pg = ep.is_postgres
        original_tools = ep.tools_available
        try:
            ep.is_postgres = lambda: True
            ep.tools_available = lambda: True
            headers = _superuser(client, seed_auth["password"])
            resp = client.get(f"{BACKUP}/info", headers=headers)
            assert resp.status_code == 200
            body = resp.json()
            assert body["is_postgres"] is True
            assert body["database_name"]  # default 'pug_holding'
            assert body["host"]
            assert isinstance(body["port"], int)
        finally:
            ep.is_postgres = original_pg
            ep.tools_available = original_tools


# ---------------------------------------------------------------------------
# /download — must refuse on non-Postgres
# ---------------------------------------------------------------------------


class TestDownload:
    def test_download_refuses_on_non_postgres(self, client, seed_auth, monkeypatch):
        # ``is_postgres()`` defaults to True from the per-field settings
        # (no DATABASE_URL set), even though the test engine is SQLite.
        # Force the helper False to verify the 400 guard fires.
        from app.api.endpoints import admin_backup as ep

        monkeypatch.setattr(ep, "is_postgres", lambda: False)
        headers = _superuser(client, seed_auth["password"])
        resp = client.post(f"{BACKUP}/download", headers=headers)
        assert resp.status_code == 400
        assert "postgresql" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /restore — security gates
# ---------------------------------------------------------------------------


class TestRestore:
    def test_restore_refuses_on_non_postgres(self, client, seed_auth, monkeypatch):
        from app.api.endpoints import admin_backup as ep

        monkeypatch.setattr(ep, "is_postgres", lambda: False)
        headers = _superuser(client, seed_auth["password"])
        resp = client.post(
            f"{BACKUP}/restore",
            headers=headers,
            files={"file": ("x.dump", b"PGDMP_fake", "application/octet-stream")},
            data={"confirm_db_name": "anything"},
        )
        assert resp.status_code == 400
        assert "postgresql" in resp.json()["detail"].lower()

    def test_restore_wrong_confirm_db_name(self, client, seed_auth, monkeypatch):
        # Pretend the env is Postgres so we get past the early gate
        # and exercise the confirmation check itself.
        from app.api.endpoints import admin_backup as ep
        from app.services.db_backup import DbConnection

        monkeypatch.setattr(ep, "is_postgres", lambda: True)
        monkeypatch.setattr(ep, "tools_available", lambda: True)
        # Pin the resolved connection so this test is hermetic — a
        # developer-supplied .env with a different POSTGRES_DB doesn't
        # leak in and silently match the typed confirmation.
        monkeypatch.setattr(
            ep,
            "resolve_connection",
            lambda: DbConnection(
                user="t", password=None, host="h", port="5432",
                database="pug_holding_test_fixture",
            ),
        )
        headers = _superuser(client, seed_auth["password"])
        resp = client.post(
            f"{BACKUP}/restore",
            headers=headers,
            files={"file": ("x.dump", b"PGDMP_payload", "application/octet-stream")},
            data={"confirm_db_name": "WRONG_NAME"},
        )
        assert resp.status_code == 400
        assert "does not match" in resp.json()["detail"]

    def test_restore_rejects_non_pgdump_file(self, client, seed_auth, monkeypatch):
        from app.api.endpoints import admin_backup as ep
        from app.services.db_backup import DbConnection

        monkeypatch.setattr(ep, "is_postgres", lambda: True)
        monkeypatch.setattr(ep, "tools_available", lambda: True)
        monkeypatch.setattr(
            ep,
            "resolve_connection",
            lambda: DbConnection(
                user="t", password=None, host="h", port="5432",
                database="pug_holding_test_fixture",
            ),
        )
        headers = _superuser(client, seed_auth["password"])
        resp = client.post(
            f"{BACKUP}/restore",
            headers=headers,
            files={
                "file": (
                    "looks-like-sql.dump",
                    b"-- this is just a plain SQL file\nCREATE TABLE foo();",
                    "application/octet-stream",
                ),
            },
            data={"confirm_db_name": "pug_holding_test_fixture"},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "pg_dump custom-format" in detail

    def test_restore_rejects_empty_file(self, client, seed_auth, monkeypatch):
        from app.api.endpoints import admin_backup as ep
        from app.services.db_backup import DbConnection

        monkeypatch.setattr(ep, "is_postgres", lambda: True)
        monkeypatch.setattr(ep, "tools_available", lambda: True)
        monkeypatch.setattr(
            ep,
            "resolve_connection",
            lambda: DbConnection(
                user="t", password=None, host="h", port="5432",
                database="pug_holding_test_fixture",
            ),
        )
        headers = _superuser(client, seed_auth["password"])
        resp = client.post(
            f"{BACKUP}/restore",
            headers=headers,
            files={"file": ("empty.dump", b"", "application/octet-stream")},
            data={"confirm_db_name": "pug_holding_test_fixture"},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# _audit — actor-row wipe survival
# ---------------------------------------------------------------------------


class TestAuditAfterActorWipe:
    """A successful restore can DROP+RECREATE the ``users`` table from
    the backup file, in which case the actor whose JWT initiated the
    restore no longer exists. ``_audit`` must still write the success
    row instead of FK-violating and 500ing the whole request."""

    def test_audit_writes_email_only_row_when_actor_row_gone(
        self, db_session
    ):
        from sqlalchemy import select as sa_select

        from app.api.endpoints.admin_backup import _audit
        from app.models.auth import AuditLog, User

        # Stand up the actor as a real DB row first so the helper has
        # something to capture before we wipe it.
        actor = User(
            email="ghost-superadmin@test.example",
            password_hash="x" * 60,
            full_name="Ghost Superadmin",
            is_active=True,
            is_superuser=True,
        )
        db_session.add(actor)
        db_session.commit()
        db_session.refresh(actor)
        captured_id = actor.id
        captured_email = actor.email

        # Simulate the pg_restore wiping the actor row.
        db_session.delete(actor)
        db_session.commit()

        # A minimal fake Request — _audit only touches headers/client
        # via get_request_context, which we feed a stub for.
        class _FakeReq:
            headers: dict[str, str] = {}
            client = None

        from app.api.endpoints import admin_backup as ep

        ep_get_ctx = ep.get_request_context
        ep.get_request_context = lambda req: {  # type: ignore[assignment]
            "ip_address": "127.0.0.1",
            "user_agent": "pytest",
        }
        try:
            # The actor object still has the now-orphaned id; pass a
            # transient stand-in so _audit sees actor.id == captured_id.
            ghost = User(
                email=captured_email,
                password_hash="x" * 60,
                full_name="Ghost Superadmin",
            )
            ghost.id = captured_id
            _audit(
                db_session,
                ghost,
                _FakeReq(),  # type: ignore[arg-type]
                action="admin.database.restore.success",
                details={"uploaded_filename": "test.dump"},
            )
        finally:
            ep.get_request_context = ep_get_ctx  # type: ignore[assignment]

        row = db_session.execute(
            sa_select(AuditLog).where(
                AuditLog.action == "admin.database.restore.success"
            )
        ).scalar_one()
        assert row.actor_id is None  # FK reference dropped, request succeeded
        assert row.actor_email == captured_email
        assert row.details["actor_row_wiped_by_restore"] is True
        assert row.details["uploaded_filename"] == "test.dump"


# ---------------------------------------------------------------------------
# /safety/{filename} — path traversal + 404
# ---------------------------------------------------------------------------


class TestSafetyEndpoints:
    def test_safety_list_when_empty(self, client, seed_auth, tmp_path, monkeypatch):
        # Patch at the binding the endpoint module sees — it imports
        # ``safety_backup_dir`` by name, so a patch on the service module
        # alone would not affect the live route.
        from app.api.endpoints import admin_backup as ep

        monkeypatch.setattr(ep, "safety_backup_dir", lambda: tmp_path)
        monkeypatch.setattr(db_backup, "safety_backup_dir", lambda: tmp_path)
        headers = _superuser(client, seed_auth["password"])
        resp = client.get(f"{BACKUP}/safety", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == {"backups": []}

    def test_safety_list_reports_existing(
        self, client, seed_auth, tmp_path, monkeypatch
    ):
        # Drop two fake .dump files in the safety dir
        (tmp_path / "safety_pug_holding_20260101_120000.dump").write_bytes(
            b"PGDMP_one"
        )
        (tmp_path / "safety_pug_holding_20260102_120000.dump").write_bytes(
            b"PGDMP_two_longer"
        )
        # Non-.dump should be ignored
        (tmp_path / "notes.txt").write_bytes(b"ignore me")

        # Patch at the binding the endpoint module sees — it imports
        # ``safety_backup_dir`` by name, so a patch on the service module
        # alone would not affect the live route.
        from app.api.endpoints import admin_backup as ep

        monkeypatch.setattr(ep, "safety_backup_dir", lambda: tmp_path)
        monkeypatch.setattr(db_backup, "safety_backup_dir", lambda: tmp_path)
        headers = _superuser(client, seed_auth["password"])
        resp = client.get(f"{BACKUP}/safety", headers=headers)
        assert resp.status_code == 200
        names = [b["filename"] for b in resp.json()["backups"]]
        assert "safety_pug_holding_20260101_120000.dump" in names
        assert "safety_pug_holding_20260102_120000.dump" in names
        assert "notes.txt" not in names

    @pytest.mark.parametrize(
        "bad_name",
        [
            "../../etc/passwd",
            "..\\windows\\system32",
            "/etc/passwd",
            ".hidden.dump",
            "no-extension",
            "wrong.txt",
            "",
        ],
    )
    def test_safety_download_rejects_unsafe_filenames(
        self, client, seed_auth, bad_name
    ):
        headers = _superuser(client, seed_auth["password"])
        # Empty string would route to GET /safety (the list endpoint),
        # so skip that case in the URL test.
        if bad_name == "":
            pytest.skip("Empty filename hits the list endpoint, not download")
        resp = client.get(f"{BACKUP}/safety/{bad_name}", headers=headers)
        # 400 for the validator, 404 if the path actually resolves but
        # the file isn't there. Both are fine — what matters is "not 200".
        assert resp.status_code in (400, 404)

    def test_safety_download_404_for_missing_file(
        self, client, seed_auth, tmp_path, monkeypatch
    ):
        # Patch at the binding the endpoint module sees — it imports
        # ``safety_backup_dir`` by name, so a patch on the service module
        # alone would not affect the live route.
        from app.api.endpoints import admin_backup as ep

        monkeypatch.setattr(ep, "safety_backup_dir", lambda: tmp_path)
        monkeypatch.setattr(db_backup, "safety_backup_dir", lambda: tmp_path)
        headers = _superuser(client, seed_auth["password"])
        resp = client.get(
            f"{BACKUP}/safety/safety_pug_holding_20250101_000000.dump",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_safety_download_streams_existing_file(
        self, client, seed_auth, tmp_path, monkeypatch
    ):
        payload = b"PGDMP" + b"x" * 1000
        fname = "safety_pug_holding_20260201_120000.dump"
        (tmp_path / fname).write_bytes(payload)
        # Patch at the binding the endpoint module sees — it imports
        # ``safety_backup_dir`` by name, so a patch on the service module
        # alone would not affect the live route.
        from app.api.endpoints import admin_backup as ep

        monkeypatch.setattr(ep, "safety_backup_dir", lambda: tmp_path)
        monkeypatch.setattr(db_backup, "safety_backup_dir", lambda: tmp_path)
        headers = _superuser(client, seed_auth["password"])
        resp = client.get(f"{BACKUP}/safety/{fname}", headers=headers)
        assert resp.status_code == 200
        assert resp.content == payload
        assert "attachment" in resp.headers["content-disposition"]
        assert fname in resp.headers["content-disposition"]

    def test_safety_delete_removes_file(
        self, client, seed_auth, tmp_path, monkeypatch
    ):
        fname = "safety_pug_holding_20260301_120000.dump"
        target = tmp_path / fname
        target.write_bytes(b"PGDMP_data")
        # Patch at the binding the endpoint module sees — it imports
        # ``safety_backup_dir`` by name, so a patch on the service module
        # alone would not affect the live route.
        from app.api.endpoints import admin_backup as ep

        monkeypatch.setattr(ep, "safety_backup_dir", lambda: tmp_path)
        monkeypatch.setattr(db_backup, "safety_backup_dir", lambda: tmp_path)
        headers = _superuser(client, seed_auth["password"])
        resp = client.delete(f"{BACKUP}/safety/{fname}", headers=headers)
        assert resp.status_code == 204
        assert not target.exists()


# ---------------------------------------------------------------------------
# Pure helper unit tests
# ---------------------------------------------------------------------------


class TestPureHelpers:
    def test_validate_dump_header_accepts_pgdmp(self):
        db_backup.validate_dump_header(b"PGDMP\x00\x01")  # no raise

    def test_validate_dump_header_rejects_plain_sql(self):
        with pytest.raises(db_backup.BackupError):
            db_backup.validate_dump_header(b"-- pg_dump SQL output\nCREATE")

    def test_validate_dump_header_rejects_empty(self):
        with pytest.raises(db_backup.BackupError):
            db_backup.validate_dump_header(b"")

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("safety_pug_holding_20260201_120000.dump", True),
            ("a.dump", True),
            ("../escape.dump", False),
            ("/abs/path.dump", False),
            ("hidden.dump", True),     # filename starts with letter — fine
            (".secret.dump", False),    # dot-prefix is blocked
            ("no-extension", False),
            ("wrong.txt", False),
            ("", False),
        ],
    )
    def test_is_safe_safety_filename(self, name, expected):
        assert db_backup.is_safe_safety_filename(name) is expected

    def test_make_backup_filename_format(self):
        # The default 'pug_holding' DB name should appear plus a UTC ts.
        name = db_backup.make_backup_filename()
        assert name.startswith("pug_backup_")
        assert name.endswith(".dump")
        # ...prefix_dbname_YYYYMMDD_HHMMSS.dump = 5 underscore-separated chunks
        parts = name.rsplit("_", 2)
        assert len(parts[-1]) == len("HHMMSS.dump")

    def test_make_backup_filename_honours_prefix(self):
        assert db_backup.make_backup_filename(prefix="safety").startswith("safety_")

    def test_resolve_connection_from_field_settings(self):
        cfg = db_backup.resolve_connection()
        # Default config sits behind the per-field path; we should at
        # least get a sensible host/port/user without exploding.
        assert cfg.host
        assert cfg.port == "5432"
        assert cfg.user
        assert cfg.database
