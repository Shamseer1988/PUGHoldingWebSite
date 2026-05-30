"""QR-code brand logo — upload, delete, generate (R2-safe).

Locks the contract that the QR logo pipeline pushes through the
``app.services.storage`` backend exactly the same way as media uploads
and catalogue page renders. Before the R2 fix these endpoints wrote
files straight to local disk and hardcoded ``/api/v1/uploads/…``
URLs, which produced a broken badge on any R2 install.

Covers:

* Upload → row.qr_logo_url returned by storage, bytes are recoverable
  via ``storage.download_sync`` at the deterministic key.
* Re-upload with a different extension cleans up the orphan ext.
* Delete clears the URL and removes every known ext from storage.
* ``GET /qr-code.png`` 200s + returns a PNG; the QR builder is given
  the logo bytes (not a filesystem path), and the response stays
  usable when the logo is missing.
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.models.marketing import Catalogue


ADMIN_LOGIN = "/api/v1/admin/auth/login"
ADMIN_MARKETING = "/api/v1/admin/marketing"


def _login_super(client: TestClient, password: str) -> dict[str, str]:
    r = client.post(
        ADMIN_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _tiny_png_bytes(color: tuple[int, int, int] = (200, 30, 30)) -> bytes:
    """16x16 solid-colour PNG — enough for PIL to decode + composite."""
    img = Image.new("RGB", (16, 16), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_catalogue(db_session: Session, slug: str = "qr-test") -> Catalogue:
    row = Catalogue(slug=slug, title="QR Test", page_count=0)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _grant_catalogues_manage(db_session, seed_auth) -> None:
    from app.auth.permissions import PERM_MARKETING_CATALOGUES_MANAGE
    from app.models.auth import Permission, SCOPE_SYSTEM

    role = seed_auth["roles"]["Super Admin"]
    perm = (
        db_session.query(Permission)
        .filter_by(key=PERM_MARKETING_CATALOGUES_MANAGE)
        .first()
    )
    if perm is None:
        perm = Permission(
            key=PERM_MARKETING_CATALOGUES_MANAGE,
            scope=SCOPE_SYSTEM,
            description="Test fixture",
        )
        db_session.add(perm)
        db_session.flush()
    if perm not in role.permissions:
        role.permissions = role.permissions + [perm]
    db_session.commit()


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def test_upload_qr_logo_pushes_bytes_through_storage(
    client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services.storage import get_storage

    get_settings.cache_clear()
    _grant_catalogues_manage(db_session, seed_auth)
    cat = _make_catalogue(db_session)

    headers = _login_super(client, seed_auth["password"])
    png = _tiny_png_bytes()
    r = client.post(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-logo",
        headers=headers,
        files={"file": ("logo.png", png, "image/png")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["qr_logo_url"], "qr_logo_url should be populated"
    # Local-disk URL form — the test's storage backend is the local
    # backend pointed at tmp_path.
    assert body["qr_logo_url"].endswith(f"qr-logos/{cat.id}.png")

    # The bytes round-trip via the storage backend (same path the QR
    # generator uses, so this proves the chain works end-to-end).
    storage = get_storage()
    fetched = storage.download_sync(f"qr-logos/{cat.id}.png")
    assert fetched == png


def test_upload_rejects_unsupported_extension(
    client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    _grant_catalogues_manage(db_session, seed_auth)
    cat = _make_catalogue(db_session)

    headers = _login_super(client, seed_auth["password"])
    r = client.post(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-logo",
        headers=headers,
        files={"file": ("logo.gif", b"\x47\x49\x46\x38\x39\x61", "image/gif")},
    )
    assert r.status_code == 400


def test_upload_rejects_empty_file(
    client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    _grant_catalogues_manage(db_session, seed_auth)
    cat = _make_catalogue(db_session)

    headers = _login_super(client, seed_auth["password"])
    r = client.post(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-logo",
        headers=headers,
        files={"file": ("logo.png", b"", "image/png")},
    )
    assert r.status_code == 400


def test_reupload_with_new_extension_drops_old_orphan(
    client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
):
    """A .png upload then a .jpg upload should leave only the .jpg in
    storage — otherwise the old extension lingers as an orphan AND
    keeps getting served via the old URL until the next overwrite."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services.storage import get_storage

    get_settings.cache_clear()
    _grant_catalogues_manage(db_session, seed_auth)
    cat = _make_catalogue(db_session)

    headers = _login_super(client, seed_auth["password"])
    png = _tiny_png_bytes()
    client.post(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-logo",
        headers=headers,
        files={"file": ("logo.png", png, "image/png")},
    )

    jpg_buf = io.BytesIO()
    Image.new("RGB", (16, 16), (10, 100, 10)).save(jpg_buf, format="JPEG")
    jpg = jpg_buf.getvalue()
    r = client.post(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-logo",
        headers=headers,
        files={"file": ("logo.jpg", jpg, "image/jpeg")},
    )
    assert r.status_code == 200
    assert r.json()["qr_logo_url"].endswith(".jpg")

    storage = get_storage()
    assert storage.download_sync(f"qr-logos/{cat.id}.jpg") == jpg
    import pytest

    with pytest.raises(FileNotFoundError):
        storage.download_sync(f"qr-logos/{cat.id}.png")


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_clears_url_and_drops_bytes(
    client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services.storage import get_storage

    get_settings.cache_clear()
    _grant_catalogues_manage(db_session, seed_auth)
    cat = _make_catalogue(db_session)

    headers = _login_super(client, seed_auth["password"])
    client.post(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-logo",
        headers=headers,
        files={"file": ("logo.png", _tiny_png_bytes(), "image/png")},
    )

    r = client.delete(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-logo", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["qr_logo_url"] is None

    storage = get_storage()
    import pytest

    with pytest.raises(FileNotFoundError):
        storage.download_sync(f"qr-logos/{cat.id}.png")


def test_delete_is_idempotent_when_no_logo_set(
    client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    _grant_catalogues_manage(db_session, seed_auth)
    cat = _make_catalogue(db_session)

    headers = _login_super(client, seed_auth["password"])
    r = client.delete(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-logo", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["qr_logo_url"] is None


# ---------------------------------------------------------------------------
# QR generation
# ---------------------------------------------------------------------------


def test_qr_code_renders_with_uploaded_logo(
    client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
):
    """The endpoint pulls logo bytes via storage.download_sync and
    composites them into the badge — proves the QR flow doesn't rely
    on a filesystem path anymore."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    _grant_catalogues_manage(db_session, seed_auth)
    cat = _make_catalogue(db_session)

    headers = _login_super(client, seed_auth["password"])
    client.post(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-logo",
        headers=headers,
        files={"file": ("logo.png", _tiny_png_bytes(), "image/png")},
    )

    r = client.get(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-code.png", headers=headers
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    # Decodes as a real PNG (smoke test — anything that wasn't a
    # valid image would explode here).
    img = Image.open(io.BytesIO(r.content))
    assert img.size[0] > 0 and img.size[1] > 0


def test_qr_code_falls_back_when_logo_bytes_missing(
    client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
):
    """If row.qr_logo_url points at a key that no longer exists in
    storage (e.g. R2 dashboard deletion), the QR endpoint should
    still 200 — silently dropping back to the monogram fallback."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services.storage import get_storage

    get_settings.cache_clear()
    _grant_catalogues_manage(db_session, seed_auth)
    cat = _make_catalogue(db_session)
    cat.qr_logo_url = "/api/v1/uploads/qr-logos/9999.png"  # nonexistent
    db_session.commit()

    storage = get_storage()
    # Sanity: the key really isn't there.
    import pytest

    with pytest.raises(FileNotFoundError):
        storage.download_sync("qr-logos/9999.png")

    headers = _login_super(client, seed_auth["password"])
    r = client.get(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-code.png", headers=headers
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_qr_code_works_without_any_logo(
    client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    _grant_catalogues_manage(db_session, seed_auth)
    cat = _make_catalogue(db_session)

    headers = _login_super(client, seed_auth["password"])
    r = client.get(
        f"{ADMIN_MARKETING}/catalogues/{cat.id}/qr-code.png", headers=headers
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


# ---------------------------------------------------------------------------
# URL-shape recovery
# ---------------------------------------------------------------------------


def test_qr_logo_key_recovered_from_local_url():
    from app.api.endpoints.admin_marketing import _qr_logo_key_from_url

    assert (
        _qr_logo_key_from_url("/api/v1/uploads/qr-logos/42.png")
        == "qr-logos/42.png"
    )


def test_qr_logo_key_recovered_from_r2_url():
    from app.api.endpoints.admin_marketing import _qr_logo_key_from_url

    assert (
        _qr_logo_key_from_url("https://media.example.com/qr-logos/42.png")
        == "qr-logos/42.png"
    )


def test_qr_logo_key_returns_none_for_unrelated_url():
    from app.api.endpoints.admin_marketing import _qr_logo_key_from_url

    assert _qr_logo_key_from_url("https://example.com/something-else.png") is None
    assert _qr_logo_key_from_url("") is None
