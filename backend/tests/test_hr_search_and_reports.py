"""Tests for Phase 16: advanced search filters, reports, and exports."""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    STATUS_CV_RECEIVED,
    STATUS_REJECTED,
    STATUS_SELECTED,
    STATUS_SHORTLISTED,
    Candidate,
    CandidateExtractedData,
    CandidateJobApplication,
    CandidateScore,
    JobOpening,
)


CAND_LIST = "/api/v1/hr/candidates"
REPORT_TYPES = "/api/v1/hr/reports/types"
JOB_OPTS = "/api/v1/hr/reports/options/jobs"
DEPT_OPTS = "/api/v1/hr/reports/options/departments"


def _hr_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        "/api/v1/hr/auth/login",
        json={"email": "hr@pug.example.com", "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_pipeline(db: Session) -> dict[str, int]:
    """Seed two jobs + four candidates with varied attributes."""
    job_pm = JobOpening(
        slug="pm-construction",
        title="Project Manager",
        department="Construction",
        company="Core Engineering",
        location="Doha, Qatar",
        status=JOB_STATUS_OPEN,
    )
    job_retail = JobOpening(
        slug="store-manager",
        title="Store Manager",
        department="Retail",
        company="Paris Hyper Market",
        location="Doha, Qatar",
        status=JOB_STATUS_OPEN,
    )
    db.add_all([job_pm, job_retail])
    db.flush()

    def make(
        name: str,
        email: str,
        *,
        nationality: str,
        location: str,
        experience: float,
        salary: int,
        visa: str,
        notice: str,
        skills: str,
        languages: list[str],
        education_raw: str,
        status: str,
        score: int,
        job: JobOpening,
    ) -> Candidate:
        c = Candidate(
            full_name=name,
            email=email,
            mobile=f"+97455{hash(name) % 10000:04d}",
            nationality=nationality,
            current_location=location,
            current_designation="Engineer",
            total_experience_years=experience,
            expected_salary=salary,
            visa_status=visa,
            notice_period=notice,
            extracted_data=CandidateExtractedData(
                skills=skills,
                languages=languages,
                education=[{"raw": education_raw, "degree": None}],
            ),
        )
        db.add(c)
        db.flush()
        app = CandidateJobApplication(
            candidate_id=c.id, job_opening_id=job.id, status=status
        )
        db.add(app)
        db.flush()
        s = CandidateScore(application_id=app.id, total=score)
        db.add(s)
        return c

    alice = make(
        "Alice Engineer", "alice@example.com",
        nationality="Qatari", location="Doha", experience=12, salary=20000,
        visa="Transferable NOC", notice="1 month",
        skills="Project Management, MEP, AutoCAD",
        languages=["English", "Arabic"],
        education_raw="Bachelor of Engineering, Qatar University, 2012",
        status=STATUS_SHORTLISTED, score=88, job=job_pm,
    )
    bob = make(
        "Bob Retail", "bob@example.com",
        nationality="Filipino", location="Doha", experience=5, salary=8000,
        visa="Work permit", notice="2 months",
        skills="Retail Operations, POS, Merchandising",
        languages=["English"],
        education_raw="Bachelor of Commerce, 2018",
        status=STATUS_SELECTED, score=72, job=job_retail,
    )
    cara = make(
        "Cara Distribution", "cara@example.com",
        nationality="Indian", location="Doha", experience=8, salary=14000,
        visa="Sponsorship required", notice="3 months",
        skills="FMCG, Distribution, Supply Chain",
        languages=["English", "Hindi"],
        education_raw="MBA, Karachi University, 2017",
        status=STATUS_REJECTED, score=45, job=job_pm,
    )
    dan = make(
        "Dan New", "dan@example.com",
        nationality="Pakistani", location="Doha", experience=2, salary=4500,
        visa="Visit visa", notice="Immediate",
        skills="Customer Service, Cashiering",
        languages=["English", "Urdu"],
        education_raw="Diploma in Business, 2022",
        status=STATUS_CV_RECEIVED, score=30, job=job_retail,
    )
    # Mark the rejected one with a reason so the rejected report exercises it.
    cara_app = db.execute(
        # Re-fetch via raw .applications relationship
        # (CandidateJobApplication objects already flushed above).
        # We grab it through the candidate's applications collection:
        # equivalent to: candidate.applications[0]
        # But to stay independent of relationship state we hit the table.
        db.query(CandidateJobApplication).filter_by(candidate_id=cara.id).statement
    ).scalar_one()
    cara_app.status = STATUS_REJECTED
    cara_app.last_rejection_reason = "Below the experience minimum."
    db.commit()
    return {
        "job_pm": job_pm.id,
        "job_retail": job_retail.id,
        "alice": alice.id,
        "bob": bob.id,
        "cara": cara.id,
        "dan": dan.id,
    }


# ---------------------------------------------------------------------------
# /hr/candidates — advanced filters
# ---------------------------------------------------------------------------


def test_candidate_search_by_nationality(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST, headers=headers, params={"nationality": "Qatari"}
    )
    assert response.status_code == 200
    names = [c["full_name"] for c in response.json()]
    assert names == ["Alice Engineer"]


def test_candidate_search_by_experience_range(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST,
        headers=headers,
        params={"experience_min": 5, "experience_max": 10},
    )
    names = sorted(c["full_name"] for c in response.json())
    assert names == ["Bob Retail", "Cara Distribution"]


def test_candidate_search_by_salary_range(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST,
        headers=headers,
        params={"salary_min": 10000, "salary_max": 25000},
    )
    names = sorted(c["full_name"] for c in response.json())
    assert names == ["Alice Engineer", "Cara Distribution"]


def test_candidate_search_by_visa_keyword(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST, headers=headers, params={"visa": "NOC"}
    )
    assert [c["full_name"] for c in response.json()] == ["Alice Engineer"]


def test_candidate_search_by_skill_keyword(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST, headers=headers, params={"skill": "POS"}
    )
    assert [c["full_name"] for c in response.json()] == ["Bob Retail"]


def test_candidate_search_by_language(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST, headers=headers, params={"language": "Hindi"}
    )
    assert [c["full_name"] for c in response.json()] == ["Cara Distribution"]


def test_candidate_search_by_education(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST, headers=headers, params={"education": "MBA"}
    )
    assert [c["full_name"] for c in response.json()] == ["Cara Distribution"]


def test_candidate_search_by_status(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST, headers=headers, params={"status": STATUS_SHORTLISTED}
    )
    assert [c["full_name"] for c in response.json()] == ["Alice Engineer"]


def test_candidate_search_by_job_slug(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST, headers=headers, params={"job_slug": "store-manager"}
    )
    names = sorted(c["full_name"] for c in response.json())
    assert names == ["Bob Retail", "Dan New"]


def test_candidate_search_by_department(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST, headers=headers, params={"department": "Retail"}
    )
    names = sorted(c["full_name"] for c in response.json())
    assert names == ["Bob Retail", "Dan New"]


def test_candidate_search_by_score_range(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST, headers=headers, params={"score_min": 70}
    )
    names = sorted(c["full_name"] for c in response.json())
    assert names == ["Alice Engineer", "Bob Retail"]


def test_candidate_search_by_uploaded_range(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    # Everything was just created — `from = 1 year ago` includes all.
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    response = client.get(
        CAND_LIST, headers=headers, params={"uploaded_from": one_year_ago}
    )
    assert len(response.json()) == 4


def test_candidate_search_combines_filters(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        CAND_LIST,
        headers=headers,
        params={
            "department": "Construction",
            "experience_min": 8,
            "score_min": 80,
        },
    )
    assert [c["full_name"] for c in response.json()] == ["Alice Engineer"]


# ---------------------------------------------------------------------------
# /hr/reports/* — JSON
# ---------------------------------------------------------------------------


def test_report_types_list(client, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(REPORT_TYPES, headers=headers)
    assert response.status_code == 200
    keys = [r["key"] for r in response.json()]
    for expected in (
        "shortlist",
        "job_wise_summary",
        "interview_status",
        "selected_candidates",
        "rejected_candidates",
        "salary_expectations",
        "skill_availability",
    ):
        assert expected in keys


def test_report_unknown_type_404(client, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/does-not-exist", headers=headers
    )
    assert response.status_code == 404


def test_shortlist_report_returns_only_shortlisted(
    client, db_session, seed_auth
):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/shortlist", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "shortlist"
    assert body["summary"]["count"] == 1
    names = [row[0] for row in body["rows"]]
    assert names == ["Alice Engineer"]


def test_job_wise_summary_counts_per_job(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/job_wise_summary", headers=headers
    )
    body = response.json()
    assert body["summary"]["total_cvs"] == 4
    titles = [row[0] for row in body["rows"]]
    assert "Project Manager" in titles
    assert "Store Manager" in titles


def test_selected_candidates_report(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = client.get(
        "/api/v1/hr/reports/selected_candidates", headers=headers
    ).json()
    assert [row[0] for row in body["rows"]] == ["Bob Retail"]


def test_rejected_candidates_report(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = client.get(
        "/api/v1/hr/reports/rejected_candidates", headers=headers
    ).json()
    names = [row[0] for row in body["rows"]]
    assert names == ["Cara Distribution"]
    # Rejection reason carried through
    reason_col = body["columns"].index("Rejection reason")
    assert body["rows"][0][reason_col] == "Below the experience minimum."


def test_salary_expectations_report(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = client.get(
        "/api/v1/hr/reports/salary_expectations", headers=headers
    ).json()
    # Total over all buckets should equal the 4 candidates.
    total = sum(int(row[1]) for row in body["rows"])
    assert total == 4


def test_skill_availability_report(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    body = client.get(
        "/api/v1/hr/reports/skill_availability", headers=headers
    ).json()
    skills = {row[0] for row in body["rows"]}
    # Skills from any of the 4 candidates' extracted_data show up
    assert "Project Management" in skills
    assert "POS" in skills
    assert "FMCG" in skills


def test_report_respects_filters(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    # Restrict the shortlist report to "Retail" department — Alice is
    # in Construction so the report should drop her.
    body = client.get(
        "/api/v1/hr/reports/shortlist",
        headers=headers,
        params={"department": "Retail"},
    ).json()
    assert body["summary"]["count"] == 0


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------


def test_export_csv_returns_attachment(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/shortlist/export",
        headers=headers,
        params={"format": "csv"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    # BOM + header row + 1 data row
    text = response.content.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("Name,Email")
    assert "Alice Engineer" in text


def test_export_xlsx_returns_excel_file(client, db_session, seed_auth):
    pytest.importorskip("openpyxl")
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/job_wise_summary/export",
        headers=headers,
        params={"format": "xlsx"},
    )
    assert response.status_code == 200
    # XLSX = ZIP container, starts with PK\x03\x04
    assert response.content[:2] == b"PK"
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_export_pdf_returns_pdf_file(client, db_session, seed_auth):
    pytest.importorskip("reportlab")
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/selected_candidates/export",
        headers=headers,
        params={"format": "pdf"},
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-type"] == "application/pdf"


def test_export_rejects_unknown_format(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(
        "/api/v1/hr/reports/shortlist/export",
        headers=headers,
        params={"format": "doc"},
    )
    assert response.status_code == 422


def test_export_audit_log(client, db_session, seed_auth):
    from app.models.auth import AuditLog

    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    client.get(
        "/api/v1/hr/reports/shortlist/export",
        headers=headers,
        params={"format": "csv"},
    )
    entries = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "hr.reports.export")
        .all()
    )
    assert len(entries) == 1
    assert entries[0].details["format"] == "csv"
    assert entries[0].details["rows"] == 1


# ---------------------------------------------------------------------------
# Options endpoints
# ---------------------------------------------------------------------------


def test_job_options_returns_distinct_jobs(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(JOB_OPTS, headers=headers)
    slugs = {j["slug"] for j in response.json()}
    assert slugs == {"pm-construction", "store-manager"}


def test_department_options(client, db_session, seed_auth):
    _make_pipeline(db_session)
    headers = _hr_auth(client, seed_auth["password"])
    response = client.get(DEPT_OPTS, headers=headers)
    depts = response.json()
    assert set(depts) == {"Construction", "Retail"}
