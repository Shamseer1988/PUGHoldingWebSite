"""CMS image-upload ``folder`` routing.

The endpoint accepts an optional ``?folder=`` query param that
routes the uploaded file under ``cms/<folder>/`` instead of the
flat ``cms/`` root. The regex on the backend (
``_CMS_FOLDER_RE``) keeps the param safe:

* Whitelist shape — 1-4 segments of ``[a-z0-9-]+`` joined by ``/``.
* Rejects anything else with a 400 (path traversal, uppercase,
  spaces, encoded slashes, leading slash, empty segments).

These tests lock the contract so a future refactor can't widen the
validator without us noticing.
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cms import MediaAsset


UPLOAD_URL = "/api/v1/admin/cms/uploads/image"
ADMIN_LOGIN = "/api/v1/admin/auth/login"


# Minimum decodable 1×1 PNG used by the existing upload tests.
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
# Happy paths — accepted folder values land in the expected prefix
# ---------------------------------------------------------------------------


def test_no_folder_keeps_flat_cms_prefix(
    client, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        UPLOAD_URL,
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 201, r.text
    url = r.json()["url"]
    # Local backend on the test path returns ``/api/v1/uploads/cms/<file>``.
    assert "/cms/" in url
    assert "/cms/hero/" not in url


def test_single_segment_folder_routes_under_cms_hero(
    client, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        f"{UPLOAD_URL}?folder=hero",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 201, r.text
    url = r.json()["url"]
    assert "/cms/hero/" in url


def test_nested_folder_routes_under_cms_companies_logos(
    client, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        f"{UPLOAD_URL}?folder=companies/logos",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 201, r.text
    url = r.json()["url"]
    assert "/cms/companies/logos/" in url


def test_three_level_folder_routes_under_cms_marketing_catalogues(
    client, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        f"{UPLOAD_URL}?folder=marketing/catalogues",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 201, r.text
    assert "/cms/marketing/catalogues/" in r.json()["url"]


def test_blank_folder_falls_back_to_flat_prefix(
    client, db_session: Session, seed_auth
):
    """An empty ``folder=`` (or whitespace) is treated as 'no folder'
    — same shape as omitting the param entirely. Keeps the contract
    forgiving for clients that always set the param."""
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        f"{UPLOAD_URL}?folder=",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 201, r.text
    url = r.json()["url"]
    assert "/cms/" in url
    assert "/cms//" not in url  # no double-slash from concatenation


# ---------------------------------------------------------------------------
# Rejection paths — every shape we don't want to accept must return 400
# ---------------------------------------------------------------------------


def _expect_400(client: TestClient, headers: dict, folder: str) -> None:
    r = client.post(
        f"{UPLOAD_URL}?folder={folder}",
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
    _expect_400(client, headers, "hero/../secrets")


def test_folder_rejects_uppercase(client, db_session: Session, seed_auth):
    headers = _auth(client, seed_auth["password"])
    _expect_400(client, headers, "Hero")
    _expect_400(client, headers, "MARKETING")


def test_folder_rejects_spaces_and_special_chars(
    client, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    _expect_400(client, headers, "hero%20gallery")  # url-encoded space
    _expect_400(client, headers, "hero_gallery")    # underscore
    _expect_400(client, headers, "hero.gallery")    # dot
    _expect_400(client, headers, "hero gallery")    # raw space


def test_folder_rejects_too_many_segments(
    client, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    _expect_400(client, headers, "a/b/c/d/e")  # 5 segments — cap is 4


def test_folder_rejects_empty_segments(
    client, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    _expect_400(client, headers, "hero//gallery")


# ---------------------------------------------------------------------------
# MediaAsset row carries the routed URL
# ---------------------------------------------------------------------------


def test_media_asset_row_carries_routed_url(
    client, db_session: Session, seed_auth
):
    """The persisted ``MediaAsset.url`` should reflect the folder
    routing so the gallery list endpoint reads the correct path.

    The ``/uploads/image`` endpoint registers a MediaAsset row but
    returns the upload response directly (url + filename + size +
    mime_type), not wrapped in an ``asset`` envelope — so we look
    the row up via its filename instead of an id from the body.
    """
    from sqlalchemy import select

    headers = _auth(client, seed_auth["password"])
    r = client.post(
        f"{UPLOAD_URL}?folder=hero",
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert r.status_code == 201
    filename = r.json()["filename"]
    db_session.expire_all()
    row = db_session.execute(
        select(MediaAsset).where(MediaAsset.filename == filename)
    ).scalar_one_or_none()
    assert row is not None
    assert "/cms/hero/" in row.url
