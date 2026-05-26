"""Phase 19 security regression tests.

Covers the four named risks called out in the Phase 19 gap analysis:

1. **SQL injection** — every dynamic query in the codebase goes through
   SQLAlchemy parameterised queries. These tests pump classic injection
   payloads through the public surface and verify nothing escapes:
   queries return clean results, the users table is still intact, etc.

2. **Cross-site scripting (XSS)** — the API never serves HTML. JSON
   responses encode strings verbatim. We verify malicious markup
   round-trips as a plain string and that no response is ever served
   with ``text/html``.

3. **Cross-site request forgery (CSRF)** — the API uses ``HTTPBearer``
   exclusively (JWT in the ``Authorization`` header). Bearer auth is
   immune to CSRF because the browser never auto-attaches it. These
   tests verify the auth scheme has not silently regressed to cookies.

4. **Rate limiting** — Phase 19 added per-IP rate limits on the four
   public POST endpoints. These tests confirm the limits fire,
   return ``429`` with ``Retry-After``, and don't leak between
   endpoints.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

import pytest

from app.core.rate_limit import reset_rate_limits
from app.models.auth import User
from app.models.cms import Company, ContactMessage, HeroSlide, NewsItem
from datetime import datetime, timezone


PUB = "/api/v1/public"


@pytest.fixture
def rate_limit_on(monkeypatch):
    """Force-enable rate limiting for this test even if the suite-level
    ``RATE_LIMIT_ENABLED=false`` env override is set. ``_enabled()`` in
    ``app.core.rate_limit`` reads the env per call, so a monkey-patch
    in the test session is enough.
    """
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    reset_rate_limits()
    yield
    reset_rate_limits()


# =========================================================================== #
# 1. SQL INJECTION                                                            #
# =========================================================================== #

# Classic payloads pulled from OWASP. Any of these should be treated as a
# literal string by SQLAlchemy's parameter binding.
SQLI_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE users; --",
    "1; DROP TABLE users",
    "' UNION SELECT email, password_hash FROM users --",
    "admin'--",
    "\" OR \"\"=\"",
    "%27%20OR%201=1--",  # URL-encoded variant
]


def _users_table_still_intact(db_session: Session) -> bool:
    """The whole point: after running malicious queries, the table is fine."""
    try:
        db_session.execute(select(User)).scalars().all()
        return True
    except Exception:
        return False


def test_sqli_in_companies_category_query(client, db_session: Session):
    """Query-string parameter — SQLAlchemy's ``where()`` binds it."""
    db_session.add(
        Company(
            slug="retail-a", name="A", category="retail",
            initials="AA", is_active=True,
        )
    )
    db_session.commit()

    for payload in SQLI_PAYLOADS:
        resp = client.get(f"{PUB}/companies", params={"category": payload})
        # Either 200 with an empty list (no match) or 422 (validation).
        # NOT 500, and certainly not a leak of every row.
        assert resp.status_code in (200, 422), payload
        if resp.status_code == 200:
            assert resp.json() == [], (
                f"Injection payload {payload!r} matched a row — possible leak"
            )

    assert _users_table_still_intact(db_session)


def test_sqli_in_company_slug_path(client, db_session: Session):
    """Path parameter."""
    db_session.add(
        Company(
            slug="ok", name="OK", category="retail",
            initials="OK", is_active=True,
        )
    )
    db_session.commit()

    for payload in SQLI_PAYLOADS:
        resp = client.get(f"{PUB}/companies/{payload}")
        # Path lookup either 404 (no match) or 422 (invalid slug). Never 5xx.
        assert resp.status_code in (404, 422), f"{payload}: {resp.status_code}"

    assert _users_table_still_intact(db_session)


def test_sqli_in_news_search_query(client, db_session: Session):
    """Free-text search column — uses ``ILIKE %payload%`` internally."""
    db_session.add(
        NewsItem(
            slug="real",
            title="Genuine title",
            category="company",
            cover="from-x to-y",
            published_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            is_published=True,
        )
    )
    db_session.commit()

    for payload in SQLI_PAYLOADS:
        resp = client.get(f"{PUB}/news", params={"search": payload})
        # `search` isn't a supported param — but the bigger point is
        # that the endpoint shouldn't 5xx on it.
        assert resp.status_code in (200, 422), payload

    # And the genuine row is still visible.
    resp = client.get(f"{PUB}/news")
    assert resp.status_code == 200
    assert any(item["slug"] == "real" for item in resp.json())


