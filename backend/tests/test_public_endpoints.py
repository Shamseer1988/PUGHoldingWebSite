"""Integration tests for the public /public/* endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
from app.models.cms import (
    Company,
    HeroSlide,
    LeadershipMessage,
    NewsItem,
    NewsletterSubscriber,
)


PUB = "/api/v1/public"


# ---------------------------------------------------------------------------
# Read endpoints filter inactive / unpublished rows
# ---------------------------------------------------------------------------


def test_hero_slides_only_returns_active(client, db_session: Session):
    db_session.add_all(
        [
            HeroSlide(title="Active", display_order=1, is_active=True),
            HeroSlide(title="Hidden", display_order=2, is_active=False),
        ]
    )
    db_session.commit()

    response = client.get(f"{PUB}/hero-slides")
    assert response.status_code == 200
    titles = [s["title"] for s in response.json()]
    assert titles == ["Active"]


def test_companies_filter_active_and_by_category(client, db_session: Session):
    db_session.add_all(
        [
            Company(slug="retail-a", name="Retail A", category="retail", initials="RA", is_active=True),
            Company(slug="dist-a", name="Dist A", category="distribution", initials="DA", is_active=True),
            Company(slug="hidden", name="Hidden", category="retail", initials="HD", is_active=False),
        ]
    )
    db_session.commit()

    all_response = client.get(f"{PUB}/companies").json()
    slugs = {c["slug"] for c in all_response}
    assert slugs == {"retail-a", "dist-a"}

    retail_only = client.get(f"{PUB}/companies?category=retail").json()
    assert [c["slug"] for c in retail_only] == ["retail-a"]


def test_company_detail_404_for_hidden(client, db_session: Session):
    db_session.add(
        Company(slug="hidden", name="Hidden", category="retail", initials="HD", is_active=False)
    )
    db_session.commit()

    assert client.get(f"{PUB}/companies/hidden").status_code == 404


def test_company_detail_returns_active(client, db_session: Session):
    db_session.add(
        Company(slug="ok", name="OK", category="retail", initials="OK", is_active=True)
    )
    db_session.commit()

    response = client.get(f"{PUB}/companies/ok")
    assert response.status_code == 200
    assert response.json()["slug"] == "ok"


def test_news_only_returns_published(client, db_session: Session):
    db_session.add_all(
        [
            NewsItem(
                slug="pub",
                title="Published",
                category="company",
                cover="from-x to-y",
                published_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
                is_published=True,
            ),
            NewsItem(
                slug="draft",
                title="Draft",
                category="company",
                cover="from-x to-y",
                published_at=datetime(2026, 5, 13, tzinfo=timezone.utc),
                is_published=False,
            ),
        ]
    )
    db_session.commit()

    slugs = [n["slug"] for n in client.get(f"{PUB}/news").json()]
    assert slugs == ["pub"]

    # Hidden detail returns 404
    assert client.get(f"{PUB}/news/draft").status_code == 404


def test_news_featured_filter(client, db_session: Session):
    db_session.add_all(
        [
            NewsItem(slug="a", title="A", category="company", cover="x",
                     published_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                     is_published=True, is_featured=True),
            NewsItem(slug="b", title="B", category="company", cover="x",
                     published_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
                     is_published=True, is_featured=False),
        ]
    )
    db_session.commit()

    featured = client.get(f"{PUB}/news?featured=true").json()
    assert [n["slug"] for n in featured] == ["a"]


def test_leadership_only_returns_active(client, db_session: Session):
    db_session.add_all(
        [
            LeadershipMessage(slug="chairman", name="A", role="Chairman", initials="AA", display_order=1, is_active=True),
            LeadershipMessage(slug="ex", name="B", role="EX", initials="BB", display_order=2, is_active=False),
        ]
    )
    db_session.commit()

    slugs = [l["slug"] for l in client.get(f"{PUB}/leadership").json()]
    assert slugs == ["chairman"]


def test_site_settings_returns_defaults_when_missing(client):
    response = client.get(f"{PUB}/site-settings")
    assert response.status_code == 200
    assert response.json()["site_name"] == "Paris United Group Holding"


# ---------------------------------------------------------------------------
# Contact submission
# ---------------------------------------------------------------------------


def test_contact_form_persists_and_audits(client, db_session: Session):
    payload = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+97400000000",
        "department": "Sales",
        "subject": "Quote request",
        "message": "Hello, please send a quote.",
    }
    response = client.post(f"{PUB}/contact", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Jane Doe"
    assert body["email"] == "jane@example.com"
    assert body["is_read"] is False

    actions = [
        row.action
        for row in db_session.execute(select(AuditLog)).scalars()
    ]
    assert "public.contact.submit" in actions


def test_contact_form_rejects_bad_email(client):
    payload = {
        "name": "Bad Email",
        "email": "not-an-email",
        "message": "Hi",
    }
    response = client.post(f"{PUB}/contact", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Newsletter subscription
# ---------------------------------------------------------------------------


def test_newsletter_subscribe_creates_active_row(client, db_session: Session):
    response = client.post(
        f"{PUB}/newsletter", json={"email": "subscriber@example.com"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "subscriber@example.com"
    assert body["is_active"] is True

    rows = list(db_session.execute(select(NewsletterSubscriber)).scalars())
    assert len(rows) == 1


def test_newsletter_subscribe_is_idempotent(client, db_session: Session):
    first = client.post(
        f"{PUB}/newsletter", json={"email": "same@example.com"}
    )
    assert first.status_code == 201

    second = client.post(
        f"{PUB}/newsletter", json={"email": "same@example.com"}
    )
    assert second.status_code == 201
    assert second.json()["email"] == "same@example.com"

    rows = list(db_session.execute(select(NewsletterSubscriber)).scalars())
    assert len(rows) == 1


def test_newsletter_reactivates_inactive_email(client, db_session: Session):
    db_session.add(
        NewsletterSubscriber(email="back@example.com", is_active=False)
    )
    db_session.commit()

    response = client.post(
        f"{PUB}/newsletter", json={"email": "back@example.com"}
    )
    assert response.status_code == 201
    assert response.json()["is_active"] is True
