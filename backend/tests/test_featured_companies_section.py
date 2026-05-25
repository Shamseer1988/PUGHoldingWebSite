"""Tests for the featured-companies homepage section endpoint + image upload."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cms import Company, SiteSetting


PUBLIC = "/api/v1/public/featured-companies-section"
ADMIN_LOGIN = "/api/v1/admin/auth/login"
UPLOAD = "/api/v1/admin/cms/uploads/image"


def _admin_headers(client: TestClient, password: str) -> dict:
    response = client.post(
        ADMIN_LOGIN,
        json={"email": "webadmin@pug.example.com", "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Public section endpoint
# ---------------------------------------------------------------------------


def test_section_returns_defaults_with_no_data(client):
    response = client.get(PUBLIC)
    assert response.status_code == 200
    body = response.json()
    assert body["section"]["enabled"] is True
    assert body["section"]["animation_enabled"] is True
    # Fallback copy applied when site_settings has nothing custom.
    assert body["section"]["eyebrow"] == "Group companies"
    assert body["companies"] == []


def test_section_prefers_highlighted_companies(client, db_session: Session):
    db_session.add_all(
        [
            Company(
                slug="not-shown",
                name="Not shown",
                category="retail",
                initials="NS",
                is_active=True,
                is_highlighted=False,
                display_order=1,
            ),
            Company(
                slug="hero",
                name="Hero co",
                category="retail",
                initials="HC",
                is_active=True,
                is_highlighted=True,
                display_order=2,
            ),
            Company(
                slug="hidden",
                name="Hidden",
                category="retail",
                initials="HD",
                is_active=False,
                is_highlighted=True,
                display_order=3,
            ),
        ]
    )
    db_session.commit()

    response = client.get(PUBLIC)
    assert response.status_code == 200
    slugs = [c["slug"] for c in response.json()["companies"]]
    assert slugs == ["hero"]  # highlighted + active only


def test_section_falls_back_to_all_active_when_no_highlighted(
    client, db_session: Session
):
    db_session.add_all(
        [
            Company(
                slug="a",
                name="A",
                category="retail",
                initials="A",
                is_active=True,
                display_order=1,
            ),
            Company(
                slug="b",
                name="B",
                category="retail",
                initials="B",
                is_active=True,
                display_order=2,
            ),
        ]
    )
    db_session.commit()

    body = client.get(PUBLIC).json()
    assert [c["slug"] for c in body["companies"]] == ["a", "b"]


def test_section_reads_admin_settings(client, db_session: Session):
    db_session.add(
        SiteSetting(
            id=1,
            site_name="PUG",
            featured_companies_enabled=False,
            featured_companies_eyebrow="Custom eyebrow",
            featured_companies_title="Custom title",
            featured_companies_subtitle="Custom subtitle",
            featured_companies_cta_label="Open the showcase",
            featured_companies_cta_url="/companies?category=retail",
            featured_companies_animation_enabled=False,
        )
    )
    db_session.commit()

    section = client.get(PUBLIC).json()["section"]
    assert section["enabled"] is False
    assert section["animation_enabled"] is False
    assert section["eyebrow"] == "Custom eyebrow"
    assert section["title"] == "Custom title"
    assert section["subtitle"] == "Custom subtitle"
    assert section["cta_label"] == "Open the showcase"
    assert section["cta_url"] == "/companies?category=retail"


# ---------------------------------------------------------------------------
# Image upload endpoint
# ---------------------------------------------------------------------------


# 1x1 transparent PNG.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452"
    "00000001000000010806000000"
    "1f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def test_image_upload_returns_url(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    response = client.post(
        UPLOAD,
        files={"file": ("tiny.png", io.BytesIO(TINY_PNG), "image/png")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["url"].startswith("/api/v1/uploads/cms/")
    assert body["url"].endswith(".png")
    assert body["mime_type"] == "image/png"
    assert body["size"] > 0


def test_image_upload_rejects_unsupported_type(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    response = client.post(
        UPLOAD,
        files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 415
    assert "Unsupported file type" in response.json()["detail"]


def test_image_upload_requires_admin_scope(client, seed_auth):
    # HR token must be rejected.
    hr_login = client.post(
        "/api/v1/hr/auth/login",
        json={"email": "hr@pug.example.com", "password": seed_auth["password"]},
    )
    hr_headers = {"Authorization": f"Bearer {hr_login.json()['access_token']}"}

    response = client.post(
        UPLOAD,
        files={"file": ("tiny.png", io.BytesIO(TINY_PNG), "image/png")},
        headers=hr_headers,
    )
    assert response.status_code == 403


def test_image_upload_dedupes_identical_content(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    first = client.post(
        UPLOAD,
        files={"file": ("a.png", io.BytesIO(TINY_PNG), "image/png")},
        headers=headers,
    ).json()
    second = client.post(
        UPLOAD,
        files={"file": ("b.png", io.BytesIO(TINY_PNG), "image/png")},
        headers=headers,
    ).json()
    assert first["url"] == second["url"]  # same content => same filename


# ---------------------------------------------------------------------------
# Company CRUD round-trip with new fields
# ---------------------------------------------------------------------------


def test_company_with_featured_image_and_highlight(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    body = {
        "slug": "featured-co",
        "name": "Featured Co",
        "category": "retail",
        "initials": "FC",
        "is_highlighted": True,
        "featured_image_url": "/api/v1/uploads/cms/abc123.png",
        "cta_label": "Visit the brand",
        "cta_url": "https://example.com",
    }
    create = client.post("/api/v1/admin/cms/companies", json=body, headers=headers)
    assert create.status_code == 201, create.text
    out = create.json()
    assert out["is_highlighted"] is True
    assert out["featured_image_url"] == "/api/v1/uploads/cms/abc123.png"
    assert out["cta_label"] == "Visit the brand"

    # Public section should now include it.
    public = client.get(PUBLIC).json()
    slugs = [c["slug"] for c in public["companies"]]
    assert "featured-co" in slugs


def test_company_group_homepage_video_fields_roundtrip(client, seed_auth):
    """Phase 18 follow-up — admins can set + clear the Group Companies
    video URL, poster, highlight paragraph, and stat line, and the
    values flow through to the public payload."""
    headers = _admin_headers(client, seed_auth["password"])
    body = {
        "slug": "video-co",
        "name": "Video Co",
        "category": "distribution",
        "initials": "VC",
        "is_highlighted": True,
        "featured_image_url": "/api/v1/uploads/cms/poster.png",
        "homepage_group_highlight": (
            "Video Co distributes premium FMCG across the GCC, serving "
            "wholesale, retail, department store, and HORECA channels."
        ),
        "homepage_group_stat_line": "500+ Brand Partners · 15,000+ SKUs",
        "homepage_group_video_url": "/api/v1/uploads/cms/loop.mp4",
        "homepage_group_video_poster_url": "/api/v1/uploads/cms/loop-poster.jpg",
    }
    create = client.post("/api/v1/admin/cms/companies", json=body, headers=headers)
    assert create.status_code == 201, create.text
    created = create.json()
    assert created["homepage_group_video_url"] == "/api/v1/uploads/cms/loop.mp4"
    assert (
        created["homepage_group_video_poster_url"]
        == "/api/v1/uploads/cms/loop-poster.jpg"
    )
    assert created["homepage_group_highlight"].startswith("Video Co distributes")
    assert created["homepage_group_stat_line"] == "500+ Brand Partners · 15,000+ SKUs"

    # Public payload exposes the same fields.
    public = client.get(PUBLIC).json()
    payload = next(c for c in public["companies"] if c["slug"] == "video-co")
    assert payload["homepage_group_video_url"] == "/api/v1/uploads/cms/loop.mp4"
    assert payload["homepage_group_highlight"].startswith("Video Co distributes")

    # Patch — clearing the video reverts to image-only.
    patched = client.patch(
        f"/api/v1/admin/cms/companies/{created['id']}",
        headers=headers,
        json={"homepage_group_video_url": None, "homepage_group_video_poster_url": None},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["homepage_group_video_url"] is None
    assert patched.json()["homepage_group_video_poster_url"] is None
    # featured_image_url is preserved so the public section still shows
    # a sensible poster.
    assert patched.json()["featured_image_url"] == "/api/v1/uploads/cms/poster.png"


def test_company_brand_logos_roundtrip(client, seed_auth):
    """Admins can attach multiple brand-logo images to a company; the
    marquee on the public side reads them back in display order."""
    headers = _admin_headers(client, seed_auth["password"])

    create = client.post(
        "/api/v1/admin/cms/companies",
        headers=headers,
        json={
            "slug": "logo-co",
            "name": "Logo Co",
            "category": "distribution",
            "initials": "LC",
            "is_highlighted": True,
            "brand_logos": [
                {
                    "image_url": "/api/v1/uploads/cms/logo-a.png",
                    "name": "Brand A",
                    "link_url": "https://example.com/a",
                    "display_order": 1,
                },
                {
                    "image_url": "/api/v1/uploads/cms/logo-b.png",
                    "name": "Brand B",
                    "display_order": 2,
                },
            ],
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert len(body["brand_logos"]) == 2
    assert [l["name"] for l in body["brand_logos"]] == ["Brand A", "Brand B"]
    assert body["brand_logos"][0]["link_url"] == "https://example.com/a"

    # Public payload exposes the same list.
    public = client.get(PUBLIC).json()
    payload = next(c for c in public["companies"] if c["slug"] == "logo-co")
    assert len(payload["brand_logos"]) == 2

    # PATCH wholesale-replaces the list — supplying a single logo wipes
    # the previous two.
    patched = client.patch(
        f"/api/v1/admin/cms/companies/{body['id']}",
        headers=headers,
        json={
            "brand_logos": [
                {
                    "image_url": "/api/v1/uploads/cms/logo-c.png",
                    "name": "Brand C",
                }
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    assert len(patched.json()["brand_logos"]) == 1
    assert patched.json()["brand_logos"][0]["name"] == "Brand C"

    # Sending [] clears the list entirely.
    cleared = client.patch(
        f"/api/v1/admin/cms/companies/{body['id']}",
        headers=headers,
        json={"brand_logos": []},
    )
    assert cleared.status_code == 200
    assert cleared.json()["brand_logos"] == []
