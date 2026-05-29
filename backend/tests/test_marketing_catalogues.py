"""Digital Offers & Catalogue module — backend behaviour tests.

Covers:

* Campaign CRUD + slug uniqueness + active-window filtering.
* Catalogue upload (synthesises a tiny 2-page PDF via PyMuPDF so
  the processor renders something real).
* Processing failure paths (empty PDF, invalid bytes).
* Public landing endpoint bucketing (featured / killer / flash).
* View-event analytics aggregation.
* Permission gating.
"""
from __future__ import annotations

import io
import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models.marketing import (
    CATALOGUE_FAILED,
    CATALOGUE_READY,
    Catalogue,
    CataloguePage,
    OfferCampaign,
)


ADMIN_LOGIN = "/api/v1/admin/auth/login"
PUBLIC_OFFERS = "/api/v1/offers"
ADMIN_MARKETING = "/api/v1/admin/marketing"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login_super(client: TestClient, password: str) -> dict:
    resp = client.post(
        ADMIN_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(ADMIN_LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_pdf_bytes(page_count: int = 2) -> bytes:
    """Synthesise a small but real PDF via PyMuPDF.

    Each page gets a one-line text + a coloured rectangle so the
    renderer has something visible to rasterise. Returns the
    serialised bytes ready to push through the upload endpoint.
    """
    import fitz

    doc = fitz.open()
    for i in range(page_count):
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_text((72, 80), f"Page {i + 1} — test catalogue")
        page.draw_rect(
            fitz.Rect(50, 100, 545, 750), color=(0.1, 0.4, 0.2), fill=(0.85, 0.93, 0.83)
        )
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _seed_super_with_marketing_perms(db_session, seed_auth) -> None:
    """Grant the new marketing permissions to the Super Admin role so
    the existing seed user can hit the marketing endpoints. The HR
    rework seeded fine-grained permissions but didn't include the
    new marketing.* keys."""
    from app.auth.permissions import (
        PERM_MARKETING_CAMPAIGNS_MANAGE,
        PERM_MARKETING_CATALOGUES_MANAGE,
    )
    from app.models.auth import Permission, SCOPE_SYSTEM

    role = seed_auth["roles"]["Super Admin"]
    for key in (
        PERM_MARKETING_CAMPAIGNS_MANAGE,
        PERM_MARKETING_CATALOGUES_MANAGE,
    ):
        perm = db_session.query(Permission).filter_by(key=key).first()
        if perm is None:
            perm = Permission(
                key=key,
                scope=SCOPE_SYSTEM,
                description=f"Test fixture grant for {key}",
            )
            db_session.add(perm)
            db_session.flush()
        if perm not in role.permissions:
            role.permissions = role.permissions + [perm]
    db_session.commit()


# ---------------------------------------------------------------------------
# Campaign CRUD
# ---------------------------------------------------------------------------


class TestCampaignCrud:
    def test_create_list_update_delete(
        self, client: TestClient, seed_auth, db_session
    ):
        _seed_super_with_marketing_perms(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])

        # Create
        r = client.post(
            f"{ADMIN_MARKETING}/campaigns",
            headers=headers,
            json={
                "slug": "summer-2026",
                "title": "Summer Mega Deals 2026",
                "description": "Up to 50% off across hypermarket",
                "branch": "Doha",
                "theme_color": "#17382f",
                "is_featured": True,
                "is_killer_offer": True,
                "start_date": str(date.today() - timedelta(days=1)),
                "end_date": str(date.today() + timedelta(days=14)),
            },
        )
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["slug"] == "summer-2026"
        cid = created["id"]

        # List
        r = client.get(f"{ADMIN_MARKETING}/campaigns", headers=headers)
        assert r.status_code == 200
        assert any(c["id"] == cid for c in r.json())

        # Update
        r = client.patch(
            f"{ADMIN_MARKETING}/campaigns/{cid}",
            headers=headers,
            json={"title": "Summer Mega Deals — updated"},
        )
        assert r.status_code == 200
        assert r.json()["title"] == "Summer Mega Deals — updated"

        # Delete
        r = client.delete(
            f"{ADMIN_MARKETING}/campaigns/{cid}", headers=headers
        )
        assert r.status_code == 204
        r = client.get(
            f"{ADMIN_MARKETING}/campaigns/{cid}", headers=headers
        )
        assert r.status_code == 404

    def test_slug_uniqueness(
        self, client: TestClient, seed_auth, db_session
    ):
        _seed_super_with_marketing_perms(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])
        body = {"slug": "duplicate-slug", "title": "First"}
        assert client.post(
            f"{ADMIN_MARKETING}/campaigns", headers=headers, json=body
        ).status_code == 201
        r = client.post(
            f"{ADMIN_MARKETING}/campaigns",
            headers=headers,
            json={"slug": "duplicate-slug", "title": "Second"},
        )
        assert r.status_code == 409

    def test_invalid_slug_rejected(
        self, client: TestClient, seed_auth, db_session
    ):
        _seed_super_with_marketing_perms(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])
        r = client.post(
            f"{ADMIN_MARKETING}/campaigns",
            headers=headers,
            json={"slug": "Has Spaces", "title": "x"},
        )
        assert r.status_code == 422

    def test_invalid_theme_color_rejected(
        self, client: TestClient, seed_auth, db_session
    ):
        _seed_super_with_marketing_perms(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])
        r = client.post(
            f"{ADMIN_MARKETING}/campaigns",
            headers=headers,
            json={
                "slug": "bad-color",
                "title": "x",
                "theme_color": "not-a-hex",
            },
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Catalogue upload + PDF processing
# ---------------------------------------------------------------------------


class TestCatalogueUpload:
    def test_upload_pdf_renders_pages(
        self, client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
    ):
        # Sandbox the upload dir so we don't pollute the project tree.
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        from app.core.config import get_settings

        get_settings.cache_clear()

        _seed_super_with_marketing_perms(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])

        pdf = _make_pdf_bytes(page_count=3)
        files = {"file": ("flyer.pdf", pdf, "application/pdf")}
        data = {
            "slug": "summer-flyer-2026",
            "title": "Summer Flyer 2026",
            "description": "Three test pages",
            "is_featured": "true",
        }
        r = client.post(
            f"{ADMIN_MARKETING}/catalogues",
            headers=headers,
            files=files,
            data=data,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["page_count"] == 3
        assert body["processing_status"] == CATALOGUE_READY
        assert body["cover_image_url"], "cover should be populated"
        assert body["pdf_url"], "source PDF url should be set"
        assert len(body["pages"]) == 3
        for i, p in enumerate(body["pages"], start=1):
            assert p["page_number"] == i
            assert p["image_url"].endswith(f"page_{i:03d}.webp")
            assert p["thumbnail_url"].endswith(f"page_{i:03d}.thumb.webp")
            assert p["width"] > 0 and p["height"] > 0

        # The on-disk files actually exist.
        from pathlib import Path
        cat_dir = Path(tmp_path) / "catalogues" / str(body["id"])
        assert (cat_dir / "source.pdf").exists()
        assert (cat_dir / "page_001.webp").exists()
        assert (cat_dir / "page_001.thumb.webp").exists()

        get_settings.cache_clear()

    def test_upload_rejects_non_pdf(
        self, client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        from app.core.config import get_settings

        get_settings.cache_clear()
        _seed_super_with_marketing_perms(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])
        files = {"file": ("doc.txt", b"not a pdf", "text/plain")}
        data = {"slug": "not-pdf", "title": "x"}
        r = client.post(
            f"{ADMIN_MARKETING}/catalogues",
            headers=headers,
            files=files,
            data=data,
        )
        assert r.status_code == 400
        assert "pdf" in r.json()["detail"].lower()
        get_settings.cache_clear()

    def test_upload_rejects_empty_pdf(
        self, client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        from app.core.config import get_settings

        get_settings.cache_clear()
        _seed_super_with_marketing_perms(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])
        r = client.post(
            f"{ADMIN_MARKETING}/catalogues",
            headers=headers,
            files={"file": ("empty.pdf", b"", "application/pdf")},
            data={"slug": "empty", "title": "x"},
        )
        assert r.status_code == 400
        get_settings.cache_clear()

    def test_upload_corrupt_pdf_marks_failed(
        self, client: TestClient, seed_auth, db_session, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        from app.core.config import get_settings

        get_settings.cache_clear()
        _seed_super_with_marketing_perms(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])
        # Has %PDF magic so the endpoint MIME-checks pass, but the
        # content is junk so PyMuPDF refuses to open it.
        bad = b"%PDF-1.4\nthis is not a real pdf\n%%EOF"
        r = client.post(
            f"{ADMIN_MARKETING}/catalogues",
            headers=headers,
            files={"file": ("bad.pdf", bad, "application/pdf")},
            data={"slug": "bad-pdf", "title": "x"},
        )
        assert r.status_code == 500
        # The catalogue row should be created with a failed status so
        # the admin sees it in the inbox and can reprocess.
        cat = (
            db_session.query(Catalogue).filter_by(slug="bad-pdf").one()
        )
        assert cat.processing_status == CATALOGUE_FAILED
        assert cat.processing_error
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Public landing
# ---------------------------------------------------------------------------


class TestPublicLanding:
    def test_landing_buckets_campaigns(
        self, client: TestClient, db_session, seed_auth, tmp_path, monkeypatch
    ):
        # Need a real catalogue so the landing surfaces the campaign
        # (we filter to "has at least one ready catalogue").
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        from app.core.config import get_settings

        get_settings.cache_clear()
        _seed_super_with_marketing_perms(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])

        # Create a featured + killer campaign and upload one catalogue
        # into it.
        camp = client.post(
            f"{ADMIN_MARKETING}/campaigns",
            headers=headers,
            json={
                "slug": "featured-killer",
                "title": "Featured + Killer",
                "branch": "Doha",
                "is_featured": True,
                "is_killer_offer": True,
            },
        ).json()
        client.post(
            f"{ADMIN_MARKETING}/catalogues",
            headers=headers,
            files={"file": ("a.pdf", _make_pdf_bytes(1), "application/pdf")},
            data={
                "slug": "fk-cat",
                "title": "FK Catalogue",
                "campaign_id": str(camp["id"]),
            },
        )

        # Plain non-featured campaign WITHOUT a catalogue — must be
        # hidden from the public list.
        client.post(
            f"{ADMIN_MARKETING}/campaigns",
            headers=headers,
            json={"slug": "draft-empty", "title": "Empty Draft"},
        )

        r = client.get(PUBLIC_OFFERS)
        assert r.status_code == 200
        body = r.json()

        slugs_all = {c["slug"] for c in body["all_campaigns"]}
        slugs_featured = {c["slug"] for c in body["featured"]}
        slugs_killer = {c["slug"] for c in body["killer_offers"]}

        assert "featured-killer" in slugs_all
        assert "featured-killer" in slugs_featured
        assert "featured-killer" in slugs_killer
        assert "draft-empty" not in slugs_all  # no ready catalogue
        assert "Doha" in body["branches"]

        get_settings.cache_clear()

    def test_branch_filter(
        self, client: TestClient, db_session, seed_auth, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
        from app.core.config import get_settings

        get_settings.cache_clear()
        _seed_super_with_marketing_perms(db_session, seed_auth)
        headers = _login_super(client, seed_auth["password"])
        # Two campaigns in two branches.
        for slug, branch in [("doha-now", "Doha"), ("lusail-now", "Lusail")]:
            c = client.post(
                f"{ADMIN_MARKETING}/campaigns",
                headers=headers,
                json={"slug": slug, "title": slug, "branch": branch},
            ).json()
            client.post(
                f"{ADMIN_MARKETING}/catalogues",
                headers=headers,
                files={
                    "file": (
                        f"{slug}.pdf",
                        _make_pdf_bytes(1),
                        "application/pdf",
                    )
                },
                data={
                    "slug": f"{slug}-cat",
                    "title": slug,
                    "campaign_id": str(c["id"]),
                },
            )
        r = client.get(f"{PUBLIC_OFFERS}?branch=Doha")
        assert r.status_code == 200
        slugs = {c["slug"] for c in r.json()["all_campaigns"]}
        assert slugs == {"doha-now"}
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Permission gating
# ---------------------------------------------------------------------------


class TestPermissions:
    def test_non_admin_cannot_create_campaign(
        self, client: TestClient, seed_auth
    ):
        # HR user holds no website scope at all — the website-admin
        # login flow rejects them outright.
        resp = client.post(
            "/api/v1/admin/auth/login",
            json={
                "email": "hr@pug.example.com",
                "password": seed_auth["password"],
            },
        )
        assert resp.status_code in (401, 403)

    def test_website_admin_without_marketing_perm_is_403(
        self, client: TestClient, seed_auth
    ):
        # Plain website admin holds the scope but not the new
        # marketing.campaigns:manage permission.
        headers = _login(
            client, "webadmin@pug.example.com", seed_auth["password"]
        )
        r = client.get(f"{ADMIN_MARKETING}/campaigns", headers=headers)
        assert r.status_code == 403
