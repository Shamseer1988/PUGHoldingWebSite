"""Phase A-5 — admin storage health endpoint.

Covers:

* When R2 is not configured (test default), the endpoint reports the
  local backend and skips the round-trip — no boto3 calls.
* The endpoint is gated on superuser; an HR-only operator gets 403.
* When a fake R2 backend is pinned, the endpoint runs the
  upload → head → delete sequence and surfaces the result.
* A failing ``head_object`` propagates as ``roundtrip.ok == False``
  with the error message (truncated) on the response.

Real R2 credentials are never required — the boto3 client inside
``R2StorageBackend`` is replaced with a hand-rolled stub via the
storage factory.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.services.storage import R2StorageBackend


HEALTH_URL = "/api/v1/admin/storage/health"


def _superuser_token(client: TestClient, password: str) -> dict:
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _hr_token(client: TestClient, password: str) -> dict:
    response = client.post(
        "/api/v1/hr/auth/login",
        json={"email": "hr@pug.example.com", "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Local-backend path (the default for the test suite)
# ---------------------------------------------------------------------------


def test_local_backend_reports_unconfigured(client, seed_auth):
    headers = _superuser_token(client, seed_auth["password"])
    response = client.get(HEALTH_URL, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["backend"] == "local"
    assert body["configured"] is False
    assert body["bucket"] is None
    assert body["roundtrip"] is None


def test_endpoint_requires_authentication(client):
    response = client.get(HEALTH_URL)
    assert response.status_code == 401


def test_endpoint_rejects_non_superuser(client, seed_auth):
    headers = _hr_token(client, seed_auth["password"])
    response = client.get(HEALTH_URL, headers=headers)
    # HR token doesn't carry the website scope require_superuser uses,
    # so the dependency rejects with 403 (or 401 if the scope check
    # short-circuits earlier).
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# R2-backend path — pin a fake backend via the storage factory
# ---------------------------------------------------------------------------


class _FakeR2Client:
    """boto3 stand-in. Records every ``put_object`` / ``head_object``
    / ``delete_object`` call so tests can introspect the round-trip."""

    def __init__(self) -> None:
        self.put_calls: list[dict[str, Any]] = []
        self.head_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self.head_should_raise: Exception | None = None

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        return {"ETag": '"fake-etag"'}

    def head_object(self, **kwargs):
        if self.head_should_raise is not None:
            raise self.head_should_raise
        self.head_calls.append(kwargs)
        return {"ContentLength": 2, "ContentType": "text/plain"}

    def delete_object(self, **kwargs):
        self.delete_calls.append(kwargs)
        return {"DeleteMarker": True}


def _install_fake_r2(monkeypatch, fake_client: _FakeR2Client) -> R2StorageBackend:
    """Build an ``R2StorageBackend`` whose boto3 client is the fake,
    and pin it via the storage factory so the endpoint picks it up.

    The dataclass is frozen, so we use ``object.__setattr__`` to
    swap the client in — same trick ``__post_init__`` already uses.
    """
    backend = R2StorageBackend.__new__(R2StorageBackend)
    object.__setattr__(backend, "bucket", "pug-holding-media")
    object.__setattr__(
        backend, "endpoint_url", "https://fake.r2.cloudflarestorage.com"
    )
    object.__setattr__(backend, "access_key_id", "fake-key")
    object.__setattr__(backend, "secret_access_key", "fake-secret")
    object.__setattr__(
        backend, "public_base_url", "https://media.example.com"
    )
    object.__setattr__(backend, "_client", fake_client)

    from app.api.endpoints import admin_storage
    from app.services import storage as storage_mod

    monkeypatch.setattr(storage_mod, "get_storage", lambda: backend)
    monkeypatch.setattr(admin_storage, "get_storage", lambda: backend)
    return backend


def test_r2_backend_runs_round_trip(client, seed_auth, monkeypatch):
    fake = _FakeR2Client()
    _install_fake_r2(monkeypatch, fake)

    headers = _superuser_token(client, seed_auth["password"])
    response = client.get(HEALTH_URL, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["backend"] == "r2"
    assert body["roundtrip"]["ok"] is True
    assert body["roundtrip"]["upload_key"].startswith("_healthcheck/")

    # The boto3 stand-in saw exactly one PUT + HEAD + DELETE.
    assert len(fake.put_calls) == 1
    assert len(fake.head_calls) == 1
    assert len(fake.delete_calls) == 1

    # PUT key matches what the response advertises.
    put_key = fake.put_calls[0]["Key"]
    assert body["roundtrip"]["upload_key"] == put_key


def test_r2_backend_reports_failure_when_head_raises(
    client, seed_auth, monkeypatch
):
    fake = _FakeR2Client()
    fake.head_should_raise = RuntimeError("AccessDenied")
    _install_fake_r2(monkeypatch, fake)

    headers = _superuser_token(client, seed_auth["password"])
    response = client.get(HEALTH_URL, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["roundtrip"]["ok"] is False
    assert "AccessDenied" in body["roundtrip"]["error"]
    # Even when HEAD failed, we still tried to clean up the PUT.
    assert len(fake.delete_calls) == 1
