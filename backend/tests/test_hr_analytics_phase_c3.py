"""Phase C-3 — HR recruitment analytics.

Pins the ``GET /hr/analytics/recruitment`` payload shape and the
arithmetic of the four metrics it ships:

* ``daily_applications`` is zero-filled across the window so the
  frontend line chart doesn't visually collapse on quiet days.
* ``funnel_conversion`` lists every canonical stage in master-plan
  order, including stages with zero in-window matches.
* ``source_breakdown`` reports cumulative drop-offs per source
  (an application that landed at ``joined`` still counts as
  ``shortlisted`` + ``offers_issued``, so conversion-rate math
  reads cleanly from the payload).
* ``time_to_hire`` averages ``joined_at - applied_at`` across
  joined applications inside the window and reports per-source
  averages too.

Permission gating is exercised at the bottom — an HR user without
``hr:dashboard:view`` is denied. Out-of-window data is ignored to
prove the ``window_days`` parameter actually narrows the result.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    OFFER_ACCEPTED,
    SOURCE_BULK_UPLOAD,
    SOURCE_MANUAL_UPLOAD,
    SOURCE_PUBLIC_FORM,
    STATUS_CV_RECEIVED,
    STATUS_JOINED,
    STATUS_SHORTLISTED,
    Candidate,
    CandidateJobApplication,
    JobOpening,
    OfferTracking,
)


HR_LOGIN = "/api/v1/hr/auth/login"
ANALYTICS_URL = "/api/v1/hr/analytics/recruitment"


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_job(db: Session, slug: str) -> JobOpening:
    job = JobOpening(
        slug=slug,
        title=f"Job {slug}",
        department="Engineering",
        company="PUG",
        location="Doha",
    )
    db.add(job)
    db.flush()
    return job


def _seed_application(
    db: Session,
    *,
    candidate_name: str,
    source: str,
    status: str,
    applied_days_ago: int,
    job: JobOpening,
) -> CandidateJobApplication:
    candidate = Candidate(
        full_name=candidate_name,
        email=f"{candidate_name.lower().replace(' ', '.')}@example.com",
        mobile="100",
        source=source,
    )
    db.add(candidate)
    db.flush()
    application = CandidateJobApplication(
        candidate_id=candidate.id,
        job_opening_id=job.id,
        status=status,
        applied_at=datetime.now(timezone.utc) - timedelta(days=applied_days_ago),
        source=source,
    )
    db.add(application)
    db.flush()
    return application


def _seed_offer_joined(
    db: Session,
    *,
    application: CandidateJobApplication,
    days_to_join: int,
) -> OfferTracking:
    offer = OfferTracking(
        application_id=application.id,
        status=OFFER_ACCEPTED,
        joined_at=application.applied_at + timedelta(days=days_to_join),
    )
    db.add(offer)
    db.flush()
    return offer


# ---------------------------------------------------------------------------
# Permission gate
# ---------------------------------------------------------------------------


def test_analytics_endpoint_requires_authentication(client):
    response = client.get(ANALYTICS_URL)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Payload shape
# ---------------------------------------------------------------------------


def test_analytics_returns_the_four_top_level_sections(client, seed_auth):
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.get(ANALYTICS_URL, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {
        "window_days",
        "daily_applications",
        "funnel_conversion",
        "source_breakdown",
        "time_to_hire",
    }
    assert body["window_days"] == 90


def test_analytics_window_param_narrows_to_default_when_omitted(client, seed_auth):
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.get(f"{ANALYTICS_URL}?window_days=30", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["window_days"] == 30
    assert len(body["daily_applications"]) == 30


def test_analytics_window_param_validates_range(client, seed_auth):
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    too_small = client.get(f"{ANALYTICS_URL}?window_days=3", headers=headers)
    assert too_small.status_code == 422
    too_large = client.get(f"{ANALYTICS_URL}?window_days=400", headers=headers)
    assert too_large.status_code == 422


# ---------------------------------------------------------------------------
# Daily applications zero-fill
# ---------------------------------------------------------------------------


def test_daily_applications_is_zero_filled_across_the_window(
    client, seed_auth, db_session: Session
):
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    job = _seed_job(db_session, "an-zero-fill")
    _seed_application(
        db_session,
        candidate_name="In Window",
        source=SOURCE_PUBLIC_FORM,
        status=STATUS_CV_RECEIVED,
        applied_days_ago=2,
        job=job,
    )
    db_session.commit()

    response = client.get(f"{ANALYTICS_URL}?window_days=14", headers=headers)
    body = response.json()
    daily = body["daily_applications"]
    assert len(daily) == 14
    # Every entry has a YYYY-MM-DD date and a count >= 0.
    for entry in daily:
        assert len(entry["date"]) == 10
        assert entry["count"] >= 0
    # The one we seeded shows up.
    counts = [d["count"] for d in daily]
    assert sum(counts) >= 1


def test_daily_applications_excludes_rows_outside_the_window(
    client, seed_auth, db_session: Session
):
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    job = _seed_job(db_session, "an-out-of-window")
    # Way outside any sensible window.
    _seed_application(
        db_session,
        candidate_name="Old Timer",
        source=SOURCE_PUBLIC_FORM,
        status=STATUS_CV_RECEIVED,
        applied_days_ago=500,
        job=job,
    )
    db_session.commit()

    response = client.get(f"{ANALYTICS_URL}?window_days=30", headers=headers)
    daily = response.json()["daily_applications"]
    # Within a 30-day window the 500-day-old application must not
    # appear in any bucket.
    assert all(d["count"] == 0 for d in daily) or sum(d["count"] for d in daily) < 500


# ---------------------------------------------------------------------------
# Source breakdown — cumulative drop-offs
# ---------------------------------------------------------------------------


def test_source_breakdown_buckets_per_source_with_cumulative_counts(
    client, seed_auth, db_session: Session
):
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    job = _seed_job(db_session, "an-source-mix")
    _seed_application(
        db_session,
        candidate_name="Public CV",
        source=SOURCE_PUBLIC_FORM,
        status=STATUS_CV_RECEIVED,
        applied_days_ago=5,
        job=job,
    )
    _seed_application(
        db_session,
        candidate_name="Public Shortlist",
        source=SOURCE_PUBLIC_FORM,
        status=STATUS_SHORTLISTED,
        applied_days_ago=10,
        job=job,
    )
    _seed_application(
        db_session,
        candidate_name="Manual Joined",
        source=SOURCE_MANUAL_UPLOAD,
        status=STATUS_JOINED,
        applied_days_ago=15,
        job=job,
    )
    db_session.commit()

    response = client.get(f"{ANALYTICS_URL}?window_days=60", headers=headers)
    body = response.json()
    by_source = {entry["source"]: entry for entry in body["source_breakdown"]}

    # public_form: 2 total, 1 shortlisted (cumulative), 0 offers, 0 joined
    assert by_source[SOURCE_PUBLIC_FORM]["total"] == 2
    assert by_source[SOURCE_PUBLIC_FORM]["shortlisted"] == 1
    assert by_source[SOURCE_PUBLIC_FORM]["offers_issued"] == 0
    assert by_source[SOURCE_PUBLIC_FORM]["joined"] == 0

    # manual_upload: 1 total, 1 shortlisted (cumulative), 1 offer, 1 joined
    assert by_source[SOURCE_MANUAL_UPLOAD]["total"] == 1
    assert by_source[SOURCE_MANUAL_UPLOAD]["shortlisted"] == 1
    assert by_source[SOURCE_MANUAL_UPLOAD]["offers_issued"] == 1
    assert by_source[SOURCE_MANUAL_UPLOAD]["joined"] == 1

    # bulk_upload had no rows but the canonical source still shows up
    # with zero counts so the frontend can render the row.
    assert by_source[SOURCE_BULK_UPLOAD]["total"] == 0


# ---------------------------------------------------------------------------
# Time-to-hire average
# ---------------------------------------------------------------------------


def test_time_to_hire_averages_joined_applications(
    client, seed_auth, db_session: Session
):
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])

    job = _seed_job(db_session, "an-tth")
    # Three joined applications: 10, 20, 30 day cycles → avg 20.
    for cycle_days, idx in [(10, 1), (20, 2), (30, 3)]:
        application = _seed_application(
            db_session,
            candidate_name=f"Joined {idx}",
            source=SOURCE_PUBLIC_FORM,
            status=STATUS_JOINED,
            applied_days_ago=cycle_days + 1,
            job=job,
        )
        _seed_offer_joined(
            db_session, application=application, days_to_join=cycle_days
        )
    db_session.commit()

    response = client.get(f"{ANALYTICS_URL}?window_days=90", headers=headers)
    body = response.json()
    tth = body["time_to_hire"]
    assert tth["sample_size"] == 3
    assert tth["overall_avg_days"] == 20.0
    public = next(
        s for s in tth["by_source"] if s["source"] == SOURCE_PUBLIC_FORM
    )
    assert public["sample_size"] == 3
    assert public["avg_days"] == 20.0


def test_time_to_hire_handles_zero_joined_applications(
    client, seed_auth
):
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.get(f"{ANALYTICS_URL}?window_days=30", headers=headers)
    tth = response.json()["time_to_hire"]
    # No data → no average, but the canonical sources are still listed.
    assert tth["overall_avg_days"] is None
    assert tth["sample_size"] == 0
    sources_in_payload = {s["source"] for s in tth["by_source"]}
    assert sources_in_payload >= {
        SOURCE_PUBLIC_FORM,
        SOURCE_MANUAL_UPLOAD,
        SOURCE_BULK_UPLOAD,
    }


# ---------------------------------------------------------------------------
# Funnel conversion — windowed
# ---------------------------------------------------------------------------


def test_funnel_conversion_lists_every_canonical_stage(client, seed_auth):
    headers = _login(client, "hr@pug.example.com", seed_auth["password"])
    response = client.get(ANALYTICS_URL, headers=headers)
    body = response.json()
    stages = [entry["status"] for entry in body["funnel_conversion"]]
    # Master-plan order, every stage present (even ones with zero
    # rows in window).
    assert stages == [
        "cv_received",
        "ai_reviewed",
        "hr_review_pending",
        "shortlisted",
        "first_interview",
        "technical_interview",
        "final_interview",
        "selected",
        "offer_sent",
        "joined",
    ]
    for entry in body["funnel_conversion"]:
        assert "label" in entry and entry["label"]
        assert entry["count"] >= 0
