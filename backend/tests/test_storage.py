"""Pluggable storage backend (Phase A-6).

Two implementations, two test groups:

* ``LocalStorageBackend`` — writes to disk under a tmp_path-rooted
  upload dir; we round-trip a small payload and check the returned
  URL + that the bytes landed where promised. Delete + missing-key
  delete are also covered because the upload endpoint relies on both.

* ``R2StorageBackend`` — boto3's S3 client is stubbed via
  ``monkeypatch`` so the test never opens a real connection. We
  verify the call shape (Bucket / Key / Body / ContentType) is what
  R2 expects, the returned URL respects the optional custom domain,
  and ``delete`` issues a ``delete_object`` against the same key.

A third test group covers the ``get_storage()`` factory — the
configured-vs-unconfigured branch and the LRU cache.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from app.services import storage as storage_module
from app.services.storage import (
    LocalStorageBackend,
    R2StorageBackend,
    _build_storage,
    get_storage,
)


# ---------------------------------------------------------------------------
# Helpers — synchronous wrappers so the test bodies stay readable
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# ---------------------------------------------------------------------------
# LocalStorageBackend
# ---------------------------------------------------------------------------


class TestLocalStorageBackend:
    def test_upload_writes_bytes_to_disk_and_returns_static_url(
        self, tmp_path: Path
    ):
        backend = LocalStorageBackend(root=tmp_path)
        url = _run(
            backend.upload("cms/example.png", b"PNGDATA", "image/png")
        )
        assert url == "/api/v1/uploads/cms/example.png"
        on_disk = tmp_path / "cms" / "example.png"
        assert on_disk.exists()
        assert on_disk.read_bytes() == b"PNGDATA"

    def test_upload_normalises_leading_slash_on_key(self, tmp_path: Path):
        backend = LocalStorageBackend(root=tmp_path)
        url = _run(backend.upload("/cms/foo.png", b"x", "image/png"))
        # No double-slash, key still ends up under cms/.
        assert url == "/api/v1/uploads/cms/foo.png"
        assert (tmp_path / "cms" / "foo.png").exists()

    def test_upload_creates_intermediate_directories(self, tmp_path: Path):
        backend = LocalStorageBackend(root=tmp_path)
        _run(
            backend.upload(
                "cms/deeply/nested/path/file.bin", b"hello", "application/octet-stream"
            )
        )
        assert (
            tmp_path / "cms" / "deeply" / "nested" / "path" / "file.bin"
        ).exists()

    def test_delete_removes_an_existing_file(self, tmp_path: Path):
        backend = LocalStorageBackend(root=tmp_path)
        _run(backend.upload("cms/doomed.bin", b"bye", None))
        assert (tmp_path / "cms" / "doomed.bin").exists()

        _run(backend.delete("cms/doomed.bin"))
        assert not (tmp_path / "cms" / "doomed.bin").exists()

    def test_delete_is_idempotent_when_key_is_missing(self, tmp_path: Path):
        # The upload-image endpoint may call delete on a key that
        # never existed (e.g. when an admin retries an aborted upload).
        # That must not raise — otherwise a transient cleanup failure
        # would surface as a 500 to the operator.
        backend = LocalStorageBackend(root=tmp_path)
        _run(backend.delete("cms/never-existed.bin"))  # no exception


# ---------------------------------------------------------------------------
# R2StorageBackend — boto3 client stubbed
# ---------------------------------------------------------------------------


@dataclass
class _FakeBoto3Client:
    """Minimal stub matching the ``put_object`` + ``delete_object``
    shape boto3 exposes for S3-compatible buckets.

    Records every call so tests can assert on parameter shape (Bucket
    name, Key, Body bytes, ContentType) instead of having to mock the
    HTTP layer underneath.
    """

    puts: list[dict[str, Any]] = field(default_factory=list)
    deletes: list[dict[str, Any]] = field(default_factory=list)

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.puts.append(kwargs)
        return {"ETag": '"abc123"'}

    def delete_object(self, **kwargs: Any) -> dict[str, Any]:
        self.deletes.append(kwargs)
        return {"DeleteMarker": False}


@pytest.fixture
def fake_boto3(monkeypatch):
    """Patch ``boto3.client`` so the R2 backend captures call shape
    without opening a TCP socket. Yields the captured client so the
    test body can inspect ``.puts`` / ``.deletes`` directly."""
    instance = _FakeBoto3Client()
    seen_kwargs: dict[str, Any] = {}

    def _factory(service: str, **kwargs: Any) -> _FakeBoto3Client:
        # Record the boto3.client(...) constructor args so the test
        # can confirm the endpoint URL + region are wired correctly.
        seen_kwargs.update({"service": service, **kwargs})
        return instance

    monkeypatch.setattr("boto3.client", _factory)
    return instance, seen_kwargs


def _r2_backend(public_base_url: str | None = None) -> R2StorageBackend:
    return R2StorageBackend(
        bucket="pug-test-bucket",
        endpoint_url="https://accountid.r2.cloudflarestorage.com",
        access_key_id="AKIA-TEST",
        secret_access_key="SECRET-TEST",
        public_base_url=public_base_url,
    )


class TestR2StorageBackend:
    def test_constructor_passes_credentials_to_boto3(self, fake_boto3):
        _instance, seen = fake_boto3
        _r2_backend()
        # boto3.client("s3", endpoint_url=…, aws_access_key_id=…, …)
        assert seen["service"] == "s3"
        assert (
            seen["endpoint_url"]
            == "https://accountid.r2.cloudflarestorage.com"
        )
        assert seen["aws_access_key_id"] == "AKIA-TEST"
        assert seen["aws_secret_access_key"] == "SECRET-TEST"
        # ``region_name`` lands on the Config object, not as a kwarg.
        assert seen["config"].region_name == "auto"
        assert seen["config"].signature_version == "s3v4"

    def test_upload_invokes_put_object_with_expected_shape(self, fake_boto3):
        instance, _ = fake_boto3
        backend = _r2_backend()
        url = _run(
            backend.upload("cms/foo.png", b"PNGDATA", "image/png")
        )

        # Exactly one put_object call, with the expected kwargs.
        assert len(instance.puts) == 1
        call = instance.puts[0]
        assert call["Bucket"] == "pug-test-bucket"
        assert call["Key"] == "cms/foo.png"
        assert call["Body"] == b"PNGDATA"
        assert call["ContentType"] == "image/png"

        # Without a custom domain we fall back to the long URL form.
        assert url == (
            "https://accountid.r2.cloudflarestorage.com/"
            "pug-test-bucket/cms/foo.png"
        )

    def test_upload_returns_custom_public_url_when_configured(self, fake_boto3):
        backend = _r2_backend(public_base_url="https://media.example.com")
        url = _run(backend.upload("cms/bar.png", b"X", "image/png"))
        assert url == "https://media.example.com/cms/bar.png"

    def test_upload_prepends_https_when_public_base_url_lacks_scheme(
        self, fake_boto3
    ):
        """Operators frequently set ``R2_PUBLIC_BASE_URL=cdn.example.com``
        without the ``https://`` prefix. The resulting
        ``cdn.example.com/cms/foo.jpg`` would otherwise be saved as-is
        into the DB and treated as a relative URL by the browser,
        404-ing the image. Auto-promote to ``https://`` so a missed
        scheme doesn't break uploads silently."""
        backend = _r2_backend(public_base_url="cdn.example.com")
        url = _run(backend.upload("cms/bar.png", b"X", "image/png"))
        assert url == "https://cdn.example.com/cms/bar.png"

    def test_upload_preserves_explicit_http_scheme(self, fake_boto3):
        """If an operator deliberately uses plain ``http://`` (LAN dev,
        internal mirror) we leave it alone — only the no-scheme case
        gets promoted."""
        backend = _r2_backend(public_base_url="http://cdn.example.com")
        url = _run(backend.upload("cms/bar.png", b"X", "image/png"))
        assert url == "http://cdn.example.com/cms/bar.png"

    def test_upload_defaults_content_type_when_missing(self, fake_boto3):
        instance, _ = fake_boto3
        backend = _r2_backend()
        _run(backend.upload("cms/x.bin", b"\x00", None))
        assert instance.puts[0]["ContentType"] == "application/octet-stream"

    def test_upload_strips_leading_slash_from_key(self, fake_boto3):
        instance, _ = fake_boto3
        backend = _r2_backend()
        _run(backend.upload("/cms/y.png", b"x", "image/png"))
        assert instance.puts[0]["Key"] == "cms/y.png"

    def test_delete_invokes_delete_object(self, fake_boto3):
        instance, _ = fake_boto3
        backend = _r2_backend()
        _run(backend.delete("cms/old.png"))
        assert len(instance.deletes) == 1
        assert instance.deletes[0]["Bucket"] == "pug-test-bucket"
        assert instance.deletes[0]["Key"] == "cms/old.png"


