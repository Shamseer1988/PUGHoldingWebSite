"""Integration tests for the Phase 11 candidate-parser endpoints."""
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


HR_LOGIN = "/api/v1/hr/auth/login"
HR_UPLOAD = "/api/v1/hr/candidates/upload"


def _hr_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_job(db_session: Session, slug: str = "pm-construction") -> JobOpening:
    job = JobOpening(
        slug=slug,
        title="Project Manager",
        department="Construction",
        company="Core Engineering",
        location="Doha",
        status=JOB_STATUS_OPEN,
    )
    db_session.add(job)
    db_session.commit()
    return job


def _docx_bytes(text: str) -> bytes:
    """Build a tiny in-memory DOCX with each line as its own paragraph."""
    docx = pytest.importorskip("docx")
    document = docx.Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


SAMPLE_BODY = """Sarah Khan
sarah.khan@pug.example.com
+974 7733 2211

Address: Doha, Qatar
Nationality: Pakistani

Summary
Retail operations lead with 9 years of GCC experience.

Experience
Operations Manager — Paris Hyper Market, Doha — 2021 – Present
Assistant Manager at Al Mihrab Groceries — 2017 – 2021

Education
MBA, Qatar University, 2017
Bachelor of Commerce, Karachi University, 2012

Skills
Retail Operations, Merchandising, Inventory Management, POS, Customer Service

Languages
English, Urdu, Arabic

Expected salary: QAR 18,000 per month
Notice period: 2 months
Visa status: Transferable NOC available
"""


def _upload_candidate(client: TestClient, headers: dict, slug: str | None = None) -> dict:
    payload = _docx_bytes(SAMPLE_BODY)
    data: dict = {
        "full_name": "Unknown",
        "email": "",
        "mobile": "",
    }
    if slug:
        data["job_slug"] = slug
    response = client.post(
        HR_UPLOAD,
        headers=headers,
        files={
            "file": (
                "sarah.docx",
                io.BytesIO(payload),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data=data,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_hr_single_upload_runs_parser_and_persists_extracted_data(
    client, db_session: Session, seed_auth
):
    """After uploading a CV with the rich sample body, the candidate row
    must be auto-populated and a CandidateExtractedData row must exist."""
    job = _make_job(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    result = _upload_candidate(client, headers, job.slug)

    candidate = db_session.get(Candidate, result["candidate_id"])
    assert candidate is not None
    # Manually-supplied full name was "Unknown" — parser should replace it.
    assert candidate.full_name == "Sarah Khan"
    assert candidate.email == "sarah.khan@pug.example.com"
    assert candidate.mobile and "7733" in candidate.mobile
    assert candidate.nationality == "Pakistani"
    assert candidate.current_designation == "Operations Manager"
    assert candidate.current_company and "Paris Hyper Market" in candidate.current_company
    assert candidate.expected_salary == 18000
    assert candidate.notice_period and "month" in candidate.notice_period.lower()
    assert candidate.visa_status is not None
    assert candidate.total_experience_years == 9
    assert candidate.gcc_experience_years == 9

    extracted = candidate.extracted_data
    assert extracted is not None
    assert extracted.parser_version is not None
    assert extracted.skills and "Retail Operations" in extracted.skills
    assert extracted.languages and "Arabic" in extracted.languages
    assert extracted.education and any(
        edu["raw"].startswith("MBA") for edu in extracted.education
    )
    assert extracted.full_text and "Sarah Khan" in extracted.full_text


def test_hr_extracted_data_endpoints_round_trip(
    client, db_session: Session, seed_auth
):
    headers = _hr_auth(client, seed_auth["password"])
    result = _upload_candidate(client, headers)

    cid = result["candidate_id"]
    # GET extracted data
    response = client.get(
        f"/api/v1/hr/candidates/{cid}/extracted-data", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "Retail Operations" in body["skills"]
    assert "Arabic" in body["languages"]

    # PATCH with HR corrections
    response = client.patch(
        f"/api/v1/hr/candidates/{cid}/extracted-data",
        headers=headers,
        json={
            "skills": "Retail Operations, P&L, Team Leadership",
            "languages": ["English", "Urdu", "Arabic", "Hindi"],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "Team Leadership" in body["skills"]
    assert "Hindi" in body["languages"]


def test_hr_candidate_update_endpoint(client, db_session: Session, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    result = _upload_candidate(client, headers)
    cid = result["candidate_id"]

    response = client.patch(
        f"/api/v1/hr/candidates/{cid}",
        headers=headers,
        json={
            "full_name": "Sarah K. Khan",
            "expected_salary": 20000,
            "notice_period": "1 month",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["full_name"] == "Sarah K. Khan"
    assert body["expected_salary"] == 20000
    assert body["notice_period"] == "1 month"


def test_hr_reparse_endpoint(client, db_session: Session, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    result = _upload_candidate(client, headers)
    cid = result["candidate_id"]

    # Wipe the persisted extracted data so reparse has work to do.
    extracted = (
        db_session.query(CandidateExtractedData)
        .filter_by(candidate_id=cid)
        .first()
    )
    if extracted is not None:
        db_session.delete(extracted)
        db_session.commit()

    response = client.post(
        f"/api/v1/hr/candidates/{cid}/parse-cv", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parsed"] is True
    assert body["parser_version"]
    assert body["candidate"]["extracted_data"] is not None
    assert "Retail Operations" in body["candidate"]["extracted_data"]["skills"]


def test_hr_reparse_no_documents_returns_400(client, db_session: Session, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    # Empty candidate with no documents
    candidate = Candidate(full_name="Empty Person")
    db_session.add(candidate)
    db_session.commit()

    response = client.post(
        f"/api/v1/hr/candidates/{candidate.id}/parse-cv", headers=headers
    )
    assert response.status_code == 400


def test_hr_extracted_data_404_when_missing(client, db_session: Session, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    candidate = Candidate(full_name="No Docs")
    db_session.add(candidate)
    db_session.commit()

    response = client.get(
        f"/api/v1/hr/candidates/{candidate.id}/extracted-data", headers=headers
    )
    assert response.status_code == 404
