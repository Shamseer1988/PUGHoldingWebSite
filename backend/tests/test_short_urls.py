"""Admin CRUD + public redirect for the URL Shortener (Marketing → Tools).

Covers:

* ``POST /admin/marketing/short-urls`` — create with custom slug,
  auto-generated slug, validation errors, slug conflict.
* ``GET  /admin/marketing/short-urls`` — list + search.
* ``PATCH /admin/marketing/short-urls/{id}`` — target swap +
  disable.
* ``DELETE /admin/marketing/short-urls/{id}``.
* ``GET /go/{slug}`` — 302 to target + click counter, 404 for
  missing/inactive/expired/invalid-shape slugs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.short_url import ShortUrl


ADMIN_LOGIN = "/api/v1/admin/auth/login"
BASE = "/api/v1/admin/marketing/short-urls"
PUBLIC_BASE = "/api/v1/go"


def _auth(client: TestClient, password: str) -> dict[str, str]:
    r = client.post(
        ADMIN_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_with_custom_slug(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        BASE,
        headers=headers,
        json={
            "slug": "summer-25",
            "target_url": "https://parisunitedgroup.com/offers/summer",
            "title": "Summer mailer",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slug"] == "summer-25"
    assert body["target_url"] == "https://parisunitedgroup.com/offers/summer"
    assert body["title"] == "Summer mailer"
    assert body["click_count"] == 0
    assert body["is_active"] is True


def test_create_autogenerates_slug_when_omitted(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        BASE,
        headers=headers,
        json={"target_url": "https://example.com/landing"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # 7 chars from the lower-case alphabet + digits.
    assert len(body["slug"]) == 7
    assert body["slug"].isalnum()
    assert body["slug"] == body["slug"].lower()


def test_create_normalises_slug_to_lowercase(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        BASE,
        headers=headers,
        json={"slug": "Summer-25", "target_url": "https://example.com/x"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["slug"] == "summer-25"


def test_create_rejects_bad_target_url(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        BASE, headers=headers, json={"target_url": "ftp://example.com"}
    )
    assert r.status_code == 422, r.text


def test_create_rejects_reserved_slug(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        BASE,
        headers=headers,
        json={"slug": "admin", "target_url": "https://example.com/x"},
    )
    assert r.status_code == 422, r.text


def test_create_rejects_too_short_slug(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    r = client.post(
        BASE,
        headers=headers,
        json={"slug": "ab", "target_url": "https://example.com/x"},
    )
    assert r.status_code == 422


def test_create_rejects_duplicate_slug(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    r1 = client.post(
        BASE,
        headers=headers,
        json={"slug": "dup-test", "target_url": "https://example.com/a"},
    )
    assert r1.status_code == 201
    r2 = client.post(
        BASE,
        headers=headers,
        json={"slug": "dup-test", "target_url": "https://example.com/b"},
    )
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# List / detail
# ---------------------------------------------------------------------------


def test_list_returns_paginated_items_with_total(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    for i in range(3):
        client.post(
            BASE,
            headers=headers,
            json={
                "slug": f"list-{i}",
                "target_url": f"https://example.com/{i}",
            },
        )
    r = client.get(BASE, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_search_filters_by_slug(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    client.post(
        BASE,
        headers=headers,
        json={"slug": "haystack", "target_url": "https://example.com/h"},
    )
    client.post(
        BASE,
        headers=headers,
        json={"slug": "needle", "target_url": "https://example.com/n"},
    )
    r = client.get(f"{BASE}?search=needle", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["slug"] == "needle"


# ---------------------------------------------------------------------------
# Update + delete
# ---------------------------------------------------------------------------


def test_patch_target_url(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    created = client.post(
        BASE,
        headers=headers,
        json={"slug": "patch-me", "target_url": "https://example.com/old"},
    ).json()
    r = client.patch(
        f"{BASE}/{created['id']}",
        headers=headers,
        json={"target_url": "https://example.com/new"},
    )
    assert r.status_code == 200
    assert r.json()["target_url"] == "https://example.com/new"


def test_patch_disables_link(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    created = client.post(
        BASE,
        headers=headers,
        json={"slug": "disable-me", "target_url": "https://example.com/x"},
    ).json()
    r = client.patch(
        f"{BASE}/{created['id']}", headers=headers, json={"is_active": False}
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_delete_short_url(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    created = client.post(
        BASE,
        headers=headers,
        json={"slug": "delete-me", "target_url": "https://example.com/d"},
    ).json()
    r = client.delete(f"{BASE}/{created['id']}", headers=headers)
    assert r.status_code == 204
    assert client.get(f"{BASE}/{created['id']}", headers=headers).status_code == 404


def test_unauthenticated_admin_call_is_rejected(client: TestClient, seed_auth):
    # No bearer header — must 401 not 200.
    r = client.get(BASE)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Public redirect
# ---------------------------------------------------------------------------


def test_public_redirects_to_target_and_bumps_counter(
    client: TestClient, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    client.post(
        BASE,
        headers=headers,
        json={"slug": "go-here", "target_url": "https://example.com/landing"},
    )
    r = client.get(
        f"{PUBLIC_BASE}/go-here", follow_redirects=False
    )
    assert r.status_code == 302
    assert r.headers["location"] == "https://example.com/landing"

    row = db_session.query(ShortUrl).filter(ShortUrl.slug == "go-here").first()
    db_session.refresh(row)
    assert row.click_count == 1
    assert row.last_click_at is not None


def test_public_redirect_handles_mixed_case_slug(
    client: TestClient, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    client.post(
        BASE,
        headers=headers,
        json={"slug": "mixedcase", "target_url": "https://example.com/m"},
    )
    r = client.get(f"{PUBLIC_BASE}/MixedCase", follow_redirects=False)
    assert r.status_code == 302


def test_public_redirect_404s_when_disabled(
    client: TestClient, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    created = client.post(
        BASE,
        headers=headers,
        json={"slug": "off-air", "target_url": "https://example.com/o"},
    ).json()
    client.patch(
        f"{BASE}/{created['id']}", headers=headers, json={"is_active": False}
    )
    r = client.get(f"{PUBLIC_BASE}/off-air", follow_redirects=False)
    assert r.status_code == 404


def test_public_redirect_404s_when_expired(
    client: TestClient, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    client.post(
        BASE,
        headers=headers,
        json={
            "slug": "expired",
            "target_url": "https://example.com/e",
            "expires_at": yesterday,
        },
    )
    r = client.get(f"{PUBLIC_BASE}/expired", follow_redirects=False)
    assert r.status_code == 404


def test_public_redirect_404s_for_missing_slug(client: TestClient):
    r = client.get(f"{PUBLIC_BASE}/no-such-thing", follow_redirects=False)
    assert r.status_code == 404


@pytest.mark.parametrize("slug", ["ab", "x" * 64, "ADMIN-CAPS!", "with space"])
def test_public_redirect_rejects_invalid_slug_shapes(
    client: TestClient, slug: str
):
    r = client.get(f"{PUBLIC_BASE}/{slug}", follow_redirects=False)
    assert r.status_code == 404
