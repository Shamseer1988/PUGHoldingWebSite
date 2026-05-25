"""Tests for the Phase 12 candidate-scoring engine + endpoints."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    Candidate,
    CandidateExtractedData,
    JobOpening,
)
from app.services.candidate_scoring import (
    MAX_POINTS,
    TOTAL_MAX,
    compute_score,
)


HR_LOGIN = "/api/v1/hr/auth/login"
HR_UPLOAD = "/api/v1/hr/candidates/upload"


# ---------------------------------------------------------------------------
# Unit tests (engine)
# ---------------------------------------------------------------------------


def _strong_candidate() -> Candidate:
    return Candidate(
        full_name="Ahmed Hassan",
        email="ahmed@pug.example.com",
        mobile="+97455001122",
        nationality="Qatari",
        current_location="Doha, Qatar",
        current_designation="Project Manager",
        current_company="Core Engineering and Construction",
        total_experience_years=12,
        gcc_experience_years=12,
        qatar_experience_years=8,
        expected_salary=22000,
        notice_period="1 month",
        visa_status="Transferable NOC available",
        extracted_data=CandidateExtractedData(
            skills="Project Management, MEP, AutoCAD, BOQ, Estimation",
            languages=["English", "Arabic"],
            education=[
                {"raw": "Master of Engineering, Qatar University, 2015",
                 "degree": "Master of", "institution": "Qatar University", "year": 2015}
            ],
            previous_companies=[
                {"name": "Core Engineering and Construction", "title": "Project Manager", "duration": "2020-Present"},
                {"name": "Sister Group Co", "title": "Senior Engineer", "duration": "2016-2019"},
            ],
            full_text="Senior project engineer ...",
        ),
    )


def _construction_job() -> JobOpening:
    return JobOpening(
        slug="pm-construction",
        title="Project Manager",
        department="Construction",
        company="Core Engineering",
        location="Doha, Qatar",
        min_experience=8,
        max_experience=15,
        required_education="Bachelor of Engineering",
        required_skills="Project Management, MEP, AutoCAD",
        preferred_skills="BOQ, Estimation",
        salary_min=18000,
        salary_max=25000,
        visa_requirement="transferable NOC",
        language_requirement="English, Arabic",
        notice_period_preference="1 month",
        status=JOB_STATUS_OPEN,
    )


def test_strong_candidate_scores_near_max():
    result = compute_score(candidate=_strong_candidate(), job=_construction_job())
    assert result.total >= 90, f"Expected ≥90, got {result.total}: {result.notes()}"
    # No component should be zero for this candidate.
    for key, comp in result.breakdown.items():
        assert comp.points > 0, f"Component {key} was zero: {comp.note}"


def test_score_breakdown_sums_to_total():
    result = compute_score(candidate=_strong_candidate(), job=_construction_job())
    assert result.total == sum(c.points for c in result.breakdown.values())
    assert result.total <= TOTAL_MAX == 100


def test_each_component_respects_its_max():
    result = compute_score(candidate=_strong_candidate(), job=_construction_job())
    for key, comp in result.breakdown.items():
        assert comp.max_points == MAX_POINTS[key]
        assert 0 <= comp.points <= comp.max_points


def test_weak_candidate_scores_low():
    weak = Candidate(
        full_name="Junior Newcomer",
        total_experience_years=1,
        # No nationality, no skills, no salary, no visa, etc.
    )
    result = compute_score(candidate=weak, job=_construction_job())
    assert result.total < 40, f"Expected <40, got {result.total}: {result.notes()}"


def test_missing_job_returns_zero():
    result = compute_score(candidate=_strong_candidate(), job=None)
    assert result.total == 0
    assert all(c.points == 0 for c in result.breakdown.values())


def test_salary_inside_band_is_full_points():
    cand = _strong_candidate()
    cand.expected_salary = 20000  # well inside 18,000–25,000
    job = _construction_job()
    result = compute_score(candidate=cand, job=job)
    assert result.breakdown["salary_fit"].points == MAX_POINTS["salary_fit"]


def test_salary_far_above_cap_zeroes_out():
    cand = _strong_candidate()
    cand.expected_salary = 80000
    job = _construction_job()
    result = compute_score(candidate=cand, job=job)
    assert result.breakdown["salary_fit"].points == 0


def test_notice_period_match():
    cand = _strong_candidate()
    cand.notice_period = "Immediate"
    job = _construction_job()
    result = compute_score(candidate=cand, job=job)
    assert result.breakdown["notice_period"].points == MAX_POINTS["notice_period"]


def test_notice_period_far_longer_zeroes_out():
    cand = _strong_candidate()
    cand.notice_period = "6 months"
    job = _construction_job()
    result = compute_score(candidate=cand, job=job)
    assert result.breakdown["notice_period"].points == 0


def test_visa_status_missing_when_required_zeroes_out():
    cand = _strong_candidate()
    cand.visa_status = None
    job = _construction_job()
    result = compute_score(candidate=cand, job=job)
    assert result.breakdown["visa_status"].points == 0


def test_language_partial_match_scales():
    cand = _strong_candidate()
    cand.extracted_data.languages = ["English"]  # missing Arabic
    job = _construction_job()
    result = compute_score(candidate=cand, job=job)
    pts = result.breakdown["language_match"].points
    assert 0 < pts < MAX_POINTS["language_match"]


def test_industry_overlap_via_same_company():
    cand = _strong_candidate()
    # Even if the job.company differs slightly, "Core Engineering" should
    # match "Core Engineering and Construction" via substring.
    job = _construction_job()
    job.company = "Core Engineering"
    result = compute_score(candidate=cand, job=job)
    assert result.breakdown["industry_experience"].points == MAX_POINTS["industry_experience"]


# ---------------------------------------------------------------------------
# Endpoint integration tests
# ---------------------------------------------------------------------------


def _hr_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_job(db_session: Session) -> JobOpening:
    job = JobOpening(
        slug="pm-core-eng",
        title="Project Manager",
        department="Construction",
        company="Core Engineering",
        location="Doha, Qatar",
        min_experience=8,
        max_experience=15,
        required_education="Bachelor of Engineering",
        required_skills="Project Management, MEP, AutoCAD",
        preferred_skills="BOQ, Estimation",
        salary_min=18000,
        salary_max=25000,
        visa_requirement="transferable NOC",
        language_requirement="English, Arabic",
        notice_period_preference="1 month",
        status=JOB_STATUS_OPEN,
    )
    db_session.add(job)
    db_session.commit()
    return job


def _docx_bytes(text: str) -> bytes:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


SAMPLE_CV = """Ahmed Hassan
ahmed.hassan@pug.example.com
+974 5500 1122