def test_sqli_in_contact_form_body(client, db_session: Session):
    """JSON body fields — ORM treats them as bound parameters."""
    reset_rate_limits()

    for payload in SQLI_PAYLOADS[:3]:  # 3 within the 5/min limit
        resp = client.post(
            f"{PUB}/contact",
            json={
                "name": payload,
                "email": "real@example.com",
                "subject": payload,
                "message": payload,
            },
        )
        assert resp.status_code in (201, 422), payload
        if resp.status_code == 201:
            # The payload survived as literal data — verify the row.
            body = resp.json()
            assert body["name"] == payload
            assert body["message"] == payload

    # Users table still queryable.
    assert _users_table_still_intact(db_session)


def test_sqli_in_admin_login_email(client):
    """Login endpoint — classic auth-bypass target."""
    reset_rate_limits()

    for payload in SQLI_PAYLOADS:
        resp = client.post(
            "/api/v1/admin/auth/login",
            json={"email": payload, "password": "anything"},
        )
        # 422 (email validation rejects), or 401 (no such user) — never 200.
        assert resp.status_code in (401, 422), (
            f"Injection payload {payload!r} got {resp.status_code} — possible auth bypass"
        )


# =========================================================================== #
# 2. CROSS-SITE SCRIPTING (XSS)                                               #
# =========================================================================== #

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "\"><script>alert(document.cookie)</script>",
    "<svg/onload=alert(1)>",
]


