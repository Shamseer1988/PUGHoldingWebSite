"""Tests for the public Cache-Control middleware."""
from __future__ import annotations


def test_cms_endpoint_is_no_store(client):
    """CMS endpoints (site-settings, leadership, companies, …) must
    ship a no-cache / no-store header so admin edits propagate
    immediately and partial responses can't be cached and replayed
    by Cloudflare or Next.js for 60 s. This is the fix for the
    'footer / leadership fields disappear on refresh' bug."""
    resp = client.get("/api/v1/public/site-settings")
    assert resp.status_code == 200
    cc = resp.headers.get("cache-control", "")
    assert "no-store" in cc
    assert "no-cache" in cc
    assert "must-revalidate" in cc
    assert "max-age=0" in cc
    # Belt-and-braces for the few ancient proxies that still respect
    # Pragma / Expires.
    assert resp.headers.get("pragma", "").lower() == "no-cache"
    assert resp.headers.get("expires") == "0"
    # Vary should include Origin so CORS doesn't collide across domains.
    assert "Origin" in resp.headers.get("vary", "")


def test_all_cms_paths_carry_no_store(client, seed_auth, db_session):
    """Every prefix the middleware flags as CMS must serve no-store —
    not just /site-settings."""
    # Seed something so the read endpoints have rows to return.
    from app.models.cms import HeroSlide

    db_session.add(HeroSlide(title="x", display_order=1, is_active=True))
    db_session.commit()

    for path in (
        "/api/v1/public/site-settings",
        "/api/v1/public/leadership",
        "/api/v1/public/companies",
        "/api/v1/public/hero-slides",
        "/api/v1/public/navigation",
        "/api/v1/public/news",
        "/api/v1/public/pages",
        "/api/v1/public/media",
        "/api/v1/public/site-pages/about",
    ):
        resp = client.get(path)
        # Not every endpoint returns 200 on a fresh test DB (some 404),
        # but the middleware only adds headers on 2xx responses anyway.
        if 200 <= resp.status_code < 300:
            cc = resp.headers.get("cache-control", "")
            assert "no-store" in cc, f"{path} missing no-store: {cc!r}"


def test_admin_endpoint_is_not_cached(client, seed_auth):
    """Even on GET, /admin/* must NEVER carry Cache-Control."""
    auth = client.post(
        "/api/v1/admin/auth/login",
        json={
            "email": "superadmin@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    token = auth.json()["access_token"]
    resp = client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "cache-control" not in {k.lower() for k in resp.headers.keys()}


def test_post_is_not_cached(client):
    """The middleware must skip non-GET methods even on /public/*."""
    # Use newsletter — the simplest 2xx POST. Avoid contact-form quota
    # by using a unique email per call.
    resp = client.post(
        "/api/v1/public/newsletter",
        json={"email": "no-cache@example.com"},
    )
    assert resp.status_code == 201
    assert "cache-control" not in {k.lower() for k in resp.headers.keys()}


def test_404_is_not_cached(client):
    """4xx responses must not be edge-cached."""
    resp = client.get("/api/v1/public/site-pages/not-a-real-page")
    assert resp.status_code == 404
    assert "cache-control" not in {k.lower() for k in resp.headers.keys()}


def test_disabled_via_env(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_CACHE_HEADERS_ENABLED", "false")
    resp = client.get("/api/v1/public/site-settings")
    assert resp.status_code == 200
    assert "cache-control" not in {k.lower() for k in resp.headers.keys()}
