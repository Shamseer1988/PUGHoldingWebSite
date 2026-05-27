"""Offer letter PDF generator (Feature F3)."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.models.hr_ats import (
    Candidate,
    CandidateJobApplication,
    JobOpening,
    OfferTracking,
)
from app.services.offer_pdf import build_offer_letter_pdf, offer_pdf_filename


HR_LOGIN = "/api/v1/hr/auth/login"


def _login(client: TestClient, email: str, password: str) -> dict:
    r = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_offer(db_session, *, with_job: bool = True) -> OfferTracking:
    """Insert a candidate -> application -> offer chain that the PDF
    renderer can chew on."""
    cand = Candidate(
        full_name="Jane Test Candidate",
        email="jane@example.com",
        mobile="+97412345678",
        current_location="Doha, Qatar",
    )
    db_session.add(cand)
    db_session.flush()

    job_id = None
    if with_job:
        job = JobOpening(
            slug="senior-backend-test",
            title="Senior Backend Engineer",
            department="Engineering",
            company="Paris United Group Holding",
            location="Doha, Qatar",
            status="open",
            approval_status="approved",
            publish_status="published",
        )
        db_session.add(job)
        db_session.flush()
        job_id = job.id

    app = CandidateJobApplication(
        candidate_id=cand.id,
        job_opening_id=job_id,
        status="selected",
    )
    db_session.add(app)
    db_session.flush()

    offer = OfferTracking(
        application_id=app.id,
        position="Senior Backend Engineer",
        salary_offered=18000,
        allowances="Housing + transport allowances per policy",
        joining_date=date(2026, 7, 1),
        probation_period="6 months",
        reporting_manager="Director of Engineering",
        work_location="Doha, Qatar",
        benefits_summary="25 days leave, full medical, annual airfare",
        offer_letter_number="PUG-OFR-2026-0042",
        remarks="Subject to medical clearance.",
        status="approved",
        approval_status="approved",
        created_by_id=None,
    )
    db_session.add(offer)
    db_session.commit()
    db_session.refresh(offer)
    return offer


# ---------------------------------------------------------------------------
# Pure renderer tests
# ---------------------------------------------------------------------------


class TestBuildOfferLetterPdf:
    def test_returns_pdf_bytes(self, db_session):
        offer = _make_offer(db_session)
        pdf = build_offer_letter_pdf(
            offer, offer.application.candidate, offer.application.job_opening
        )
        # Starts with the PDF magic header.
        assert pdf[:4] == b"%PDF"
        # Big enough to plausibly contain a letter.
        assert len(pdf) > 1000

    def test_renders_without_job_attached(self, db_session):
        """If a candidate applied via the manual-upload path with no
        job_opening_id, the PDF should still render, just dropping
        the job-derived lines."""
        offer = _make_offer(db_session, with_job=False)
        pdf = build_offer_letter_pdf(
            offer, offer.application.candidate, None
        )
        assert pdf[:4] == b"%PDF"

    def test_renders_with_minimal_offer_fields(self, db_session):
        """Many offer fields are nullable — confirm none of the empty
        ones crash the renderer."""
        cand = Candidate(full_name="Minimal Candidate")
        db_session.add(cand)
        db_session.flush()
        app = CandidateJobApplication(
            candidate_id=cand.id,
            status="cv_received",
        )
        db_session.add(app)
        db_session.flush()
        offer = OfferTracking(
            application_id=app.id,
            status="draft",
            approval_status="draft",
        )
        db_session.add(offer)
        db_session.commit()
        db_session.refresh(offer)
        pdf = build_offer_letter_pdf(offer, cand, None)
        assert pdf[:4] == b"%PDF"


class TestOfferPdfFilename:
    def test_predictable_safe_name(self, db_session):
        offer = _make_offer(db_session)
        name = offer_pdf_filename(offer, offer.application.candidate)
        assert name.endswith(".pdf")
        assert "Jane_Test_Candidate" in name
        assert "PUG-OFR-2026-0042" in name


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestPdfEndpoint:
    def test_download_returns_pdf(self, client: TestClient, seed_auth, db_session):
        offer = _make_offer(db_session)
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        resp = client.get(
            f"/api/v1/hr/offers/{offer.id}/pdf", headers=headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("application/pdf")
        assert "attachment" in resp.headers["content-disposition"]
        assert "Jane_Test_Candidate" in resp.headers["content-disposition"]
        assert resp.content[:4] == b"%PDF"

    def test_download_404_for_unknown_offer(self, client: TestClient, seed_auth):
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        resp = client.get(
            "/api/v1/hr/offers/9999999/pdf", headers=headers
        )
        assert resp.status_code == 404

    def test_download_requires_offers_view(
        self, client: TestClient, seed_auth, db_session
    ):
        offer = _make_offer(db_session)
        # Interviewer doesn't hold hr:offers:view.
        headers = _login(
            client, "interviewer@pug.example.com", seed_auth["password"]
        )
        resp = client.get(
            f"/api/v1/hr/offers/{offer.id}/pdf", headers=headers
        )
        assert resp.status_code == 403
