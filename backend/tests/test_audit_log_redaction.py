"""``record_audit`` must redact sensitive keys from ``details`` before
storing them — the audit-log table must not become a credential leak
vector if a developer accidentally logs ``{"password": "..."}``."""
from __future__ import annotations

import pytest

from app.services.audit_log import _sanitize_details, record_audit


class TestSanitizeDetails:
    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "Password",
            "PASSWORD",
            "user_password",
            "password_hash",
            "passwd",
            "secret",
            "client_secret",
            "api_key",
            "apiKey",
            "api-key",
            "access_token",
            "refresh_token",
            "authorization",
            "Bearer",
            "Cookie",
            "private_key",
        ],
    )
    def test_redacts_top_level_sensitive_keys(self, key):
        out = _sanitize_details({key: "supersecret"})
        assert out[key] == "<redacted>"

    def test_keeps_unrelated_keys(self):
        out = _sanitize_details(
            {
                "candidate_id": 42,
                "email": "x@example.com",
                "file_hash": "abc123",  # content-addressed id, not a secret
            }
        )
        assert out == {
            "candidate_id": 42,
            "email": "x@example.com",
            "file_hash": "abc123",
        }

    def test_redacts_nested_dicts(self):
        out = _sanitize_details(
            {"user": {"id": 1, "password": "p"}, "ok": True}
        )
        assert out == {"user": {"id": 1, "password": "<redacted>"}, "ok": True}

    def test_redacts_inside_lists_and_tuples(self):
        out = _sanitize_details(
            {"sessions": [{"id": 1, "access_token": "tok"}, {"id": 2}]}
        )
        assert out["sessions"][0]["access_token"] == "<redacted>"
        assert out["sessions"][1] == {"id": 2}

    def test_none_input_returns_none_path(self):
        # ``record_audit`` skips sanitize when details is None, so the
        # function itself only ever sees non-None — but it should still
        # cleanly pass-through leaf values.
        assert _sanitize_details(42) == 42
        assert _sanitize_details("x") == "x"
        assert _sanitize_details(None) is None

    def test_does_not_mutate_input(self):
        original = {"password": "p", "ok": True}
        snapshot = dict(original)
        _sanitize_details(original)
        assert original == snapshot


class TestRecordAuditRedaction:
    def test_record_audit_redacts_before_persist(self, db_session):
        record_audit(
            db_session,
            action="test.demo",
            details={"password": "p", "kept": "v"},
        )
        from app.models.auth import AuditLog

        row = db_session.query(AuditLog).filter_by(action="test.demo").one()
        assert row.details == {"password": "<redacted>", "kept": "v"}
