"""Public ``/offers`` — expired campaigns stay visible, badged.

Pre-fix behaviour silently dropped any campaign with ``end_date``
in the past, which meant a customer landing on ``/offers`` from a
slightly-stale share link saw an empty page. The new contract:

  * Inactive campaigns are still hidden.
  * Not-yet-started campaigns (``start_date > today``) are still
    hidden.
  * EXPIRED campaigns (``end_date < today``) come back with
    ``is_expired = true``, sorted below the active ones.
  * Highlighted carousels (featured / killer / flash) skip expired
    rows — surfacing an expired flash sale would mislead the
    customer.
  * ``GET /offers/{slug}`` returns 200 + ``is_expired = true`` for
    expired rows so old share links resolve instead of 404-ing.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.marketing import (
    CATALOGUE_READY,
    Catalogue,
    OfferCampaign,
)


PUBLIC = "/api/v1/offers"


def _make_campaign(
    db: Session,
    *,
    slug: str,
    title: str = "Campaign",
    end_date: date | None = None,
    start_date: date | None = None,
    is_active: bool = True,
    is_featured: bool = False,
    is_killer_offer: bool = False,
    is_flash_sale: bool = False,
    with_ready_catalogue: bool = True,
) -> OfferCampaign:
    """Stand up a campaign + an attached ready catalogue (so the
    landing's "must have ≥1 ready catalogue" filter passes)."""
    camp = OfferCampaign(
        slug=slug,
        title=title,
        end_date=end_date,
        start_date=start_date,
        is_active=is_active,
        is_featured=is_featured,
        is_killer_offer=is_killer_offer,
        is_flash_sale=is_flash_sale,
    )
    db.add(camp)
    db.flush()
    if with_ready_catalogue:
        db.add(
            Catalogue(
                campaign_id=camp.id,
                slug=f"{slug}-cat",
                title=f"{title} catalogue",
                processing_status=CATALOGUE_READY,
                is_active=True,
                page_count=1,
                cover_image_url="/api/v1/uploads/x.webp",
            )
        )
    db.commit()
    db.refresh(camp)
    return camp


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------


def test_expired_campaign_shows_up_with_is_expired_flag(
    client: TestClient, db_session: Session
):
    _make_campaign(
        db_session,
        slug="last-month-sale",
        title="Last month sale",
        end_date=date.today() - timedelta(days=1),
    )

    r = client.get(PUBLIC)
    assert r.status_code == 200
    body = r.json()
    slugs = [c["slug"] for c in body["all_campaigns"]]
    assert "last-month-sale" in slugs
    target = next(c for c in body["all_campaigns"] if c["slug"] == "last-month-sale")
    assert target["is_expired"] is True


def test_inactive_campaign_stays_hidden(
    client: TestClient, db_session: Session
):
    _make_campaign(
        db_session,
        slug="archived",
        end_date=date.today() + timedelta(days=30),
        is_active=False,
    )
    body = client.get(PUBLIC).json()
    assert "archived" not in [c["slug"] for c in body["all_campaigns"]]


def test_future_start_date_stays_hidden(
    client: TestClient, db_session: Session
):
    _make_campaign(
        db_session,
        slug="next-month",
        start_date=date.today() + timedelta(days=7),
    )
    body = client.get(PUBLIC).json()
    assert "next-month" not in [c["slug"] for c in body["all_campaigns"]]


# ---------------------------------------------------------------------------
# Sorting + carousels
# ---------------------------------------------------------------------------


def test_active_campaigns_sort_above_expired(
    client: TestClient, db_session: Session
):
    _make_campaign(db_session, slug="alpha-old", end_date=date.today() - timedelta(days=2))
    _make_campaign(db_session, slug="bravo-current")
    _make_campaign(db_session, slug="charlie-old", end_date=date.today() - timedelta(days=10))

    body = client.get(PUBLIC).json()
    order = [c["slug"] for c in body["all_campaigns"]]
    expired_flags = [c["is_expired"] for c in body["all_campaigns"]]
    # All active come before all expired regardless of insert order.
    assert expired_flags == sorted(expired_flags), (
        f"expected active-first, got: {list(zip(order, expired_flags))}"
    )


def test_expired_flash_sale_is_dropped_from_carousel(
    client: TestClient, db_session: Session
):
    """An expired campaign with ``is_flash_sale=True`` should NOT
    appear in the ``flash_sales`` carousel — promising a "live flash
    sale" that ended yesterday is the worst-case customer trust hit.
    It still shows in ``all_campaigns`` (with the expired badge)."""
    _make_campaign(
        db_session,
        slug="expired-flash",
        end_date=date.today() - timedelta(days=1),
        is_flash_sale=True,
        is_killer_offer=True,
        is_featured=True,
    )
    body = client.get(PUBLIC).json()
    assert body["flash_sales"] == []
    assert body["killer_offers"] == []
    assert body["featured"] == []
    # …but the campaign itself is still in the all-campaigns list.
    assert "expired-flash" in [c["slug"] for c in body["all_campaigns"]]


def test_active_flash_sale_appears_in_carousel(
    client: TestClient, db_session: Session
):
    _make_campaign(
        db_session,
        slug="live-flash",
        end_date=date.today() + timedelta(days=2),
        is_flash_sale=True,
    )
    body = client.get(PUBLIC).json()
    assert [c["slug"] for c in body["flash_sales"]] == ["live-flash"]
    assert body["flash_sales"][0]["is_expired"] is False


# ---------------------------------------------------------------------------
# Campaign detail
# ---------------------------------------------------------------------------


def test_detail_endpoint_serves_expired_campaign(
    client: TestClient, db_session: Session
):
    """Hitting an old share link should land on the campaign page
    (200) with ``is_expired`` true — not a 404."""
    _make_campaign(
        db_session,
        slug="black-friday-25",
        title="Black Friday 2025",
        end_date=date.today() - timedelta(days=180),
    )
    r = client.get(f"{PUBLIC}/black-friday-25")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "black-friday-25"
    assert body["is_expired"] is True


def test_detail_endpoint_active_campaign_not_expired(
    client: TestClient, db_session: Session
):
    _make_campaign(
        db_session,
        slug="winter-edit",
        end_date=date.today() + timedelta(days=14),
    )
    body = client.get(f"{PUBLIC}/winter-edit").json()
    assert body["is_expired"] is False