Address: Doha, Qatar
Nationality: Qatari

Summary
Senior project engineer with 12 years of experience in the GCC including 8 years in Qatar.

Experience
Project Manager — Core Engineering and Construction, Doha — 2020 – Present

Education
Bachelor of Engineering, Qatar University, 2012

Skills
Project Management, MEP, AutoCAD, BOQ, Estimation

Languages
English, Arabic

Expected salary: QAR 22,000 per month
Notice period: 1 month
Visa status: Transferable NOC available
"""


def _upload(client: TestClient, headers: dict, job_slug: str) -> dict:
    response = client.post(
        HR_UPLOAD,
        headers=headers,
        files={
            "file": (
                "ahmed.docx",
                io.BytesIO(_docx_bytes(SAMPLE_CV)),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"full_name": "Unknown", "job_slug": job_slug},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_auto_computes_score(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid = body["candidate_id"]

    detail = client.get(f"/api/v1/hr/candidates/{cid}", headers=headers).json()
    assert detail["top_score"] is not None
    assert detail["top_score"] >= 80
    apps = detail["applications"]
    assert len(apps) == 1
    score = apps[0]["score"]
    assert score is not None
    assert score["total"] == detail["top_score"]
    assert score["breakdown"] is not None
    assert score["breakdown"]["notes"]  # explanation strings exist


def test_list_includes_top_score(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    _upload(client, headers, job.slug)

    response = client.get("/api/v1/hr/candidates", headers=headers)
    assert response.status_code == 200
    rows = response.json()
    assert rows[0]["top_score"] is not None
    assert rows[0]["top_score"] > 0


def test_recompute_endpoint(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid = body["candidate_id"]
    aid = body["application_id"]

    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/score/recompute",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    score = response.json()
    assert score["total"] > 0
    assert not score["is_manual_override"]


def test_override_requires_reason(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid = body["candidate_id"]
    aid = body["application_id"]

    # No reason → 422 (validation)
    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/score/override",
        headers=headers,
        json={"total": 95},
    )
    assert response.status_code == 422

    # Empty reason → 422
    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/score/override",
        headers=headers,
        json={"total": 95, "reason": ""},
    )
    assert response.status_code == 422


def test_override_applies_and_clears(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid = body["candidate_id"]
    aid = body["application_id"]

    # Override to 92
    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/score/override",
        headers=headers,
        json={"total": 92, "reason": "Strong interview signal from peer screen"},
    )
    assert response.status_code == 200, response.text
    score = response.json()
    assert score["total"] == 92
    assert score["is_manual_override"] is True
    assert "peer screen" in score["override_reason"]

    # Recompute keeps the override total
    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/score/recompute",
        headers=headers,
    )
    body2 = response.json()
    assert body2["total"] == 92
    assert body2["is_manual_override"] is True

    # Clear the override → restore auto total
    response = client.delete(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/score/override",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body3 = response.json()
    assert body3["is_manual_override"] is False
    assert body3["total"] != 92  # auto total restored


def test_score_explanation_notes_are_strings(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload(client, headers, job.slug)
    cid = body["candidate_id"]
    aid = body["application_id"]

    response = client.get(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/score",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    score = response.json()
    assert score["breakdown"]["notes"]
    for key in MAX_POINTS:
        assert key in score["breakdown"]["notes"]
        assert isinstance(score["breakdown"]["notes"][key], str)
