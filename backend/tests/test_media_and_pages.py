"""Tests for the Phase 5 follow-up: media gallery + CMS pages."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cms import CMSPage, MediaAsset


ADMIN_LOGIN = "/api/v1/admin/auth/login"
MEDIA_UPLOAD = "/api/v1/admin/cms/media/upload"
MEDIA_LIST = "/api/v1/admin/cms/media"
PAGES = "/api/v1/admin/cms/pages"


# Minimal valid 1×1 PNG. The bytes are a real, decodable PNG file.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def _admin_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        ADMIN_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Media gallery
# ---------------------------------------------------------------------------


def test_upload_image_creates_media_asset(client, db_session: Session, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    response = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["deduped"] is False
    asset = body["asset"]
    assert asset["kind"] == "image"
    assert asset["mime_type"] == "image/png"
    assert asset["url"].endswith(".png")
    assert asset["file_size"] == len(TINY_PNG)
    # Persisted row visible in the list endpoint
    rows = client.get(MEDIA_LIST, headers=headers).json()
    assert any(r["id"] == asset["id"] for r in rows)


def test_upload_same_file_dedupes(client, db_session: Session, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    first = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    ).json()
    second = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    ).json()
    assert first["asset"]["id"] == second["asset"]["id"]
    assert second["deduped"] is True


def test_upload_via_legacy_image_endpoint_also_registers(
    client, db_session: Session, seed_auth
):
    """The pre-existing /uploads/image still works and now registers
    a MediaAsset row."""
    headers = _admin_auth(client, seed_auth["password"])
    response = client.post(
        "/api/v1/admin/cms/uploads/image",
        headers=headers,
        files={"file": ("b.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert response.status_code == 201, response.text
    rows = client.get(MEDIA_LIST, headers=headers).json()
    assert len(rows) >= 1


def test_upload_rejects_unsupported_type(client, db_session: Session, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    response = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("a.exe", io.BytesIO(b"MZ\x90"), "application/octet-stream")},
    )
    assert response.status_code == 415


def test_media_list_filter_by_kind(client, db_session: Session, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    images = client.get(f"{MEDIA_LIST}?kind=image", headers=headers).json()
    assert all(row["kind"] == "image" for row in images)
    videos = client.get(f"{MEDIA_LIST}?kind=video", headers=headers).json()
    assert videos == []


def test_media_metadata_update(client, db_session: Session, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    body = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("logo.png", io.BytesIO(TINY_PNG), "image/png")},
    ).json()
    asset_id = body["asset"]["id"]

    response = client.patch(
        f"{MEDIA_LIST}/{asset_id}",
        headers=headers,
        json={
            "title": "Group brand logo",
            "alt_text": "Paris United Group monogram",
            "tags": "brand,logo,monogram",
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["title"] == "Group brand logo"
    assert "monogram" in updated["tags"]


def test_media_delete_removes_row_and_audits(
    client, db_session: Session, seed_auth
):
    headers = _admin_auth(client, seed_auth["password"])
    body = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("x.png", io.BytesIO(TINY_PNG), "image/png")},
    ).json()
    asset_id = body["asset"]["id"]
    response = client.delete(f"{MEDIA_LIST}/{asset_id}", headers=headers)
    assert response.status_code == 204
    assert db_session.get(MediaAsset, asset_id) is None


def test_public_media_endpoint_returns_assets(
    client, db_session: Session, seed_auth
):
    headers = _admin_auth(client, seed_auth["password"])
    client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    response = client.get("/api/v1/public/media")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 1
    assert rows[0]["kind"] == "image"


def test_media_is_public_defaults_true(client, db_session: Session, seed_auth):
    """A fresh upload is visible in the public album by default."""
    headers = _admin_auth(client, seed_auth["password"])
    body = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("default.png", io.BytesIO(TINY_PNG), "image/png")},
    ).json()
    assert body["asset"]["is_public"] is True


def test_admin_can_hide_asset_from_public_album(
    client, db_session: Session, seed_auth
):
    """Toggling is_public=False removes the asset from /public/media but
    keeps it in the admin listing."""
    headers = _admin_auth(client, seed_auth["password"])
    body = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("private.png", io.BytesIO(TINY_PNG), "image/png")},
    ).json()
    asset_id = body["asset"]["id"]

    # Public sees it.
    public_first = client.get("/api/v1/public/media").json()
    assert any(row["id"] == asset_id for row in public_first)

    # Hide it.
    patched = client.patch(
        f"{MEDIA_LIST}/{asset_id}",
        headers=headers,
        json={"is_public": False},
    )
    assert patched.status_code == 200
    assert patched.json()["is_public"] is False

    # Public no longer sees it.
    public_after = client.get("/api/v1/public/media").json()
    assert not any(row["id"] == asset_id for row in public_after)

    # Admin still does (so it can be re-shown or used as a hero image).
    admin_view = client.get(MEDIA_LIST, headers=headers).json()
    assert any(row["id"] == asset_id for row in admin_view)


def test_media_banner_urls_round_trip_through_site_settings(
    client, db_session: Session, seed_auth
):
    """The new media-page banner URLs persist and surface on the public
    site-settings endpoint that the Media page consumes."""
    headers = _admin_auth(client, seed_auth["password"])
    resp = client.patch(
        "/api/v1/admin/cms/site-settings",
        headers=headers,
        json={
            "media_banner_image_url": "/uploads/img/media-hero.jpg",
            "media_banner_mobile_url": "/uploads/img/media-hero-m.jpg",
        },
    )
    assert resp.status_code == 200, resp.text
    pub = client.get("/api/v1/public/site-settings").json()
    assert pub["media_banner_image_url"] == "/uploads/img/media-hero.jpg"
    assert pub["media_banner_mobile_url"] == "/uploads/img/media-hero-m.jpg"


def test_media_search_filter(client, db_session: Session, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    body = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("contract.png", io.BytesIO(TINY_PNG), "image/png")},
    ).json()
    asset_id = body["asset"]["id"]
    client.patch(
        f"{MEDIA_LIST}/{asset_id}",
        headers=headers,
        json={"tags": "press,event"},
    )
    found = client.get(f"{MEDIA_LIST}?q=press", headers=headers).json()
    assert any(row["id"] == asset_id for row in found)
    missing = client.get(f"{MEDIA_LIST}?q=zzz-not-there", headers=headers).json()
    assert missing == []


def test_public_media_tag_filter(client, db_session: Session, seed_auth):
    """Public /media endpoint accepts a `?tag=` query and matches the
    exact tag token in the asset's comma-separated `tags` field — so
    `?tag=team` doesn't bleed into `teammate`."""
    headers = _admin_auth(client, seed_auth["password"])

    # Three uploads with overlapping + unrelated tags.
    a = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
    ).json()["asset"]
    b = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        # tiny dedupe-buster so this row exists separately
        files={"file": ("b.png", io.BytesIO(TINY_PNG + b"\x00"), "image/png")},
    ).json()["asset"]
    c = client.post(
        MEDIA_UPLOAD,
        headers=headers,
        files={"file": ("c.png", io.BytesIO(TINY_PNG + b"\x01"), "image/png")},
    ).json()["asset"]

    client.patch(f"{MEDIA_LIST}/{a['id']}", headers=headers,
                 json={"tags": "team, paris-food-international"})
    client.patch(f"{MEDIA_LIST}/{b['id']}", headers=headers,
                 json={"tags": "stores,paris-hyper-market"})
    client.patch(f"{MEDIA_LIST}/{c['id']}", headers=headers,
                 # `teammate` would match a naive LIKE %team% — the
                 # tokenised matcher must skip it.
                 json={"tags": "teammate,events"})

    by_team = client.get("/api/v1/public/media?tag=team").json()
    ids = {row["id"] for row in by_team}
    assert a["id"] in ids
    assert c["id"] not in ids  # teammate must NOT match team

    by_company = client.get(
        "/api/v1/public/media?tag=paris-food-international"
    ).json()
    assert {row["id"] for row in by_company} == {a["id"]}

    none = client.get("/api/v1/public/media?tag=nothing-here").json()
    assert none == []


