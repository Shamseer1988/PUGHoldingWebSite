"""Tests for the public Cache-Control middleware."""
from __future__ import annotations


def test_public_get_carries_cache_control(client):
    """A read endpoint under /public/* must come back with a
    Cache-Control suitable for edge caching."""
    resp = client.get("/api/v1/public/site-settings")
    assert resp.status_code == 200
    cc = resp.headers.get("cache-control", "")
    assert "s-maxage=60" in cc
    assert "stale-while-revalidate=3600" in cc
    # Vary should include Origin so CORS doesn't collide across domains.
    assert "Origin" in resp.headers.get("vary", "")


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
