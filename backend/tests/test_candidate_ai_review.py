"""Tests for the Phase 13 HR AI candidate review (mock + endpoint)."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.candidate_review import (
    AI_MODE_DISABLED,
    AI_MODE_LIVE,
    AI_MODE_MOCK,
    AIDisabledError,
    ALLOWED_RECOMMENDATIONS,
    FORBIDDEN_RECOMMENDATIONS,
    AIReviewResult,
    ResolvedAIConfig,
    _enforce_advisory_rules,
    generate_review,
)
from app.models.hr_ats import (
    AISetting,
    Candidate,
    CandidateAIReview,
    CandidateExtractedData,
    CandidateJobApplication,
    JOB_STATUS_OPEN,
    JobOpening,
)


HR_LOGIN = "/api/v1/hr/auth/login"
HR_UPLOAD = "/api/v1/hr/candidates/upload"
ADMIN_LOGIN = "/api/v1/admin/auth/login"


# ---------------------------------------------------------------------------
# Unit tests — rule enforcement
# ---------------------------------------------------------------------------


def _result_with_recommendation(rec: str) -> AIReviewResult:
    return AIReviewResult(
        summary="", strengths="", weaknesses="",
        missing_information="", risk_points="",
        suggested_questions="", recommendation=rec,
    )


def test_enforce_rules_strips_select():
    r = _result_with_recommendation("select")
    _enforce_advisory_rules(r)
    assert r.recommendation == "needs_more_info"


def test_enforce_rules_strips_reject():
    r = _result_with_recommendation("reject")
    _enforce_advisory_rules(r)
    assert r.recommendation == "needs_more_info"


def test_enforce_rules_strips_hire_variants():
    for forbidden in FORBIDDEN_RECOMMENDATIONS:
        r = _result_with_recommendation(forbidden)
        _enforce_advisory_rules(r)
        assert r.recommendation == "needs_more_info", forbidden


def test_enforce_rules_normalises_aliases():
    r = _result_with_recommendation("good_fit")
    _enforce_advisory_rules(r)
    assert r.recommendation == "strong_fit"

    r = _result_with_recommendation("not_enough_info")
    _enforce_advisory_rules(r)
    assert r.recommendation == "needs_more_info"


def test_enforce_rules_handles_dashes_and_spaces():
    r = _result_with_recommendation("Strong Fit")
    _enforce_advisory_rules(r)
    assert r.recommendation == "strong_fit"

    r = _result_with_recommendation("possible-fit")
    _enforce_advisory_rules(r)
    assert r.recommendation == "possible_fit"


def test_enforce_rules_empty_defaults_to_needs_more_info():
    r = _result_with_recommendation("")
    _enforce_advisory_rules(r)
    assert r.recommendation == "needs_more_info"


# ---------------------------------------------------------------------------
# Unit tests — mock generator
# ---------------------------------------------------------------------------


def _strong_candidate() -> Candidate:
    return Candidate(
        full_name="Ahmed Hassan",
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
            skills="Project Management, MEP, AutoCAD",
            languages=["English", "Arabic"],
        ),
    )


def _job() -> JobOpening:
    return JobOpening(
        slug="pm-core-eng",
        title="Project Manager",
        department="Construction",
        company="Core Engineering",
        location="Doha, Qatar",
        min_experience=8,
        max_experience=15,
        required_education="Bachelor of Engineering",
        required_skills="Project Management, MEP, AutoCAD",
        salary_min=18000,
        salary_max=25000,
        visa_requirement="transferable NOC",
        language_requirement="English, Arabic",
        notice_period_preference="1 month",
        status=JOB_STATUS_OPEN,
    )


def _mock_config() -> ResolvedAIConfig:
    return ResolvedAIConfig(
        mode=AI_MODE_MOCK,
        azure_endpoint=None,
        azure_deployment=None,
        azure_api_key=None,
        azure_api_version=None,
        model_name="mock",
        temperature=0.2,
        max_output_tokens=900,
        request_timeout_seconds=45,
        extra_system_prompt=None,
    )


def test_mock_review_strong_candidate():
    candidate = _strong_candidate()
    app = CandidateJobApplication(candidate=candidate, job_opening=_job(), status="cv_received")
    result = generate_review(
        candidate=candidate, application=app, job=app.job_opening, config=_mock_config()
    )
    assert result.recommendation in ALLOWED_RECOMMENDATIONS
    assert result.recommendation == "strong_fit"
    assert "Project Manager" in result.summary
    assert result.strengths
    assert result.suggested_questions.count("\n") >= 2
    assert result.model_name == "mock@phase13"
    assert result.raw_response is not None and result.raw_response.get("mode") == "mock"


def test_mock_review_missing_info_returns_needs_more_info():
    candidate = Candidate(full_name="No Data Person")
    app = CandidateJobApplication(candidate=candidate, job_opening=_job(), status="cv_received")
    result = generate_review(
        candidate=candidate, application=app, job=app.job_opening, config=_mock_config()
    )
    assert result.recommendation == "needs_more_info"
    assert result.missing_information


def test_disabled_mode_raises():
    config = ResolvedAIConfig(
        mode=AI_MODE_DISABLED,
        azure_endpoint=None,
        azure_deployment=None,
        azure_api_key=None,
        azure_api_version=None,
        model_name=None,
        temperature=0.2,
        max_output_tokens=900,
        request_timeout_seconds=45,
        extra_system_prompt=None,
    )
    candidate = _strong_candidate()
    app = CandidateJobApplication(candidate=candidate, job_opening=_job(), status="cv_received")
    with pytest.raises(AIDisabledError):
        generate_review(
            candidate=candidate, application=app, job=app.job_opening, config=config
        )


# ---------------------------------------------------------------------------
# Endpoint integration tests
# ---------------------------------------------------------------------------


def _hr_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _admin_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        ADMIN_LOGIN, json={"email": "superadmin@pug.example.com", "password": password}
    )
    assert response.status_code == 200, response.text
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


def _set_ai_mode(db_session: Session, mode: str) -> AISetting:
    setting = db_session.get(AISetting, 1)
    if setting is None:
        setting = AISetting(id=1)
        db_session.add(setting)
    setting.mode = mode
    db_session.commit()
    return setting


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
Project Management, MEP, AutoCAD

Languages
English, Arabic

Expected salary: QAR 22,000 per month
Notice period: 1 month
Visa status: Transferable NOC available
"""


