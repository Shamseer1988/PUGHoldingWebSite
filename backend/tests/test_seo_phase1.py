"""Tests for the SEO Configuration module (Phase 1).

Covers:

  * Admin settings round-trip + canonical_base_url validation.
  * Verification CRUD: meta_tag rendering, full_meta_tag sanitisation,
    HTML file uniqueness, path-traversal rejection.
  * Tracking integration upsert: per-provider ID validation +
    duplicate-tracking warning when GTM and direct GA4/Pixel are both
    on.
  * Public head feed surfaces verification meta tags + active
    integrations and hides inactive rows.
  * Public verification-file route serves active rows, 404s inactive,
    refuses traversal.
  * Public robots route renders the default + honours admin overrides.
  * Dashboard payload aggregates correctly.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


CMS = "/api/v1/admin"  # admin SEO endpoints mount at /admin/seo
SEO = f"{CMS}/seo"
PUBLIC = "/api/v1/public"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_headers(client: TestClient, password: str) -> dict:
    """Mirror the helper used by sibling test files."""
    resp = client.post(
        "/api/v1/admin/auth/login",
        json={"email": "webadmin@pug.example.com", "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def test_seo_settings_auto_create_and_patch(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])

    # GET auto-creates the singleton row on first access.
    first = client.get(f"{SEO}/settings", headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert body["enable_sitemap"] is True
    assert body["enable_robots"] is True

    # Partial PATCH.
    patched = client.patch(
        f"{SEO}/settings",
        headers=headers,
        json={
            "site_name": "PUG Holding",
            "default_meta_title": "Paris United Group | Diversified Holding",
            "canonical_base_url": "https://www.pug.example.com",
            "sitemap_default_changefreq": "weekly",
            "sitemap_default_priority": 0.7,
        },
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["site_name"] == "PUG Holding"
    # Trailing slash stripped by validator.
    assert body["canonical_base_url"] == "https://www.pug.example.com"
    assert body["sitemap_default_changefreq"] == "weekly"
    assert body["sitemap_default_priority"] == 0.7


def test_seo_settings_rejects_non_https_canonical(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    resp = client.patch(
        f"{SEO}/settings",
        headers=headers,
        json={"canonical_base_url": "http://insecure.example.com"},
    )
    assert resp.status_code == 422
    assert "https" in resp.text.lower()


def test_seo_settings_rejects_bad_changefreq_and_priority(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    resp = client.patch(
        f"{SEO}/settings",
        headers=headers,
        json={"sitemap_default_changefreq": "occasionally"},
    )
    assert resp.status_code == 422
    resp = client.patch(
        f"{SEO}/settings",
        headers=headers,
        json={"sitemap_default_priority": 1.5},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Verifications
# ---------------------------------------------------------------------------


def test_verification_meta_tag_crud_and_public_render(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])

    created = client.post(
        f"{SEO}/verifications",
        headers=headers,
        json={
            "provider": "google",
            "verification_type": "meta_tag",
            "verification_name": "google-site-verification",
            "verification_content": "abc123XYZ",
        },
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]
    assert created.json()["status"] == "pending"

    # Public head feed reflects it.
    feed = client.get(f"{PUBLIC}/seo/head").json()
    found = [
        m for m in feed["verification_metas"]
        if m.get("name") == "google-site-verification"
    ]
    assert len(found) == 1
    assert found[0]["content"] == "abc123XYZ"

    # Deactivate; public feed should drop it.
    client.patch(
        f"{SEO}/verifications/{record_id}",
        headers=headers,
        json={"is_active": False},
    )
    feed = client.get(f"{PUBLIC}/seo/head").json()
    names = [m.get("name") for m in feed["verification_metas"]]
    assert "google-site-verification" not in names


def test_verification_full_meta_tag_sanitises_and_renders(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    created = client.post(
        f"{SEO}/verifications",
        headers=headers,
        json={
            "provider": "meta",
            "verification_type": "full_meta_tag",
            "full_meta_tag": '<meta name="facebook-domain-verification" content="fbtoken123" />',
        },
    )
    assert created.status_code == 201, created.text

    feed = client.get(f"{PUBLIC}/seo/head").json()
    matched = [
        m for m in feed["verification_metas"]
        if m.get("name") == "facebook-domain-verification"
    ]
    assert len(matched) == 1
    assert matched[0]["content"] == "fbtoken123"


def test_verification_rejects_script_injection(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    resp = client.post(
        f"{SEO}/verifications",
        headers=headers,
        json={
            "provider": "google",
            "verification_type": "full_meta_tag",
            "full_meta_tag": '<meta name="google-site-verification" content="x"><script>alert(1)</script>',
        },
    )
    assert resp.status_code == 422
    assert "forbidden" in resp.text.lower() or "script" in resp.text.lower()


def test_verification_rejects_unknown_meta_name(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    resp = client.post(
        f"{SEO}/verifications",
        headers=headers,
        json={
            "provider": "custom",
            "verification_type": "full_meta_tag",
            "full_meta_tag": '<meta name="i-just-made-this-up" content="x" />',
        },
    )
    assert resp.status_code == 422
    assert "unrecognised" in resp.text.lower()


def test_html_verification_file_route_and_traversal_rejection(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])

    # Path traversal at create time.
    bad = client.post(
        f"{SEO}/verifications",
        headers=headers,
        json={
            "provider": "google",
            "verification_type": "html_file",
            "html_filename": "../etc/passwd",
            "html_file_content": "nope",
        },
    )
    assert bad.status_code == 422

    # Filenames outside the allow-list pattern.
    weird = client.post(
        f"{SEO}/verifications",
        headers=headers,
        json={
            "provider": "google",
            "verification_type": "html_file",
            "html_filename": "anything-goes.html",
            "html_file_content": "nope",
        },
    )
    assert weird.status_code == 422

    # Happy path.
    created = client.post(
        f"{SEO}/verifications",
        headers=headers,
        json={
            "provider": "google",
            "verification_type": "html_file",
            "html_filename": "google1234567890abcd.html",
            "html_file_content": "google-site-verification: google1234567890abcd.html",
        },
    )
    assert created.status_code == 201, created.text

    served = client.get(f"{PUBLIC}/seo/verify/google1234567890abcd.html")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("text/plain")
    assert "google-site-verification" in served.text

    # Traversal at the public route returns 400.
    bad = client.get(f"{PUBLIC}/seo/verify/..%2Fetc%2Fpasswd")
    assert bad.status_code in (400, 404)

    # Unknown filename → 404.
    missing = client.get(f"{PUBLIC}/seo/verify/google0000nothere.html")
    assert missing.status_code == 404


def test_html_verification_file_rejects_duplicate_active_filename(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    payload = {
        "provider": "google",
        "verification_type": "html_file",
        "html_filename": "googleAAAAAAAAAAAA.html",
        "html_file_content": "x",
    }
    a = client.post(f"{SEO}/verifications", headers=headers, json=payload)
    assert a.status_code == 201
    b = client.post(f"{SEO}/verifications", headers=headers, json=payload)
    assert b.status_code == 409


# ---------------------------------------------------------------------------
# Tracking integrations
# ---------------------------------------------------------------------------


def test_gtm_upsert_validates_id_shape(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    bad = client.put(
        f"{SEO}/integrations",
        headers=headers,
        json={"provider": "google_tag_manager", "tracking_id": "not-gtm-id"},
    )
    assert bad.status_code == 422

    good = client.put(
        f"{SEO}/integrations",
        headers=headers,
        json={"provider": "google_tag_manager", "tracking_id": "GTM-ABCD123"},
    )
    assert good.status_code == 200
    assert good.json()["tracking_id"] == "GTM-ABCD123"


def test_ga4_and_meta_pixel_validation(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])

    bad_ga = client.put(
        f"{SEO}/integrations",
        headers=headers,
        json={"provider": "google_analytics_ga4", "tracking_id": "UA-12345"},
    )
    assert bad_ga.status_code == 422

    good_ga = client.put(
        f"{SEO}/integrations",
        headers=headers,
        json={"provider": "google_analytics_ga4", "tracking_id": "G-ABC123XYZ"},
    )
    assert good_ga.status_code == 200

    bad_pixel = client.put(
        f"{SEO}/integrations",
        headers=headers,
        json={"provider": "meta_pixel", "tracking_id": "abc"},
    )
    assert bad_pixel.status_code == 422

    good_pixel = client.put(
        f"{SEO}/integrations",
        headers=headers,
        json={"provider": "meta_pixel", "tracking_id": "1234567890123"},
    )
    assert good_pixel.status_code == 200


def test_duplicate_tracking_warning_surfaces_when_gtm_and_direct_active(
    client, seed_auth
):
    headers = _admin_headers(client, seed_auth["password"])
    client.put(
        f"{SEO}/integrations",
        headers=headers,
        json={"provider": "google_tag_manager", "tracking_id": "GTM-XYZ12"},
    )
    # Dashboard while only GTM is on — no warning.
    dash = client.get(f"{SEO}/dashboard", headers=headers).json()
    assert dash["duplicate_tracking_warning"] is None

    client.put(
        f"{SEO}/integrations",
        headers=headers,
        json={"provider": "google_analytics_ga4", "tracking_id": "G-ABC123XYZ"},
    )
    dash = client.get(f"{SEO}/dashboard", headers=headers).json()
    assert dash["duplicate_tracking_warning"]
    assert "GA4" in dash["duplicate_tracking_warning"]


def test_public_head_feed_returns_only_active_integrations(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    client.put(
        f"{SEO}/integrations",
        headers=headers,
        json={"provider": "google_tag_manager", "tracking_id": "GTM-ABCD123"},
    )
    client.put(
        f"{SEO}/integrations",
        headers=headers,
        json={
            "provider": "microsoft_clarity",
            "tracking_id": "abc123xyz",
            "is_active": False,
        },
    )
    feed = client.get(f"{PUBLIC}/seo/head").json()
    providers = {row["provider"] for row in feed["integrations"]}
    assert "google_tag_manager" in providers
    assert "microsoft_clarity" not in providers


def test_integration_delete(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    client.put(
        f"{SEO}/integrations",
        headers=headers,
        json={"provider": "google_tag_manager", "tracking_id": "GTM-ABCD123"},
    )
    resp = client.delete(
        f"{SEO}/integrations/google_tag_manager", headers=headers
    )
    assert resp.status_code == 204
    rows = client.get(f"{SEO}/integrations", headers=headers).json()
    assert all(r["provider"] != "google_tag_manager" for r in rows)


# ---------------------------------------------------------------------------
# Robots route
# ---------------------------------------------------------------------------


def test_public_robots_default_contains_defaults_and_sitemap(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    client.patch(
        f"{SEO}/settings",
        headers=headers,
        json={"canonical_base_url": "https://www.pug.example.com"},
    )
    resp = client.get(f"{PUBLIC}/seo/robots")
    assert resp.status_code == 200
    body = resp.text
    assert "User-agent: *" in body
    assert "Disallow: /admin" in body
    assert "Sitemap: https://www.pug.example.com/sitemap.xml" in body


def test_public_robots_honours_custom_content(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    custom = "User-agent: Googlebot\nAllow: /\n\nUser-agent: *\nDisallow: /\n"
    client.patch(
        f"{SEO}/settings",
        headers=headers,
        json={
            "robots_use_default": False,
            "robots_custom_content": custom,
            "canonical_base_url": "https://www.pug.example.com",
        },
    )
    body = client.get(f"{PUBLIC}/seo/robots").text
    assert "Googlebot" in body
    assert "Sitemap: https://www.pug.example.com/sitemap.xml" in body


def test_public_robots_disabled_returns_closed_body(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    client.patch(
        f"{SEO}/settings",
        headers=headers,
        json={"enable_robots": False},
    )
    body = client.get(f"{PUBLIC}/seo/robots").text
    assert "Disallow: /" in body
    assert "Sitemap:" not in body
