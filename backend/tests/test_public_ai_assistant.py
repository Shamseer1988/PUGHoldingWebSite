"""Tests for the Phase 17 public Ask-PUG-AI assistant."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cms import Company, LeadershipMessage, NewsItem, SiteSetting
from app.models.hr_ats import (
    AI_MODE_DISABLED,
    AI_MODE_LIVE,
    AI_MODE_MOCK,
    JOB_STATUS_OPEN,
    AISetting,
    JobOpening,
    PublicAIQuery,
)
from app.models.marketing import OfferCampaign


ASK = "/api/v1/public/ai-assistant/ask"
ADMIN_LOGIN = "/api/v1/admin/auth/login"
AI_SETTINGS = "/api/v1/admin/ai/settings"
PUBLIC_LOGS = "/api/v1/admin/ai/public-logs"


def _set_mode(
    db: Session, *, mode: str = AI_MODE_MOCK, public_enabled: bool = True
) -> AISetting:
    setting = db.get(AISetting, 1)
    if setting is None:
        setting = AISetting(id=1)
        db.add(setting)
    setting.mode = mode
    setting.public_enabled = public_enabled
    db.commit()
    return setting


def _seed_public_content(db: Session) -> None:
    db.add(
        SiteSetting(
            id=1,
            site_name="Paris United Group Holding",
            tagline="Trusted across the GCC.",
            contact_phone="+974 0000 0000",
            contact_email="info@example.com",
            whatsapp_number="+97400000000",
            contact_address="Doha, Qatar",
        )
    )
    db.add_all(
        [
            Company(
                slug="paris-hyper",
                name="Paris Hyper Market",
                category="retail",
                short_description="Hypermarkets across Qatar and KSA.",
                branches="5 branches",
                accent="from-pug-gold-500 to-pug-gold-700",
                initials="PH",
                is_active=True,
            ),
            Company(
                slug="paris-food",
                name="Paris Food International",
                category="distribution",
                short_description="FMCG wholesale and HORECA supply.",
                accent="from-pug-green-500 to-pug-gold-500",
                initials="PF",
                is_active=True,
            ),
        ]
    )
    db.add(
        LeadershipMessage(
            slug="chairman",
            name="Mr. A. Al Hassan",
            role="Chairman",
            short_message="Service first.",
            accent="x",
            initials="AH",
            is_active=True,
        )
    )
    db.add(
        NewsItem(
            slug="news-1",
            title="A new hypermarket opens in Lusail",
            summary="Doors open this week.",
            category="company",
            cover="x",
            published_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
            is_published=True,
        )
    )
    db.add(
        JobOpening(
            slug="store-manager",
            title="Store Manager",
            department="Retail",
            company="Paris Hyper Market",
            location="Doha, Qatar",
            status=JOB_STATUS_OPEN,
        )
    )
    db.commit()


# ---------------------------------------------------------------------------
# Disabled / fallback behaviour
# ---------------------------------------------------------------------------


def test_disabled_mode_returns_safe_fallback(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_DISABLED)
    response = client.post(
        ASK, json={"question": "What companies are in the group?"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["was_fallback"] is True
    assert body["mode"] == AI_MODE_DISABLED
    # Falls back to advertising the contact details from site settings.
    assert "+974 0000 0000" in body["answer"]


def test_public_disabled_with_hr_mode_live_still_falls_back(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK, public_enabled=False)
    response = client.post(ASK, json={"question": "Hello"})
    body = response.json()
    assert body["was_fallback"] is True
    assert body["mode"] == AI_MODE_DISABLED


# ---------------------------------------------------------------------------
# Mock answers — keyword routing on real public context
# ---------------------------------------------------------------------------


def test_mock_greets(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    body = client.post(ASK, json={"question": "Hi there"}).json()
    assert body["mode"] == AI_MODE_MOCK
    assert "Paris United Group Holding" in body["answer"]


def test_mock_contact_question(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    body = client.post(
        ASK, json={"question": "How can I contact your office?"}
    ).json()
    assert "+974 0000 0000" in body["answer"]
    assert "info@example.com" in body["answer"]


def test_mock_jobs_question(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    body = client.post(
        ASK, json={"question": "Do you have any open jobs?"}
    ).json()
    assert "Store Manager" in body["answer"]
    assert body["was_fallback"] is False


def test_mock_companies_question(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    body = client.post(
        ASK, json={"question": "What companies do you operate?"}
    ).json()
    assert "Paris Hyper Market" in body["answer"]
    assert "Paris Food International" in body["answer"]


def test_mock_news_question(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    body = client.post(
        ASK, json={"question": "What's the latest news?"}
    ).json()
    assert "A new hypermarket opens in Lusail" in body["answer"]


def test_mock_leadership_question(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    body = client.post(
        ASK, json={"question": "Who's the chairman?"}
    ).json()
    assert "Mr. A. Al Hassan" in body["answer"]


# ---------------------------------------------------------------------------
# Offers awareness — the assistant answers marketing/offers questions
# ---------------------------------------------------------------------------


def _seed_offer(
    db: Session,
    *,
    slug: str = "eid-mega",
    title: str = "Eid Mega Sale",
    branch: str = "Lusail",
    is_active: bool = True,
    is_killer_offer: bool = True,
    is_featured: bool = False,
    is_flash_sale: bool = False,
    start_date=None,
    end_date=None,
) -> OfferCampaign:
    camp = OfferCampaign(
        slug=slug,
        title=title,
        branch=branch,
        description="Up to 50% off across groceries.",
        is_active=is_active,
        is_killer_offer=is_killer_offer,
        is_featured=is_featured,
        is_flash_sale=is_flash_sale,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(camp)
    db.commit()
    return camp


def test_mock_killer_offers_question(client, db_session):
    _seed_public_content(db_session)
    _seed_offer(
        db_session, title="Eid Mega Sale", branch="Lusail", is_killer_offer=True
    )
    _set_mode(db_session, mode=AI_MODE_MOCK)
    body = client.post(
        ASK, json={"question": "Any killer offers running?"}
    ).json()
    assert body["mode"] == AI_MODE_MOCK
    assert body["was_fallback"] is False
    assert "Eid Mega Sale" in body["answer"]
    assert "Killer offer" in body["answer"]
    assert "Lusail" in body["answer"]


def test_mock_offers_question_when_none(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    body = client.post(
        ASK, json={"question": "Any offers or deals on right now?"}
    ).json()
    assert "no offers running" in body["answer"].lower()


def test_public_context_includes_only_running_offers(db_session):
    """``load_public_context`` exposes active, started, non-expired
    campaigns only — drafts (inactive), expired, and not-yet-started
    promos stay out so the assistant never advertises a dead offer."""
    from app.ai.public_assistant import load_public_context

    today = date.today()
    _seed_offer(db_session, slug="running", title="Running Now", is_active=True)
    _seed_offer(db_session, slug="hidden", title="Hidden Promo", is_active=False)
    _seed_offer(
        db_session,
        slug="expired",
        title="Old Promo",
        is_active=True,
        end_date=today - timedelta(days=1),
    )
    _seed_offer(
        db_session,
        slug="future",
        title="Future Promo",
        is_active=True,
        start_date=today + timedelta(days=5),
    )

    ctx = load_public_context(db_session)
    titles = [o["title"] for o in ctx.offers]
    assert "Running Now" in titles
    assert "Hidden Promo" not in titles
    assert "Old Promo" not in titles
    assert "Future Promo" not in titles
    # The running offer carries the marketing flags + a public URL.
    running = next(o for o in ctx.offers if o["title"] == "Running Now")
    assert running["url"] == "/offers/running"
    assert running["is_killer_offer"] is True


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def test_every_question_is_logged(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    client.post(
        ASK,
        json={"question": "What companies?", "session_id": "abc-123"},
    )
    rows = db_session.query(PublicAIQuery).all()
    assert len(rows) == 1
    assert rows[0].session_id == "abc-123"
    assert rows[0].question == "What companies?"
    assert rows[0].mode == AI_MODE_MOCK
    assert rows[0].was_fallback is False


def test_disabled_log_marks_fallback(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_DISABLED)
    client.post(ASK, json={"question": "Hi"})
    row = db_session.query(PublicAIQuery).first()
    assert row is not None
    assert row.was_fallback is True
    assert row.mode == AI_MODE_DISABLED


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_empty_question_rejected(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    response = client.post(ASK, json={"question": ""})
    # Pydantic rejects empty (min_length=1) → 422.
    assert response.status_code == 422


def test_question_length_capped(client, db_session):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    response = client.post(ASK, json={"question": "x" * 5000})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Safety — public context excludes HR data
# ---------------------------------------------------------------------------


def test_mock_never_mentions_internal_data(client, db_session):
    """If the question wanders into HR territory, the mock should
    stay scoped to the public context (it has no candidate data
    loaded in the first place)."""
    _seed_public_content(db_session)
    # Add some candidate-shaped HR data so we can prove it doesn't leak.
    from app.models.hr_ats import Candidate

    db_session.add(
        Candidate(
            full_name="Secret Person", email="secret@example.com",
            source="manual_upload",
        )
    )
    db_session.commit()
    _set_mode(db_session, mode=AI_MODE_MOCK)

    body = client.post(
        ASK, json={"question": "Tell me about Secret Person"}
    ).json()
    # The mock should NOT mention the candidate's name — it only
    # routes via context-aware keywords.
    assert "Secret Person" not in body["answer"]
    assert "secret@example.com" not in body["answer"]


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


def _admin_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        ADMIN_LOGIN,
        json={
            "email": "superadmin@pug.example.com",
            "password": password,
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_can_read_public_ai_fields(client, db_session, seed_auth):
    _set_mode(db_session, mode=AI_MODE_MOCK, public_enabled=True)
    headers = _admin_auth(client, seed_auth["password"])
    body = client.get(AI_SETTINGS, headers=headers).json()
    assert body["public_enabled"] is True
    assert body["public_extra_system_prompt"] is None


def test_admin_can_disable_public_ai(client, db_session, seed_auth):
    _set_mode(db_session, mode=AI_MODE_MOCK, public_enabled=True)
    headers = _admin_auth(client, seed_auth["password"])
    response = client.patch(
        AI_SETTINGS,
        headers=headers,
        json={
            "public_enabled": False,
            "public_extra_system_prompt": "Mention our 2026 promotions.",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["public_enabled"] is False
    assert "2026 promotions" in body["public_extra_system_prompt"]


def test_admin_can_set_openai_compatible_provider(client, db_session, seed_auth):
    _set_mode(db_session, mode=AI_MODE_MOCK)
    headers = _admin_auth(client, seed_auth["password"])
    response = client.patch(
        AI_SETTINGS,
        headers=headers,
        json={
            "provider": "openai_compatible",
            "base_url": "http://localhost:8001/v1",
            "model_name": "llama3.1",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "openai_compatible"
    assert body["base_url"] == "http://localhost:8001/v1"
    assert body["effective_provider"] == "openai_compatible"
    # openai_compatible servers often run keyless → info, not a hard fail.
    assert body["requires_api_key"] is False


def test_admin_rejects_unknown_provider(client, db_session, seed_auth):
    _set_mode(db_session, mode=AI_MODE_MOCK)
    headers = _admin_auth(client, seed_auth["password"])
    response = client.patch(
        AI_SETTINGS, headers=headers, json={"provider": "anthropic"}
    )
    assert response.status_code == 422


def test_admin_public_logs_returns_recent(client, db_session, seed_auth):
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    # 3 anonymous questions
    for q in ("hello", "what jobs?", "any companies?"):
        client.post(ASK, json={"question": q})

    headers = _admin_auth(client, seed_auth["password"])
    body = client.get(PUBLIC_LOGS, headers=headers).json()
    assert len(body) == 3
    # Newest first
    questions = [row["question"] for row in body]
    assert questions == ["any companies?", "what jobs?", "hello"]


def test_public_logs_require_system_scope(client, db_session, seed_auth):
    """HR-scope users should not be able to read public AI logs."""
    _seed_public_content(db_session)
    _set_mode(db_session, mode=AI_MODE_MOCK)
    client.post(ASK, json={"question": "hi"})

    hr_login = client.post(
        "/api/v1/hr/auth/login",
        json={"email": "hr@pug.example.com", "password": seed_auth["password"]},
    )
    hr_headers = {
        "Authorization": f"Bearer {hr_login.json()['access_token']}"
    }
    response = client.get(PUBLIC_LOGS, headers=hr_headers)
    assert response.status_code in (401, 403)
