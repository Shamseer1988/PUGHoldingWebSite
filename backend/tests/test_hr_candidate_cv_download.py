"""``GET /hr/candidates/{id}/cv`` — R2-safe download endpoint.

Replaces the legacy ``/api/v1/uploads/cvs/…`` StaticFiles serving
path. The endpoint:

  * Resolves the candidate's primary ``CandidateDocument`` (or the
    most-recent fallback).
  * Asks the storage backend for a short-lived URL via
    ``cv_download_url`` and 302-redirects.
  * 404s for unknown candidate / no CV on file / storage object
    that no longer exists — never 500s on a transient miss.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import Candidate, CandidateDocument
from app.services.storage import get_storage


ADMIN_LOGIN = "/api/v1/admin/auth/login"
HR_LOGIN = "/api/v1/hr/auth/login"


def _login_super(client: TestClient, password: str) -> dict[str, str]:
    r = client.post(
        HR_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_candidate_with_cv(
    db_session: Session, *, key: str = "career/cv/abc.pdf", bytes_: bytes = b"%PDF-1.4 hello"
) -> Candidate:
    candidate = Candidate(full_name="Has CV", email="hascv@test.example")
    db_session.add(candidate)
    db_session.flush()
    db_session.add(
        CandidateDocument(
            candidate_id=candidate.id,
            filename=key.rsplit("/", 1)[-1],
            file_path=key,
            mime_type="application/pdf",
            file_size=len(bytes_),
            file_hash="0" * 64,
            is_primary=True,
        )
    )
    db_session.commit()
    db_session.refresh(candidate)
    # Push the bytes into the storage backend so the helper has
    # something to sign a URL for.
    get_storage().upload_sync(key, bytes_, "application/pdf")
    return candidate


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_download_redirects_to_storage_url(
    client: TestClient, seed_auth, db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    candidate = _seed_candidate_with_cv(db_session)
    headers = _login_super(client, seed_auth["password"])

    r = client.get(
        f"/api/v1/hr/candidates/{candidate.id}/cv",
        headers=headers,
        follow_redirects=False,
    )
    assert r.status_code == 302
    # Local backend resolves to ``/api/v1/uploads/<key>`` — good
    # enough for the redirect-target shape assertion.
    assert "career/cv/abc.pdf" in r.headers["location"]


def test_download_picks_primary_when_multiple_docs(
    client: TestClient, seed_auth, db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    candidate = Candidate(full_name="Multi", email="multi@test.example")
    db_session.add(candidate)
    db_session.flush()
    # Older non-primary first.
    db_session.add(
        CandidateDocument(
            candidate_id=candidate.id,
            filename="old.pdf",
            file_path="career/cv/old.pdf",
            mime_type="application/pdf",
            file_size=5,
            file_hash="o" * 64,
            is_primary=False,
        )
    )
    # Newer primary second.
    db_session.add(
        CandidateDocument(
            candidate_id=candidate.id,
            filename="new.pdf",
            file_path="career/cv/new.pdf",
            mime_type="application/pdf",
            file_size=10,
            file_hash="n" * 64,
            is_primary=True,
        )
    )
    db_session.commit()
    get_storage().upload_sync("career/cv/new.pdf", b"new", "application/pdf")
    get_storage().upload_sync("career/cv/old.pdf", b"old", "application/pdf")

    headers = _login_super(client, seed_auth["password"])
    r = client.get(
        f"/api/v1/hr/candidates/{candidate.id}/cv",
        headers=headers,
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "career/cv/new.pdf" in r.headers["location"]


# ---------------------------------------------------------------------------
# 404 paths
# ---------------------------------------------------------------------------


def test_download_404_when_candidate_missing(
    client: TestClient, seed_auth
):
    headers = _login_super(client, seed_auth["password"])
    r = client.get(
        "/api/v1/hr/candidates/999999/cv", headers=headers, follow_redirects=False
    )
    assert r.status_code == 404


def test_download_404_when_no_docs(
    client: TestClient, seed_auth, db_session: Session
):
    candidate = Candidate(full_name="No CV", email="nocv@test.example")
    db_session.add(candidate)
    db_session.commit()
    headers = _login_super(client, seed_auth["password"])
    r = client.get(
        f"/api/v1/hr/candidates/{candidate.id}/cv",
        headers=headers,
        follow_redirects=False,
    )
    assert r.status_code == 404


def test_download_requires_auth(
    client: TestClient, db_session: Session
):
    candidate = Candidate(full_name="No Auth", email="x@test.example")
    db_session.add(candidate)
    db_session.commit()
    r = client.get(
        f"/api/v1/hr/candidates/{candidate.id}/cv", follow_redirects=False
    )
    # 401 / 403 either is fine — point is unauthenticated rejected.
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# JSON sibling: ``/cv-url`` — used by the HR SPA where a 302 redirect
# from an ``<a href>`` click would drop the Bearer JWT and 401.
# ---------------------------------------------------------------------------


def test_cv_url_returns_signed_url_as_json(
    client: TestClient, seed_auth, db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    candidate = _seed_candidate_with_cv(db_session)
    headers = _login_super(client, seed_auth["password"])

    r = client.get(
        f"/api/v1/hr/candidates/{candidate.id}/cv-url", headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "career/cv/abc.pdf" in body["url"]
    assert body["expires_in"] == 600


def test_cv_url_404_when_no_docs(
    client: TestClient, seed_auth, db_session: Session
):
    candidate = Candidate(full_name="No CV JSON", email="nocvjson@test.example")
    db_session.add(candidate)
    db_session.commit()
    headers = _login_super(client, seed_auth["password"])
    r = client.get(
        f"/api/v1/hr/candidates/{candidate.id}/cv-url", headers=headers
    )
    assert r.status_code == 404


def test_cv_url_requires_auth(
    client: TestClient, db_session: Session
):
    candidate = Candidate(full_name="No Auth JSON", email="xjson@test.example")
    db_session.add(candidate)
    db_session.commit()
    r = client.get(f"/api/v1/hr/candidates/{candidate.id}/cv-url")
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# cv_storage helpers
# ---------------------------------------------------------------------------


def test_storage_key_from_legacy_normalises_all_shapes():
    from app.services.cv_storage import _storage_key_from_legacy

    # Modern key — unchanged.
    assert (
        _storage_key_from_legacy("career/cv/abc.pdf") == "career/cv/abc.pdf"
    )
    # Legacy URL.
    assert (
        _storage_key_from_legacy("/api/v1/uploads/cvs/abc.pdf")
        == "career/cv/abc.pdf"
    )
    # Legacy bare ``cvs/`` form.
    assert _storage_key_from_legacy("cvs/abc.pdf") == "career/cv/abc.pdf"
    # Last-resort basename fallback.
    assert (
        _storage_key_from_legacy("/some/other/path/abc.pdf")
        == "career/cv/abc.pdf"
    )


def test_storage_key_from_legacy_rejects_empty():
    import pytest

    from app.services.cv_storage import _storage_key_from_legacy

    with pytest.raises(FileNotFoundError):
        _storage_key_from_legacy("")


def test_read_cv_bytes_roundtrips_through_storage(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services.cv_storage import read_cv_bytes

    get_settings.cache_clear()
    get_storage().upload_sync("career/cv/x.pdf", b"hello", "application/pdf")
    assert read_cv_bytes("career/cv/x.pdf") == b"hello"
    # Also via legacy URL — same bytes back, no separate fetch needed.
    assert read_cv_bytes("/api/v1/uploads/cvs/x.pdf") == b"hello"


def test_cv_download_url_returns_storage_backed_url(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services.cv_storage import cv_download_url

    get_settings.cache_clear()
    url = cv_download_url("career/cv/abc.pdf", expires_in=300)
    # Local backend returns the StaticFiles URL — production R2
    # returns a signed ``https://…`` URL. Either way the storage key
    # is reachable via the returned string.
    assert "career/cv/abc.pdf" in url


def test_stage_cv_locally_writes_temp_file_and_cleans_up(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from pathlib import Path

    from app.core.config import get_settings
    from app.services.cv_storage import stage_cv_locally

    get_settings.cache_clear()
    get_storage().upload_sync(
        "career/cv/staged.pdf", b"%PDF-bytes", "application/pdf"
    )

    with stage_cv_locally("career/cv/staged.pdf") as p:
        assert p.exists()
        assert p.read_bytes() == b"%PDF-bytes"
        captured = p

    # Temp file cleaned up on exit.
    assert not Path(captured).exists()


# ---------------------------------------------------------------------------
# Storage backend presigned_url
# ---------------------------------------------------------------------------


def test_local_backend_presigned_url_uses_staticfiles_prefix(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    url = get_storage().presigned_url("career/cv/abc.pdf", expires_in=900)
    # Local doesn't sign anything; it returns the legacy
    # ``/api/v1/uploads/<key>`` URL the StaticFiles mount serves.
    assert url == "/api/v1/uploads/career/cv/abc.pdf"
