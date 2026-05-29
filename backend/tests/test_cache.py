"""Public-CMS Redis cache + invalidation (Phase B-2).

Exercises the read-through cache decorator + the prefix
invalidation pattern wired into the admin write endpoints. Uses
the autouse ``fake_redis`` fixture so a real Redis isn't required.

Test contract:

* First GET on a cached endpoint hits the DB, response is parked
  in Redis under the declared key.
* Second GET on the same endpoint (within TTL) is served from the
  cache — the DB doesn't see a second query.
* An admin write that invalidates the prefix removes the cached
  value; the next GET rebuilds the cache.
* Query parameters listed in ``vary_by`` produce distinct cache
  keys (the no-filter and filtered responses don't collide).
* Cache failures (Redis down, malformed JSON) degrade silently to
  a fresh DB call rather than 500ing the visitor.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from typing import Generator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.cache import cache_response, clear_cache_prefix
from app.core import redis_client as redis_module
from app.main import app
from app.models.cms import Company, NewsItem, SiteSetting


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_company(db: Session, *, slug: str, name: str, category: str = "retail") -> Company:
    c = Company(
        slug=slug,
        name=name,
        category=category,
        short_description=f"{name} desc",
        initials="".join(word[0].upper() for word in name.split())[:4] or "X",
        is_active=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _seed_news(db: Session, *, slug: str, title: str, is_featured: bool = False) -> NewsItem:
    item = NewsItem(
        slug=slug,
        title=title,
        body="<p>body</p>",
        summary="summary",
        category="company",
        is_published=True,
        is_featured=is_featured,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@contextmanager
def _disable_cache() -> Generator[None, None, None]:
    """Monkey-patch the cache_response wrapper so an individual test
    can run against the underlying endpoint instead of the cached
    one. Not currently used by the tests below but provided as the
    obvious escape hatch."""
    # Placeholder for future tests that need to bypass caching.
    yield


# ---------------------------------------------------------------------------
# Read-through cache: first hit DB, second hit cache
# ---------------------------------------------------------------------------


class TestPublicCompaniesCache:
    def test_first_request_populates_cache(
        self, client: TestClient, db_session: Session, fake_redis
    ):
        _seed_company(db_session, slug="acme", name="Acme")

        r = client.get("/api/v1/public/companies")
        assert r.status_code == 200
        assert any(c["slug"] == "acme" for c in r.json())

        # Cache key reflects the (no-filter) vary_by suffix.
        cached_blob = asyncio.run(
            fake_redis.get("public:companies:category=None")
        )
        assert cached_blob is not None
        assert any(
            c["slug"] == "acme" for c in json.loads(cached_blob)
        )

    def test_second_request_skips_db(
        self, client: TestClient, db_session: Session, fake_redis
    ):
        _seed_company(db_session, slug="acme", name="Acme")
        # Warm the cache.
        first = client.get("/api/v1/public/companies").json()

        # Insert a row directly via the test DB, bypassing the API
        # and therefore the invalidation hook. If the second request
        # truly came from cache, this row must NOT appear.
        _seed_company(db_session, slug="dynamo", name="Dynamo")

        second = client.get("/api/v1/public/companies").json()
        assert {c["slug"] for c in second} == {c["slug"] for c in first}
        assert "dynamo" not in {c["slug"] for c in second}

    def test_vary_by_separates_filtered_responses(
        self, client: TestClient, db_session: Session, fake_redis
    ):
        _seed_company(db_session, slug="ret", name="Retail Co", category="retail")
        _seed_company(
            db_session, slug="dis", name="Distrib Co", category="distribution"
        )

        client.get("/api/v1/public/companies")
        client.get("/api/v1/public/companies?category=retail")

        # Two distinct keys exist after both requests.
        keys = []
        async def _collect():
            async for k in fake_redis.scan_iter(match="public:companies*"):
                keys.append(k)
        asyncio.run(_collect())
        assert sorted(keys) == sorted(
            [
                "public:companies:category=None",
                "public:companies:category='retail'",
            ]
        )

    def test_admin_create_invalidates_cache(
        self, client: TestClient, db_session: Session, fake_redis, seed_auth
    ):
        # Warm the cache as a public visitor.
        client.get("/api/v1/public/companies")
        cached_before = asyncio.run(
            fake_redis.get("public:companies:category=None")
        )
        assert cached_before is not None

        # Admin posts a new company → background task fires
        # clear_cache_prefix.
        password = seed_auth["password"]
        login = client.post(
            "/api/v1/admin/auth/login",
            json={"email": "webadmin@pug.example.com", "password": password},
        )
        token = login.json()["access_token"]
        post = client.post(
            "/api/v1/admin/cms/companies",
            json={
                "slug": "fresh",
                "name": "Fresh Co",
                "category": "retail",
                "short_description": "new",
                "initials": "FC",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert post.status_code == 201, post.text

        # BackgroundTasks run after the response — TestClient awaits
        # them before returning control, so by the time we get
        # here the cache should be cleared.
        cached_after = asyncio.run(
            fake_redis.get("public:companies:category=None")
        )
        assert cached_after is None

        # The next public GET sees the new row.
        fresh = client.get("/api/v1/public/companies").json()
        assert any(c["slug"] == "fresh" for c in fresh)


class TestPublicNewsCache:
    def test_cache_key_varies_on_featured_and_limit(
        self, client: TestClient, db_session: Session, fake_redis
    ):
        _seed_news(db_session, slug="a", title="A", is_featured=True)
        _seed_news(db_session, slug="b", title="B")

        client.get("/api/v1/public/news")
        client.get("/api/v1/public/news?featured=true")
        client.get("/api/v1/public/news?limit=10")

        keys = []
        async def _collect():
            async for k in fake_redis.scan_iter(match="public:news*"):
                keys.append(k)
        asyncio.run(_collect())
        # Three distinct keys for three distinct (featured, limit) combos.
        assert len(set(keys)) == 3

    def test_admin_news_create_invalidates(
        self, client: TestClient, db_session: Session, fake_redis, seed_auth
    ):
        client.get("/api/v1/public/news")
        keys_before = []
        async def _collect_before():
            async for k in fake_redis.scan_iter(match="public:news*"):
                keys_before.append(k)
        asyncio.run(_collect_before())
        assert keys_before  # cache was populated

        password = seed_auth["password"]
        token = client.post(
            "/api/v1/admin/auth/login",
            json={"email": "webadmin@pug.example.com", "password": password},
        ).json()["access_token"]
        client.post(
            "/api/v1/admin/cms/news",
            json={
                "slug": "new-story",
                "title": "Breaking",
                "body": "<p>body</p>",
                "summary": "sum",
                "category": "company",
                "is_published": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        keys_after = []
        async def _collect_after():
            async for k in fake_redis.scan_iter(match="public:news*"):
                keys_after.append(k)
        asyncio.run(_collect_after())
        assert keys_after == []


# ---------------------------------------------------------------------------
# Site settings — no vary_by, simpler key
# ---------------------------------------------------------------------------


class TestSiteSettingsCache:
    def test_site_settings_cache_key_has_no_suffix(
        self, client: TestClient, db_session: Session, fake_redis
    ):
        client.get("/api/v1/public/site-settings")
        cached = asyncio.run(fake_redis.get("public:settings"))
        assert cached is not None
        body = json.loads(cached)
        # Sanity: the cached value is the serialised SiteSettingRead.
        assert "id" in body or "site_name" in body

    def test_admin_patch_invalidates_settings_cache(
        self, client: TestClient, db_session: Session, fake_redis, seed_auth
    ):
        # Pre-populate the singleton row so the patch has something
        # to update.
        db_session.add(SiteSetting(id=1, site_name="Initial"))
        db_session.commit()

        client.get("/api/v1/public/site-settings")
        assert asyncio.run(fake_redis.get("public:settings")) is not None

        password = seed_auth["password"]
        token = client.post(
            "/api/v1/admin/auth/login",
            json={"email": "webadmin@pug.example.com", "password": password},
        ).json()["access_token"]
        client.patch(
            "/api/v1/admin/cms/site-settings",
            json={"site_name": "Updated"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert asyncio.run(fake_redis.get("public:settings")) is None


# ---------------------------------------------------------------------------
# Degraded paths — cache failures must not 500 the visitor
# ---------------------------------------------------------------------------


class TestCacheDegradation:
    def test_redis_get_failure_falls_through_to_db(
        self, client: TestClient, db_session: Session, monkeypatch
    ):
        # Replace the fake's ``get`` with one that raises. The route
        # should still respond 200 with the live DB result.
        from app.core import redis_client as redis_module

        fake = redis_module.get_redis_client()
        monkeypatch.setattr(
            fake, "get", AsyncMock(side_effect=RuntimeError("redis down"))
        )

        _seed_company(db_session, slug="resilient", name="Resilient")
        r = client.get("/api/v1/public/companies")
        assert r.status_code == 200
        assert any(c["slug"] == "resilient" for c in r.json())

    def test_malformed_cached_payload_is_treated_as_miss(
        self, client: TestClient, db_session: Session, fake_redis
    ):
        _seed_company(db_session, slug="recover", name="Recover")
        # Plant a non-JSON value at the cache key.
        asyncio.run(
            fake_redis.set("public:companies:category=None", "{ this is not json")
        )

        r = client.get("/api/v1/public/companies")
        assert r.status_code == 200
        assert any(c["slug"] == "recover" for c in r.json())


# ---------------------------------------------------------------------------
# Prefix invalidator unit test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_cache_prefix_deletes_matching_keys(fake_redis):
    await fake_redis.set("public:companies:foo", "x")
    await fake_redis.set("public:companies:bar", "y")
    await fake_redis.set("public:news:zzz", "z")

    deleted = await clear_cache_prefix("public:companies")
    assert deleted == 2

    # Companies keys gone, news untouched.
    assert await fake_redis.get("public:companies:foo") is None
    assert await fake_redis.get("public:companies:bar") is None
    assert await fake_redis.get("public:news:zzz") == "z"


@pytest.mark.asyncio
async def test_clear_cache_prefix_with_empty_prefix_is_noop(fake_redis):
    await fake_redis.set("k", "v")
    deleted = await clear_cache_prefix("")
    assert deleted == 0
    assert await fake_redis.get("k") == "v"


# ---------------------------------------------------------------------------
# Decorator preserves the underlying signature for FastAPI
# ---------------------------------------------------------------------------


def test_decorator_preserves_route_signature_for_fastapi():
    """If ``functools.wraps`` plus our manual ``__signature__`` pin
    weren't applied, FastAPI would either choke on the forward refs
    or drop dependency-injected parameters. Snapshot the parameter
    names to lock in the contract."""
    import inspect

    from app.api.endpoints.public import list_active_companies

    sig = inspect.signature(list_active_companies)
    assert "db" in sig.parameters
    assert "category" in sig.parameters
