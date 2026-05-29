"""Marketing dashboard + counter-reconcile endpoints.

The dashboard pulls every aggregate straight from
``catalogue_view_events`` so it's stable even if the denormalised
``Catalogue.view_count`` has drifted. Reconcile resets the denormalised
counter from the events so the table view + the dashboard agree.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.marketing import (
    CATALOGUE_READY,
    Catalogue,
    CatalogueViewEvent,
    OfferCampaign,
)


ADMIN_LOGIN = "/api/v1/admin/auth/login"
ADMIN_MARKETING = "/api/v1/admin/marketing"


def _login_super(client: TestClient, password: str) -> dict[str, str]:
    resp = client.post(
        ADMIN_LOGIN,
        json={"email": "superadmin@pug.example.com", "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed_campaign(
    db: Session, *, slug: str, title: str, branch: str | None = None
) -> OfferCampaign:
    c = OfferCampaign(
        slug=slug,
        title=title,
        branch=branch,
        is_active=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _seed_catalogue(
    db: Session,
    *,
    slug: str,
    title: str,
    campaign: OfferCampaign | None = None,
    page_count: int = 4,
    download_count: int = 0,
) -> Catalogue:
    cat = Catalogue(
        slug=slug,
        title=title,
        campaign_id=campaign.id if campaign else None,
        page_count=page_count,
        processing_status=CATALOGUE_READY,
        is_active=True,
        download_count=download_count,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def _seed_view(
    db: Session,
    catalogue: Catalogue,
    *,
    days_ago: int = 0,
    device: str | None = "desktop",
    session_hash: str | None = None,
    duration_seconds: int | None = None,
) -> CatalogueViewEvent:
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    ev = CatalogueViewEvent(
        catalogue_id=catalogue.id,
        session_hash=session_hash or f"sess-{catalogue.id}-{days_ago}-{device}",
        device=device,
        duration_seconds=duration_seconds,
        viewed_at=when,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_dashboard_requires_marketing_permission(client, seed_auth):
    """Plain Website Admin doesn't have marketing:catalogues:manage,
    so the dashboard must reject — the inbox role shouldn't see
    marketing analytics."""
    # webadmin user has the Website Admin role only (no marketing perm).
    resp = client.post(
        ADMIN_LOGIN,
        json={
            "email": "webadmin@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    r = client.get(f"{ADMIN_MARKETING}/dashboard", headers=headers)
    assert r.status_code == 403


def test_dashboard_returns_zeroed_payload_for_empty_db(
    client, seed_auth
):
    headers = _login_super(client, seed_auth["password"])
    r = client.get(f"{ADMIN_MARKETING}/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["period_days"] == 30
    assert body["period_label"] == "Last 30 days"
    assert body["kpis"]["campaigns_total"] == 0
    assert body["kpis"]["catalogues_total"] == 0
    assert body["kpis"]["total_views_period"] == 0
    assert body["kpis"]["total_views_all_time"] == 0
    assert body["top_catalogues"] == []
    assert body["top_campaigns"] == []
    assert body["recent_views"] == []
    # Series is zero-filled with one entry per day in the window.
    assert len(body["views_over_time"]) == 31
    assert all(p["views"] == 0 for p in body["views_over_time"])


def test_dashboard_aggregates_kpis_and_top_lists(
    client, seed_auth, db_session: Session
):
    campaign_a = _seed_campaign(
        db_session, slug="summer", title="Summer", branch="Doha"
    )
    campaign_b = _seed_campaign(
        db_session, slug="winter", title="Winter", branch="Lusail"
    )
    cat_a = _seed_catalogue(
        db_session, slug="flyer-a", title="Flyer A",
        campaign=campaign_a, download_count=3,
    )
    cat_b = _seed_catalogue(
        db_session, slug="flyer-b", title="Flyer B",
        campaign=campaign_b, download_count=1,
    )
    standalone = _seed_catalogue(
        db_session, slug="standalone", title="Standalone",
    )

    # Three views in-window (today) for cat_a; one for cat_b; none for standalone.
    _seed_view(db_session, cat_a, days_ago=0, device="mobile",
               session_hash="sess-a", duration_seconds=60)
    _seed_view(db_session, cat_a, days_ago=0, device="mobile",
               session_hash="sess-a", duration_seconds=120)
    _seed_view(db_session, cat_a, days_ago=1, device="desktop",
               session_hash="sess-b", duration_seconds=30)
    _seed_view(db_session, cat_b, days_ago=2, device="tablet",
               session_hash="sess-c")
    # One out-of-window view (45 days ago) — counts toward all-time
    # but not toward period totals.
    _seed_view(
        db_session, cat_a, days_ago=45, device="desktop",
        session_hash="sess-old",
    )

    headers = _login_super(client, seed_auth["password"])
    r = client.get(
        f"{ADMIN_MARKETING}/dashboard?period=30d", headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()

    kpis = body["kpis"]
    assert kpis["campaigns_total"] == 2
    assert kpis["campaigns_active"] == 2
    assert kpis["catalogues_total"] == 3
    assert kpis["catalogues_ready"] == 3
    assert kpis["total_views_period"] == 4
    assert kpis["total_views_all_time"] == 5
    assert kpis["unique_sessions_period"] == 3
    assert kpis["total_downloads_all_time"] == 4
    assert kpis["total_pages"] == 12  # 3 catalogues × 4 pages

    # Top catalogues: A first (3 views), B second (1), Standalone last (0).
    top_titles = [t["title"] for t in body["top_catalogues"]]
    assert top_titles[0] == "Flyer A"
    assert top_titles[1] == "Flyer B"
    assert body["top_catalogues"][0]["views"] == 3
    assert body["top_catalogues"][0]["downloads"] == 3
    # Campaign title is denormalised onto the row.
    assert body["top_catalogues"][0]["campaign_title"] == "Summer"

    # Top campaigns by views.
    top_campaign_views = {c["title"]: c["views"] for c in body["top_campaigns"]}
    assert top_campaign_views["Summer"] == 3
    assert top_campaign_views["Winter"] == 1

    # Device mix excludes the 45-day-old event.
    assert body["by_device"] == {
        "mobile": 2,
        "desktop": 1,
        "tablet": 1,
    }

    # Recent activity is newest-first; cat_a's most-recent view leads.
    assert body["recent_views"][0]["catalogue_title"] == "Flyer A"


def test_dashboard_period_all_widens_window(
    client, seed_auth, db_session: Session
):
    cat = _seed_catalogue(db_session, slug="old", title="Old flyer")
    # Old enough that 30d window excludes it; 'all' must include.
    _seed_view(db_session, cat, days_ago=120, session_hash="sess-old")
    headers = _login_super(client, seed_auth["password"])

    r30 = client.get(
        f"{ADMIN_MARKETING}/dashboard?period=30d", headers=headers
    )
    assert r30.json()["kpis"]["total_views_period"] == 0

    rall = client.get(
        f"{ADMIN_MARKETING}/dashboard?period=all", headers=headers
    )
    assert rall.json()["kpis"]["total_views_period"] == 1


def test_dashboard_invalid_period_falls_back_to_30d(
    client, seed_auth
):
    headers = _login_super(client, seed_auth["password"])
    r = client.get(
        f"{ADMIN_MARKETING}/dashboard?period=garbage", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["period_days"] == 30


# ---------------------------------------------------------------------------
# Reconcile
# ---------------------------------------------------------------------------


def test_reconcile_resyncs_drifted_view_counts(
    client, seed_auth, db_session: Session
):
    cat = _seed_catalogue(db_session, slug="flyer", title="Flyer")
    _seed_view(db_session, cat, session_hash="s1")
    _seed_view(db_session, cat, session_hash="s2")
    _seed_view(db_session, cat, session_hash="s3")
    # Manually corrupt the denormalised counter to a value far from
    # COUNT(events) — this is what we're meant to fix.
    cat.view_count = 99
    db_session.commit()

    headers = _login_super(client, seed_auth["password"])
    r = client.post(
        f"{ADMIN_MARKETING}/catalogues/reconcile-counters",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["catalogues_inspected"] == 1
    assert body["catalogues_updated"] == 1
    assert body["total_view_count_before"] == 99
    assert body["total_view_count_after"] == 3

    db_session.refresh(cat)
    assert cat.view_count == 3


def test_reconcile_idempotent_when_already_in_sync(
    client, seed_auth, db_session: Session
):
    cat = _seed_catalogue(db_session, slug="flyer", title="Flyer")
    _seed_view(db_session, cat, session_hash="s1")
    cat.view_count = 1
    db_session.commit()

    headers = _login_super(client, seed_auth["password"])
    r = client.post(
        f"{ADMIN_MARKETING}/catalogues/reconcile-counters",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["catalogues_updated"] == 0
    assert body["total_view_count_before"] == body["total_view_count_after"]
