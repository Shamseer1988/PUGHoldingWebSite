"""Integration tests for the Phase 10 candidate-intake endpoints."""
from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    Candidate,
    CandidateDocument,
    CandidateJobApplication,
    JobOpening,
)


PUBLIC_APPLY = "/api/v1/public/candidate-applications"
HR_UPLOAD = "/api/v1/hr/candidates/upload"
HR_BULK = "/api/v1/hr/candidates/bulk-upload"
HR_LIST = "/api/v1/hr/candidates"
HR_LOGIN = "/api/v1/hr/auth/login"
ADMIN_LOGIN = "/api/v1/admin/auth/login"


# Minimal "fake PDF" — content doesn't matter, but the magic bytes do for
# any future content-sniffing. Treated as application/pdf by our service.
TINY_PDF = b"%PDF-1.4\n%fake-pdf-content-for-tests\n"


def _hr_auth(client: TestClient, password: str) -> dict:
    response = client.post(
        HR_LOGIN, json={"email": "hr@pug.example.com", "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_job(db_session: Session, slug: str = "ev-tech") -> JobOpening:
    job = JobOpening(
        slug=slug,
        title="EV Technician",
        department="Vehicle Service",
        company="YellowTech Garage",
        location="Doha",
        status=JOB_STATUS_OPEN,
    )
    db_session.add(job)
    db_session.commit()
    return job


# ---------------------------------------------------------------------------
# Public candidate-application endpoint
# ---------------------------------------------------------------------------


def test_public_application_creates_candidate_doc_and_app(
    client, db_session: Session
):
    job = _make_job(db_session)

    response = client.post(
        PUBLIC_APPLY,
        files={"file": ("alice.pdf", io.BytesIO(TINY_PDF), "application/pdf")},
        data={
            "full_name": "Alice Example",
            "email": "alice@example.com",
            "mobile": "+974 1111 2222",
            "job_slug": job.slug,
            "nationality": "QA",
            "current_location": "Doha",
            "total_experience_years": "4.5",
            "expected_salary": "8000",
            "notice_period": "1 month",
            "cover_letter": "Looking forward to joining.",
            "consent": "true",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["candidate_id"] > 0
    assert body["application_id"] > 0
    assert body["job_slug"] == job.slug
    assert body["was_existing_candidate"] is False

    candidates = list(db_session.execute(select(Candidate)).scalars())
    assert len(candidates) == 1
    assert candidates[0].email == "alice@example.com"
    assert candidates[0].mobile == "+974 1111 2222"
    assert candidates[0].source == "public_form"

    docs = list(db_session.execute(select(CandidateDocument)).scalars())
    assert len(docs) == 1
    assert docs[0].is_primary is True
    assert docs[0].file_hash is not None
    assert docs[0].file_path.startswith("/api/v1/uploads/cvs/")

    apps = list(db_session.execute(select(CandidateJobApplication)).scalars())
    assert len(apps) == 1
    assert apps[0].status == "cv_received"

    audit = [
        r.action for r in db_session.execute(select(AuditLog)).scalars()
    ]
    assert "public.candidate.apply" in audit


def test_public_application_requires_consent(client, db_session: Session):
    response = client.post(
        PUBLIC_APPLY,
        files={"file": ("a.pdf", io.BytesIO(TINY_PDF), "application/pdf")},
        data={
            "full_name": "Bob",
            "email": "bob@example.com",
            "mobile": "+974111",
            "consent": "false",
        },
    )
    assert response.status_code == 400
    assert "Consent" in response.json()["detail"]


def test_public_application_rejects_unsupported_file_type(
    client, db_session: Session
):
    response = client.post(
        PUBLIC_APPLY,
        files={"file": ("c.exe", io.BytesIO(b"MZ-bad"), "application/octet-stream")},
        data={
            "full_name": "Carla",
            "email": "carla@example.com",
            "mobile": "+97411",
            "consent": "true",
        },
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_public_application_dedupes_via_email(client, db_session: Session):
    job = _make_job(db_session)

    first = client.post(
        PUBLIC_APPLY,
        files={"file": ("a.pdf", io.BytesIO(TINY_PDF), "application/pdf")},
        data={
            "full_name": "Diana",
            "email": "diana@example.com",
            "mobile": "+974 1111 0001",
            "job_slug": job.slug,
            "consent": "true",
        },
    )
    assert first.status_code == 201

    # Same email applies to a DIFFERENT job — should attach to the same
    # candidate (was_existing_candidate=True), new application created.
    job2 = _make_job(db_session, slug="cashier")
    other = client.post(
        PUBLIC_APPLY,
        files={"file": ("b.pdf", io.BytesIO(b"%PDF-1.4\nother"), "application/pdf")},
        data={
            "full_name": "Diana Different",
            "email": "DIANA@example.com",  # case-insensitive
            "mobile": "+9745555",
            "job_slug": job2.slug,
            "consent": "true",
        },
    )
    assert other.status_code == 201
    assert other.json()["was_existing_candidate"] is True
    assert other.json()["candidate_id"] == first.json()["candidate_id"]

    # Same job + same candidate → 409
    again = client.post(
        PUBLIC_APPLY,
        files={"file": ("c.pdf", io.BytesIO(b"%PDF-1.4\nthird"), "application/pdf")},
        data={
            "full_name": "Diana",
            "email": "diana@example.com",
            "mobile": "+974 1111 0001",
            "job_slug": job.slug,
            "consent": "true",
        },
    )
    assert again.status_code == 409


def test_public_application_dedupes_via_mobile(client, db_session: Session):
    """Mobile dedup ignores spaces / dashes / plus."""
    job = _make_job(db_session)
    first = client.post(
        PUBLIC_APPLY,
        files={"file": ("a.pdf", io.BytesIO(TINY_PDF), "application/pdf")},
        data={
            "full_name": "Eric",
            "email": "eric+a@example.com",
            "mobile": "+974 5555 6666",
            "job_slug": job.slug,
            "consent": "true",
        },
    )
    assert first.status_code == 201

    job2 = _make_job(db_session, slug="hrbp")
    second = client.post(
        PUBLIC_APPLY,
        files={"file": ("b.pdf", io.BytesIO(b"%PDF-1.4\nB"), "application/pdf")},
        data={
            "full_name": "Eric Different",
            "email": "different@example.com",
            "mobile": "+97455556666",  # same digits
            "job_slug": job2.slug,
            "consent": "true",
        },
    )
    assert second.status_code == 201
    assert second.json()["was_existing_candidate"] is True
    assert second.json()["candidate_id"] == first.json()["candidate_id"]


def test_public_application_dedupes_via_file_hash(client, db_session: Session):
    """Re-uploading the SAME file links to the same candidate."""
    job = _make_job(db_session)
    first = client.post(
        PUBLIC_APPLY,
        files={"file": ("a.pdf", io.BytesIO(TINY_PDF), "application/pdf")},
        data={
            "full_name": "Fred",
            "email": "fred@example.com",
            "mobile": "+97444",
            "job_slug": job.slug,
            "consent": "true",
        },
    )

    job2 = _make_job(db_session, slug="another-role")
    # Different applicant fields, identical CV bytes.
    second = client.post(
        PUBLIC_APPLY,
        files={"file": ("renamed.pdf", io.BytesIO(TINY_PDF), "application/pdf")},
        data={
            "full_name": "Disguised Name",
            "email": "totally-different@example.com",
            "mobile": "+97499",
            "job_slug": job2.slug,
            "consent": "true",
        },
    )
    assert second.status_code == 201
    assert second.json()["was_existing_candidate"] is True
    assert second.json()["candidate_id"] == first.json()["candidate_id"]


# ---------------------------------------------------------------------------
# HR single-CV upload
# ---------------------------------------------------------------------------


def test_hr_manual_upload_requires_hr_scope(client, seed_auth):
    admin_login = client.post(
        ADMIN_LOGIN,
        json={"email": "webadmin@pug.example.com", "password": seed_auth["password"]},
    )
    admin_token = admin_login.json()["access_token"]
    response = client.post(
        HR_UPLOAD,
        files={"file": ("a.pdf", io.BytesIO(TINY_PDF), "application/pdf")},
        data={"full_name": "X"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403


def test_hr_manual_upload_creates_candidate(client, seed_auth, db_session: Session):
    headers = _hr_auth(client, seed_auth["password"])
    response = client.post(
        HR_UPLOAD,
        files={"file": ("g.pdf", io.BytesIO(TINY_PDF), "application/pdf")},
        data={
            "full_name": "Gregory",
            "email": "greg@example.com",
            "mobile": "+97411112222",
            "visa_status": "Transferable",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["was_existing_candidate"] is False

    candidate = db_session.get(Candidate, body["candidate_id"])
    assert candidate is not None
    assert candidate.visa_status == "Transferable"
    assert candidate.source == "manual_upload"

    audit_actions = [
        r.action for r in db_session.execute(select(AuditLog)).scalars()
    ]
    assert "hr.candidate.manual_upload" in audit_actions


# ---------------------------------------------------------------------------
# HR list + detail
# ---------------------------------------------------------------------------


def test_hr_list_and_detail(client, seed_auth, db_session: Session):
    headers = _hr_auth(client, seed_auth["password"])
    client.post(
        HR_UPLOAD,
        files={"file": ("h.pdf", io.BytesIO(TINY_PDF), "application/pdf")},
        data={"full_name": "Helen", "email": "helen@example.com"},
        headers=headers,
    )

    listing = client.get(HR_LIST, headers=headers).json()
    assert any(c["full_name"] == "Helen" for c in listing)
    candidate_id = listing[0]["id"]

    detail = client.get(f"{HR_LIST}/{candidate_id}", headers=headers).json()
    assert detail["full_name"]
    assert len(detail["documents"]) >= 1
    assert detail["documents"][0]["file_hash"] is not None


def test_hr_list_search(client, seed_auth, db_session: Session):
    headers = _hr_auth(client, seed_auth["password"])
    for i, name in enumerate(["Alpha", "Beta", "Gamma"]):
        client.post(
            HR_UPLOAD,
            files={"file": (f"{i}.pdf", io.BytesIO(f"%PDF-{i}".encode()), "application/pdf")},
            data={"full_name": name, "email": f"{name.lower()}@example.com"},
            headers=headers,
        )

    listing = client.get(f"{HR_LIST}?q=beta", headers=headers).json()
    assert {c["full_name"] for c in listing} == {"Beta"}


# ---------------------------------------------------------------------------
# HR bulk ZIP upload
# ---------------------------------------------------------------------------


def _build_zip(entries: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return buf.getvalue()


def test_hr_bulk_upload_processes_zip(client, seed_auth, db_session: Session):
    headers = _hr_auth(client, seed_auth["password"])
    job = _make_job(db_session, slug="bulk-target")

    zip_bytes = _build_zip(
        [
            ("alpha.pdf", b"%PDF-1.4\nalpha"),
            ("beta.docx", b"PKfakedocxbytes-beta"),
            ("notes.txt", b"text file - should be skipped"),
            ("__MACOSX/.DS_Store", b"junk"),  # silently ignored
        ]
    )

    response = client.post(
        HR_BULK,
        files={"file": ("batch.zip", io.BytesIO(zip_bytes), "application/zip")},
        data={"job_slug": job.slug},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created_candidates"] == 2  # alpha + beta
    assert body["matched_existing_candidates"] == 0
    # notes.txt should be the only skipped entry visible (.DS_Store ignored)
    assert any("notes.txt" in s["name"] for s in body["skipped_files"])

    candidates = list(
        db_session.execute(
            select(Candidate).where(Candidate.source == "bulk_upload")
        ).scalars()
    )
    assert len(candidates) == 2
    names = {c.full_name for c in candidates}
    assert "alpha" in names
    assert "beta" in names

    audit_actions = [
        r.action for r in db_session.execute(select(AuditLog)).scalars()
    ]
    assert "hr.candidate.bulk_upload" in audit_actions


def test_hr_bulk_upload_rejects_bad_zip(client, seed_auth):
    headers = _hr_auth(client, seed_auth["password"])
    response = client.post(
        HR_BULK,
        files={"file": ("bad.zip", io.BytesIO(b"not a zip"), "application/zip")},
        headers=headers,
    )
    assert response.status_code == 400
