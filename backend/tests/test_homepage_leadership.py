"""Tests for the unified Leadership Messages homepage section."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.cms import LeadershipMessage, SiteSetting


ENDPOINT = "/api/v1/public/homepage/leadership-messages"


def _leader(
    db_session: Session,
    *,
    slug: str,
    role: str,
    name: str,
    initials: str,
    is_homepage_featured: bool,
    display_order: int = 1,
    is_active: bool = True,
    **extra,
) -> LeadershipMessage:
    leader = LeadershipMessage(
        slug=slug,
        name=name,
        role=role,
        initials=initials,
        is_homepage_featured=is_homepage_featured,
        is_active=is_active,
        display_order=display_order,
        **extra,
    )
    db_session.add(leader)
    db_session.commit()
    return leader


def _site_settings(db_session: Session, **overrides) -> SiteSetting:
    existing = db_session.get(SiteSetting, 1)
    if existing is None:
        existing = SiteSetting(id=1, site_name="Test")
        db_session.add(existing)
    for k, v in overrides.items():
        setattr(existing, k, v)
    db_session.commit()
    return existing


def test_endpoint_returns_default_response_when_db_is_empty(client):
    response = client.get(ENDPOINT)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enabled"] is True
    assert body["animation_enabled"] is True
    assert body["title"]
    assert body["eyebrow"]
    assert body["messages"] == []


def test_endpoint_returns_chairman_and_md_in_order(client, db_session: Session):
    _site_settings(
        db_session,
        home_leadership_section_eyebrow="Voices",
        home_leadership_section_title="Hello",
        home_leadership_section_subtitle="World",
    )
    _leader(
        db_session,
        slug="chairman",
        role="Chairman",
        name="Ms Chair",
        initials="MC",
        is_homepage_featured=True,
        display_order=1,
        role_label="Chairman",
        highlight_quote="The quote.",
        message_paragraph_1="Para 1.",
        message_paragraph_2="Para 2.",
    )
    _leader(
        db_session,
        slug="md",
        role="Managing Director",
        name="Mr MD",
        initials="MD",
        is_homepage_featured=True,
        display_order=2,
        role_label="MD",
    )
    response = client.get(ENDPOINT)
    body = response.json()
    assert body["eyebrow"] == "Voices"
    assert body["title"] == "Hello"
    assert body["subtitle"] == "World"
    assert [m["slug"] for m in body["messages"]] == ["chairman", "md"]
    chair = body["messages"][0]
    assert chair["role_type"] == "chairman"
    assert chair["highlight_quote"] == "The quote."
    assert chair["message_paragraph_1"] == "Para 1."
    assert chair["message_paragraph_2"] == "Para 2."


def test_endpoint_disabled_section_still_returns_messages(
    client, db_session: Session
):
    """`enabled=false` is the admin signal to hide the section; the API
    still returns the messages so the frontend can decide what to do."""
    _site_settings(db_session, home_leadership_section_enabled=False)
    _leader(
        db_session,
        slug="chairman",
        role="Chairman",
        name="Ms Chair",
        initials="MC",
        is_homepage_featured=True,
    )
    body = client.get(ENDPOINT).json()
    assert body["enabled"] is False
    assert len(body["messages"]) == 1


def test_inactive_or_unfeatured_leaders_are_excluded(
    client, db_session: Session
):
    _leader(
        db_session,
        slug="chairman",
        role="Chairman",
        name="Active chair",
        initials="AC",
        is_homepage_featured=True,
        is_active=True,
    )
    _leader(
        db_session,
        slug="md",
        role="Managing Director",
        name="Hidden md",
        initials="HM",
        is_homepage_featured=True,
        is_active=False,  # inactive — should not appear
    )
    _leader(
        db_session,
        slug="ed-retail",
        role="Executive Director",
        name="Not featured",
        initials="NF",
        is_homepage_featured=False,
        is_active=True,
    )
    body = client.get(ENDPOINT).json()
    slugs = [m["slug"] for m in body["messages"]]
    assert slugs == ["chairman"]


def test_chairman_only_returns_single_card(client, db_session: Session):
    _leader(
        db_session,
        slug="chairman",
        role="Chairman",
        name="Solo chair",
        initials="SC",
        is_homepage_featured=True,
    )
    body = client.get(ENDPOINT).json()
    assert len(body["messages"]) == 1
    assert body["messages"][0]["role_type"] == "chairman"


def test_role_type_falls_back_when_slug_is_custom(
    client, db_session: Session
):
    _leader(
        db_session,
        slug="other-leader",
        role="Founder",
        name="Custom",
        initials="C",
        is_homepage_featured=True,
    )
    body = client.get(ENDPOINT).json()
    assert body["messages"][0]["role_type"] == "chairman"


def test_admin_can_toggle_homepage_featured_via_existing_endpoint(
    client, db_session: Session, seed_auth
):
    leader = _leader(
        db_session,
        slug="ed-retail",
        role="Executive Director",
        name="Custom person",
        initials="CP",
        is_homepage_featured=False,
    )

    # Log in as the website admin and flip is_homepage_featured.
    login = client.post(
        "/api/v1/admin/auth/login",
        json={
            "email": "webadmin@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.patch(
        f"/api/v1/admin/cms/leadership/{leader.id}",
        headers=headers,
        json={"is_homepage_featured": True, "role_label": "Custom role"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_homepage_featured"] is True
    assert body["role_label"] == "Custom role"

    homepage = client.get(ENDPOINT).json()
    assert any(m["slug"] == "ed-retail" for m in homepage["messages"])
