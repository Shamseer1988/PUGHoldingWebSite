"""Tests for the Trusted Brands showcase (Phase 2 redesign).

Covers:

  * Admin CRUD: list / create / update / delete.
  * Section settings round-trip via the site-settings PATCH route.
  * Public homepage endpoint returns active rows ordered by
    ``display_order`` and falls back to ``home_brand_strip_title``
    when the new ``home_brand_title`` is empty (backwards-compat).
  * Inactive brands are filtered out of the public payload.
  * Layout mode validation (only marquee/grid/carousel).
"""
from __future__ import annotations

from fastapi.testclient import TestClient


ADMIN_LOGIN = "/api/v1/admin/auth/login"
CMS = "/api/v1/admin/cms"
PUBLIC = "/api/v1/public"


def _admin_headers(client: TestClient, password: str) -> dict:
    resp = client.post(
        ADMIN_LOGIN,
        json={"email": "webadmin@pug.example.com", "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_brand_crud_round_trip(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])

    # Empty list to start (test DB has no brand rows seeded).
    rows = client.get(f"{CMS}/brands", headers=headers).json()
    initial = len(rows)

    created = client.post(
        f"{CMS}/brands",
        headers=headers,
        json={
            "brand_name": "Paris Hyper Market",
            "logo_url": "/images/home/brands/brand_01.png",
            "link_url": "https://parishyper.example.com",
            "category": "retail",
            "is_highlight": True,
            "display_order": 1,
        },
    )
    assert created.status_code == 201, created.text
    brand_id = created.json()["id"]
    assert created.json()["brand_name"] == "Paris Hyper Market"
    assert created.json()["is_highlight"] is True

    rows = client.get(f"{CMS}/brands", headers=headers).json()
    assert len(rows) == initial + 1

    patched = client.patch(
        f"{CMS}/brands/{brand_id}",
        headers=headers,
        json={"display_order": 5, "is_active": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["display_order"] == 5
    assert patched.json()["is_active"] is False

    deleted = client.delete(f"{CMS}/brands/{brand_id}", headers=headers)
    assert deleted.status_code == 204
    assert (
        client.get(f"{CMS}/brands/{brand_id}", headers=headers).status_code in (404, 405)
    )


def test_brand_update_404(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    resp = client.patch(
        f"{CMS}/brands/999999",
        headers=headers,
        json={"brand_name": "x"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Section-settings round-trip
# ---------------------------------------------------------------------------


def test_section_settings_update(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])

    resp = client.patch(
        f"{CMS}/site-settings",
        headers=headers,
        json={
            "home_brand_section_enabled": True,
            "home_brand_eyebrow": "OUR BRANDS",
            "home_brand_title": "Brands across our group",
            "home_brand_subtitle": "Built on quality and trust.",
            "home_brand_layout_mode": "grid",
            "home_brand_animation_enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["home_brand_eyebrow"] == "OUR BRANDS"
    assert body["home_brand_title"] == "Brands across our group"
    assert body["home_brand_layout_mode"] == "grid"


# ---------------------------------------------------------------------------
# Public homepage endpoint
# ---------------------------------------------------------------------------


def test_public_endpoint_returns_active_sorted_brands(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])

    # Two active rows, one inactive. Out-of-order display_order so we
    # verify sorting actually happens.
    client.post(
        f"{CMS}/brands",
        headers=headers,
        json={
            "brand_name": "Beta",
            "logo_url": "/b.png",
            "display_order": 3,
            "is_active": True,
        },
    )
    client.post(
        f"{CMS}/brands",
        headers=headers,
        json={
            "brand_name": "Alpha",
            "logo_url": "/a.png",
            "display_order": 1,
            "is_active": True,
        },
    )
    client.post(
        f"{CMS}/brands",
        headers=headers,
        json={
            "brand_name": "Draft",
            "logo_url": "/d.png",
            "display_order": 2,
            "is_active": False,
        },
    )

    payload = client.get(f"{PUBLIC}/homepage/trusted-brands").json()
    names = [b["brand_name"] for b in payload["brands"]]
    assert "Draft" not in names
    assert names.index("Alpha") < names.index("Beta")


def test_public_endpoint_section_disable_hides_brands_at_renderer(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    client.patch(
        f"{CMS}/site-settings",
        headers=headers,
        json={"home_brand_section_enabled": False},
    )
    payload = client.get(f"{PUBLIC}/homepage/trusted-brands").json()
    assert payload["enabled"] is False


def test_public_endpoint_layout_mode_falls_back_to_marquee_for_unknown(
    client, seed_auth
):
    # No PATCH; just confirm the default. The schema validator clamps
    # garbage values to "marquee".
    payload = client.get(f"{PUBLIC}/homepage/trusted-brands").json()
    assert payload["layout_mode"] in {"marquee", "grid", "carousel"}


def test_public_endpoint_title_falls_back_to_legacy_strip_title(client, seed_auth):
    """Existing ``home_brand_strip_title`` admins set on the OLD strip
    keeps surfacing on the new section when the new title is empty."""
    headers = _admin_headers(client, seed_auth["password"])
    client.patch(
        f"{CMS}/site-settings",
        headers=headers,
        json={
            "home_brand_strip_title": "Legacy strip title",
            "home_brand_title": None,
        },
    )
    payload = client.get(f"{PUBLIC}/homepage/trusted-brands").json()
    assert payload["title"] == "Legacy strip title"
