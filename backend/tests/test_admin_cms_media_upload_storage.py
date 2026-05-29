"""Media gallery upload — storage backend + folder routing.

The ``/admin/cms/media/upload`` endpoint used to write directly to
local disk regardless of ``R2_*`` env config, so R2-configured
installs ended up with two storage worlds: the inline image picker
went to R2 (via ``/uploads/image``), while the gallery direct upload
stayed local (``/api/v1/uploads/cms/<hash>.png``). These tests pin
the contract that the gallery endpoint now:

* Routes every upload through ``app.services.storage.get_storage``
  — the same abstraction the inline image picker uses, so an
  R2-configured install ships gallery files to R2 too.

* Accepts an optional ``folder`` query param mirroring the inline
  picker's surface — same validator (``_CMS_FOLDER_RE``), same
  rejection codes, same ``cms/<folder>/`` prefix shape.

* Short-circuits dedup BEFORE the storage round-trip — re-uploading
  the same bytes does not pay for a wasted R2 PUT.
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cms import MediaAsset


MEDIA_UPLOAD = "/api/v1/admin/cms/media/upload"
ADMIN_LOGIN = "/api/v1/admin/auth/login"

# Minimal valid 1×1 PNG — same one used elsewhere in the suite.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def _auth(client: TestClient, password: str) -> dict:
    r = client.post(
        ADMIN_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Folder routing — accepted shapes
# ---------------------------------------------------------------------------


def test_no_folder_keeps_flat_cms_prefix(
    client, db_session: Session, seed_auth
):
    """Missing ``folder=`` => upload lands under ``cms/`` directly, same as
    before this refactor. Backward-compatible."""
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 201, r.text
    url = r.json()["asset"]["url"]
    # Local backend on the test path returns
    # ``/api/v1/uploads/cms/<hash>.png``.
    assert "/cms/" in url
    assert "/cms/gallery/" not in url


def test_gallery_folder_routes_under_cms_gallery(
    client, db_session: Session, seed_auth
):
    """The exact case the operator hit — Media Gallery direct upload
    should land under ``cms/gallery/`` so a future ``ls`` on the R2
    bucket can tell admin-typed assets apart from CMS image picks."""
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        f"{MEDIA_UPLOAD}?folder=gallery",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 201, r.text
    url = r.json()["asset"]["url"]
    assert "/cms/gallery/" in url


def test_nested_folder_routes_under_cms_companies_logos(
    client, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        f"{MEDIA_UPLOAD}?folder=companies/logos",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 201, r.text
    url = r.json()["asset"]["url"]
    assert "/cms/companies/logos/" in url


# ---------------------------------------------------------------------------
# Folder routing — rejection shapes (same as the image picker)
# ---------------------------------------------------------------------------


def _expect_400(client: TestClient, headers: dict, folder: str) -> None:
    r = client.post(
        f"{MEDIA_UPLOAD}?folder={folder}",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 400, (
        f"expected 400 for folder={folder!r}, got {r.status_code} {r.text}"
    )


def test_folder_rejects_path_traversal(client, db_session: Session, seed_auth):
    headers = _auth(client, seed_auth["password"])
    _expect_400(client, headers, "..")
    _expect_400(client, headers, "../etc")
    _expect_400(client, headers, "gallery/../secrets")


def test_folder_rejects_uppercase(client, db_session: Session, seed_auth):
    headers = _auth(client, seed_auth["password"])
    _expect_400(client, headers, "Gallery")
    _expect_400(client, headers, "MARKETING")


def test_folder_rejects_too_many_segments(
    client, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    _expect_400(client, headers, "a/b/c/d/e")  # cap is 4


# ---------------------------------------------------------------------------
# Storage abstraction — go through get_storage, never direct disk writes
# ---------------------------------------------------------------------------


def test_upload_calls_storage_backend_not_raw_disk(
    client, db_session: Session, seed_auth, monkeypatch
):
    """The original bug: the endpoint wrote bytes directly to
    ``settings.upload_dir`` regardless of R2 being configured. Pin
    that every upload now goes through ``storage.upload`` so the
    R2 backend actually gets exercised when R2_* are set."""
    from app.services import storage as storage_module

    upload_calls: list[tuple[str, int, str | None]] = []
    # ``LocalStorageBackend`` is a frozen dataclass, so patch the
    # class method (not the instance attribute) to record calls.
    original_upload = storage_module.LocalStorageBackend.upload

    async def fake_upload(self, key, data, content_type):
        upload_calls.append((key, len(data), content_type))
        return await original_upload(self, key, data, content_type)

    monkeypatch.setattr(
        storage_module.LocalStorageBackend, "upload", fake_upload
    )

    headers = _auth(client, seed_auth["password"])
    r = client.post(
        f"{MEDIA_UPLOAD}?folder=gallery",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 201, r.text

    # Original file plus 3 WebP variants plus 3 JPEG variants = 7
    # storage.upload calls in total. Each PNG-derived variant lands
    # under the same ``cms/gallery/`` prefix as the original.
    keys = [c[0] for c in upload_calls]
    assert len(keys) >= 1, "storage.upload was never called"
    assert all(k.startswith("cms/gallery/") for k in keys), keys


# ---------------------------------------------------------------------------
# Dedup short-circuit — no second storage round-trip on duplicate bytes
# ---------------------------------------------------------------------------


def test_duplicate_upload_skips_storage_round_trip(
    client, db_session: Session, seed_auth, monkeypatch
):
    """Re-uploading the same bytes should reuse the MediaAsset row
    and NOT pay for another storage.upload call. Saves R2 PUT cost
    + variant generation on accidental double-clicks."""
    from app.services import storage as storage_module

    upload_count = {"n": 0}
    original_upload = storage_module.LocalStorageBackend.upload

    async def counting_upload(self, key, data, content_type):
        upload_count["n"] += 1
        return await original_upload(self, key, data, content_type)

    monkeypatch.setattr(
        storage_module.LocalStorageBackend, "upload", counting_upload
    )

    headers = _auth(client, seed_auth["password"])
    files = {"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")}

    # First upload — should hit storage for original + variants.
    r1 = client.post(f"{MEDIA_UPLOAD}?folder=gallery", headers=headers, files=files)
    assert r1.status_code == 201
    first_count = upload_count["n"]
    assert first_count >= 1
    assert r1.json()["deduped"] is False

    # Second upload of the same bytes — dedup short-circuits before
    # touching the storage backend.
    files = {"file": ("a-again.png", io.BytesIO(TINY_PNG), "image/png")}
    r2 = client.post(f"{MEDIA_UPLOAD}?folder=gallery", headers=headers, files=files)
    assert r2.status_code == 201
    assert r2.json()["deduped"] is True
    assert upload_count["n"] == first_count, (
        f"storage.upload called {upload_count['n'] - first_count} extra "
        f"times for a duplicate upload"
    )


# ---------------------------------------------------------------------------
# MediaAsset row — URL reflects the storage backend's response
# ---------------------------------------------------------------------------


def test_media_asset_row_carries_storage_url(
    client, db_session: Session, seed_auth
):
    """The persisted ``MediaAsset.url`` should equal whatever
    ``storage.upload`` returned. On an R2-configured install that's
    the custom-domain URL; on the test's local backend it's the
    ``/api/v1/uploads/...`` path. Either way the row stores the
    public URL, not a constructed one."""
    from sqlalchemy import select

    headers = _auth(client, seed_auth["password"])
    r = client.post(
        f"{MEDIA_UPLOAD}?folder=gallery",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 201
    api_url = r.json()["asset"]["url"]
    asset_id = r.json()["asset"]["id"]
    db_session.expire_all()
    row = db_session.execute(
        select(MediaAsset).where(MediaAsset.id == asset_id)
    ).scalar_one()
    assert row.url == api_url
    assert "/cms/gallery/" in row.url