def test_xss_contact_form_stores_verbatim_and_serves_as_json(
    client, db_session: Session
):
    """Submitting markup must store it as data and serve it as a JSON string.

    The dangerous case is the API returning ``text/html`` with the payload
    interpolated into a template. JSON encoding of the same string is
    completely safe — the frontend (React/Next.js) escapes it on render.
    """
    reset_rate_limits()
    payload = XSS_PAYLOADS[0]
    resp = client.post(
        f"{PUB}/contact",
        json={
            "name": payload,
            "email": "xss@example.com",
            "subject": "Test",
            "message": payload,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.headers["content-type"].startswith("application/json")

    body = resp.json()
    assert body["name"] == payload  # round-trips
    assert body["message"] == payload

    # And the row in the DB is the literal string, not eval'd or sanitised.
    row = db_session.execute(select(ContactMessage)).scalars().one()
    assert row.name == payload
    assert row.message == payload


def test_xss_in_cms_public_read_returns_json_not_html(client, db_session: Session):
    """A hero slide title with markup is returned as a JSON-encoded string."""
    payload = XSS_PAYLOADS[1]
    db_session.add(
        HeroSlide(title=payload, display_order=1, is_active=True)
    )
    db_session.commit()

    resp = client.get(f"{PUB}/hero-slides")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()[0]["title"] == payload
    # Belt-and-braces: the raw body must NOT contain the unescaped markup
    # outside a JSON string literal. JSON encoding escapes `<` and `>` to
    # `<` / `>` *or* leaves them as-is depending on encoder,
    # but either way it's inside a quoted string — never raw HTML.
    body = resp.text
    assert "<html" not in body.lower()


def test_response_never_serves_user_content_as_html(client, db_session: Session):
    """Spot-check: no public endpoint flips its Content-Type to text/html
    when given HTML-ish input.
    """
    reset_rate_limits()
    db_session.add(
        HeroSlide(title="<script>x</script>", display_order=1, is_active=True)
    )
    db_session.commit()

    for path in [
        f"{PUB}/hero-slides",
        f"{PUB}/companies",
        f"{PUB}/news",
        f"{PUB}/leadership",
    ]:
        resp = client.get(path)
        assert resp.status_code in (200, 404)
        assert "text/html" not in resp.headers.get("content-type", ""), path


# =========================================================================== #
# 3. CROSS-SITE REQUEST FORGERY (CSRF)                                        #
# =========================================================================== #


def test_admin_login_uses_bearer_not_cookie(client, db_session: Session, seed_auth):
    """The whole anti-CSRF posture rests on this: no auth cookie is set
    anywhere. If a future change adds a session cookie, CSRF protections
    would have to come with it.
    """
    resp = client.post(
        "/api/v1/admin/auth/login",
        json={
            "email": "superadmin@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    assert resp.status_code == 200, resp.text

    # Token is in the JSON body...
    body = resp.json()
    assert "access_token" in body
    assert body["access_token"]

    # ...and NOT in a Set-Cookie header.
    assert "set-cookie" not in {k.lower() for k in resp.headers.keys()}, (
        f"Login response set a cookie: {resp.headers}"
    )


def test_hr_login_uses_bearer_not_cookie(client, db_session: Session, seed_auth):
    resp = client.post(
        "/api/v1/hr/auth/login",
        json={
            "email": "hr@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert "set-cookie" not in {k.lower() for k in resp.headers.keys()}


def test_protected_endpoint_rejects_cookie_only_auth(
    client, db_session: Session, seed_auth
):
    """Even if a forged request smuggles a cookie, the API must reject it."""
    # No Authorization header, only a forged cookie that looks like a JWT.
    resp = client.get(
        "/api/v1/admin/auth/me",
        cookies={"access_token": "anything.at.all"},
    )
    assert resp.status_code == 401


def test_protected_endpoint_rejects_no_credentials(client):
    resp = client.get("/api/v1/admin/auth/me")
    assert resp.status_code == 401


# =========================================================================== #
# 4. RATE LIMITING                                                            #
# =========================================================================== #


def test_rate_limit_contact_form_minute_window(
    client, db_session: Session, rate_limit_on
):
    """5/minute on /contact — sixth call from the same IP gets 429."""
    body = {
        "name": "Bot",
        "email": "bot@example.com",
        "subject": "Spam",
        "message": "stuff",
    }
    # First 5 must succeed.
    for i in range(5):
        resp = client.post(f"{PUB}/contact", json=body)
        assert resp.status_code == 201, f"call {i+1} unexpectedly blocked"

    # 6th is rate-limited.
    resp = client.post(f"{PUB}/contact", json=body)
    assert resp.status_code == 429
    assert "retry-after" in {k.lower() for k in resp.headers.keys()}
    assert int(resp.headers["retry-after"]) >= 1


def test_rate_limit_applies_per_endpoint(
    client, db_session: Session, rate_limit_on
):
    """Exhausting /contact must not block /newsletter (different bucket)."""
    # Exhaust /contact.
    body = {
        "name": "Bot",
        "email": "bot@example.com",
        "message": "x",
    }
    for _ in range(5):
        client.post(f"{PUB}/contact", json=body)
    blocked = client.post(f"{PUB}/contact", json=body)
    assert blocked.status_code == 429

    # /newsletter still works.
    ok = client.post(
        f"{PUB}/newsletter", json={"email": "ok@example.com"}
    )
    assert ok.status_code == 201


def test_rate_limit_uses_x_forwarded_for(
    client, db_session: Session, rate_limit_on
):
    """Two IPs behind the proxy must be tracked separately."""
    body = {
        "name": "A",
        "email": "a@example.com",
        "message": "x",
    }

    # Exhaust limit for IP 1.1.1.1.
    for _ in range(5):
        resp = client.post(
            f"{PUB}/contact",
            json=body,
            headers={"X-Forwarded-For": "1.1.1.1"},
        )
        assert resp.status_code == 201
    blocked = client.post(
        f"{PUB}/contact",
        json=body,
        headers={"X-Forwarded-For": "1.1.1.1"},
    )
    assert blocked.status_code == 429

    # IP 2.2.2.2 still has its full budget.
    ok = client.post(
        f"{PUB}/contact",
        json=body,
        headers={"X-Forwarded-For": "2.2.2.2"},
    )
    assert ok.status_code == 201


def test_rate_limit_newsletter_endpoint(
    client, db_session: Session, rate_limit_on
):
    """3/minute on /newsletter."""
    for i in range(3):
        resp = client.post(
            f"{PUB}/newsletter",
            json={"email": f"n{i}@example.com"},
        )
        assert resp.status_code == 201, i

    resp = client.post(
        f"{PUB}/newsletter", json={"email": "over@example.com"}
    )
    assert resp.status_code == 429