def _upload_candidate(client: TestClient, headers: dict, job_slug: str) -> dict:
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


def test_disabled_mode_returns_409(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    _set_ai_mode(db_session, AI_MODE_DISABLED)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload_candidate(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/ai-review",
        headers=headers,
    )
    assert response.status_code == 409, response.text
    assert "disabled" in response.json()["detail"].lower()


def test_mock_mode_generates_review(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    _set_ai_mode(db_session, AI_MODE_MOCK)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload_candidate(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    response = client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/ai-review",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body2 = response.json()
    assert body2["mode"] == "mock"
    review = body2["review"]
    assert review["recommendation"] in ALLOWED_RECOMMENDATIONS
    assert review["summary"]
    assert review["suggested_questions"]
    assert review["model_name"] == "mock@phase13"


def test_get_ai_review_after_generate(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    _set_ai_mode(db_session, AI_MODE_MOCK)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload_candidate(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    # Before generating → 404
    response = client.get(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/ai-review",
        headers=headers,
    )
    assert response.status_code == 404

    # Generate
    client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/ai-review",
        headers=headers,
    )
    # Now fetch
    response = client.get(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/ai-review",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["recommendation"] in ALLOWED_RECOMMENDATIONS


def test_delete_ai_review(client, db_session: Session, seed_auth):
    job = _make_job(db_session)
    _set_ai_mode(db_session, AI_MODE_MOCK)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload_candidate(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/ai-review",
        headers=headers,
    )
    response = client.delete(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/ai-review",
        headers=headers,
    )
    assert response.status_code == 204

    # Subsequent GET → 404 again
    response = client.get(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/ai-review",
        headers=headers,
    )
    assert response.status_code == 404


def test_candidate_detail_includes_ai_preview(
    client, db_session: Session, seed_auth
):
    job = _make_job(db_session)
    _set_ai_mode(db_session, AI_MODE_MOCK)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload_candidate(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]
    client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/ai-review",
        headers=headers,
    )

    detail = client.get(f"/api/v1/hr/candidates/{cid}", headers=headers).json()
    app = detail["applications"][0]
    assert app["ai_review"] is not None
    assert app["ai_review"]["recommendation"] in ALLOWED_RECOMMENDATIONS


# ---------------------------------------------------------------------------
# Admin AI settings endpoint
# ---------------------------------------------------------------------------


def test_admin_get_ai_settings(client, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    response = client.get("/api/v1/admin/ai/settings", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == 1
    assert body["mode"] in ("disabled", "mock", "live")
    assert "has_azure_api_key" in body
    assert "effective_mode" in body


def test_admin_patch_ai_settings_audits(
    client, db_session: Session, seed_auth
):
    headers = _admin_auth(client, seed_auth["password"])
    response = client.patch(
        "/api/v1/admin/ai/settings",
        headers=headers,
        json={"mode": "mock", "temperature": 0.4, "model_name": "gpt-4o"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "mock"
    assert body["temperature"] == 0.4
    assert body["model_name"] == "gpt-4o"


def test_admin_patch_ai_settings_rejects_invalid_mode(client, seed_auth):
    headers = _admin_auth(client, seed_auth["password"])
    response = client.patch(
        "/api/v1/admin/ai/settings",
        headers=headers,
        json={"mode": "magic"},
    )
    assert response.status_code == 422


def test_hr_user_cannot_access_admin_ai_settings(client, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get("/api/v1/admin/ai/settings", headers=headers)
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Safety: the AI never selects/rejects
# ---------------------------------------------------------------------------


def test_full_round_trip_recommendation_is_advisory(
    client, db_session: Session, seed_auth
):
    """End-to-end check: even though the mock returns 'strong_fit',
    the candidate's status must not change and no auto-status was set."""
    job = _make_job(db_session)
    _set_ai_mode(db_session, AI_MODE_MOCK)
    headers = _hr_auth(client, seed_auth["password"])
    body = _upload_candidate(client, headers, job.slug)
    cid, aid = body["candidate_id"], body["application_id"]

    pre_status_response = client.get(f"/api/v1/hr/candidates/{cid}", headers=headers)
    pre_status = pre_status_response.json()["applications"][0]["status"]

    client.post(
        f"/api/v1/hr/candidates/{cid}/applications/{aid}/ai-review",
        headers=headers,
    )

    post_status_response = client.get(f"/api/v1/hr/candidates/{cid}", headers=headers)
    post_status = post_status_response.json()["applications"][0]["status"]

    # AI must NOT have changed the status (the rule is "AI only recommends").
    assert post_status == pre_status