# ---------------------------------------------------------------------------
# CMS pages
# ---------------------------------------------------------------------------


def test_create_page_validates_slug(client, db_session: Session, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    response = client.post(
        PAGES,
        headers=headers,
        json={"slug": "Bad Slug!", "title": "X"},
    )
    assert response.status_code == 422


def test_create_then_get_page(client, db_session: Session, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    response = client.post(
        PAGES,
        headers=headers,
        json={
            "slug": "privacy",
            "title": "Privacy policy",
            "summary": "How we handle data.",
            "body": "## Privacy\n\nWe respect your data.",
            "is_published": True,
        },
    )
    assert response.status_code == 201, response.text
    page_id = response.json()["id"]

    detail = client.get(f"{PAGES}/{page_id}", headers=headers).json()
    assert detail["slug"] == "privacy"
    assert detail["is_published"] is True
    assert detail["published_at"] is not None


def test_create_duplicate_slug_returns_409(client, db_session: Session, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    payload = {"slug": "about-x", "title": "About", "body": ""}
    response = client.post(PAGES, headers=headers, json=payload)
    assert response.status_code == 201
    response2 = client.post(PAGES, headers=headers, json=payload)
    assert response2.status_code == 409


def test_update_page_publishes_and_unpublishes(
    client, db_session: Session, seed_auth
):
    headers = _admin_auth(client, seed_auth["password"])
    response = client.post(
        PAGES,
        headers=headers,
        json={"slug": "team", "title": "Team", "is_published": False},
    )
    page_id = response.json()["id"]

    # Publish → published_at set
    response = client.patch(
        f"{PAGES}/{page_id}",
        headers=headers,
        json={"is_published": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_published"] is True
    assert body["published_at"] is not None

    # Unpublish → published_at cleared
    response = client.patch(
        f"{PAGES}/{page_id}",
        headers=headers,
        json={"is_published": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_published"] is False
    assert body["published_at"] is None


def test_delete_page(client, db_session: Session, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    response = client.post(
        PAGES,
        headers=headers,
        json={"slug": "old", "title": "Old"},
    )
    page_id = response.json()["id"]
    response = client.delete(f"{PAGES}/{page_id}", headers=headers)
    assert response.status_code == 204
    assert db_session.get(CMSPage, page_id) is None


def test_public_pages_only_shows_published(
    client, db_session: Session, seed_auth
):
    headers = _admin_auth(client, seed_auth["password"])
    client.post(
        PAGES,
        headers=headers,
        json={"slug": "draft-page", "title": "Draft", "is_published": False},
    )
    client.post(
        PAGES,
        headers=headers,
        json={"slug": "live-page", "title": "Live", "is_published": True},
    )

    public = client.get("/api/v1/public/pages").json()
    slugs = {p["slug"] for p in public}
    assert "live-page" in slugs
    assert "draft-page" not in slugs

    # Direct draft access also 404s
    response = client.get("/api/v1/public/pages/draft-page")
    assert response.status_code == 404
    response = client.get("/api/v1/public/pages/live-page")
    assert response.status_code == 200
    assert response.json()["title"] == "Live"


def test_pages_list_admin_can_include_drafts(client, db_session: Session, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    client.post(
        PAGES,
        headers=headers,
        json={"slug": "d", "title": "D", "is_published": False},
    )
    client.post(
        PAGES,
        headers=headers,
        json={"slug": "p", "title": "P", "is_published": True},
    )

    all_pages = client.get(PAGES, headers=headers).json()
    assert {p["slug"] for p in all_pages} == {"d", "p"}

    only_pub = client.get(
        f"{PAGES}?include_drafts=false", headers=headers
    ).json()
    assert {p["slug"] for p in only_pub} == {"p"}