# ---------------------------------------------------------------------------
# Factory selection
# ---------------------------------------------------------------------------


class TestStorageFactory:
    def test_returns_local_backend_when_r2_unconfigured(
        self, fake_boto3, monkeypatch, tmp_path
    ):
        from app.core.config import Settings

        s = Settings(upload_dir=str(tmp_path))  # no R2_* env → unconfigured
        backend = _build_storage(s)
        assert isinstance(backend, LocalStorageBackend)
        assert backend.root == tmp_path

    def test_returns_r2_backend_when_r2_configured(
        self, fake_boto3, monkeypatch
    ):
        from app.core.config import Settings

        s = Settings(
            r2_endpoint_url="https://acc.r2.cloudflarestorage.com",
            r2_access_key_id="KEY",
            r2_secret_access_key="SECRET",
            r2_bucket_name="pug-test",
            r2_public_base_url="https://media.example.com",
        )
        backend = _build_storage(s)
        assert isinstance(backend, R2StorageBackend)
        assert backend.bucket == "pug-test"

    def test_get_storage_is_cached(self, monkeypatch, fake_boto3):
        # Bust the cache so the previous tests don't bleed in.
        get_storage.cache_clear()
        a = get_storage()
        b = get_storage()
        assert a is b  # same instance — boto3 client only built once
        get_storage.cache_clear()
