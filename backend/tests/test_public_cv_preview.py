"""Tests for the public CV parse-preview endpoint (advanced module phase 7).

The endpoint must:

* Accept PDF / DOCX / PNG / JPG uploads and return the extracted fields.
* Reject empty / oversized / unsupported uploads with a clear 400 message.
* Reject legacy ``.doc`` files with a helpful "please upload PDF or DOCX".
* **Never** create Candidate / CandidateDocument / CandidateJobApplication rows.
* Delete the temp file after parsing (no upload-dir CV pile-up).
"""
from __future__ import annotations

import io

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rate_limit import reset_rate_limits
from app.models.hr_ats import (
    Candidate,
    CandidateDocument,
    CandidateJobApplication,
)


PREVIEW = "/api/v1/public/candidate-applications/parse-preview"


@pytest.fixture(autouse=True)
def _no_rate_limit():
    reset_rate_limits()
    yield
    reset_rate_limits()


def _docx_bytes(text: str) -> bytes:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


SAMPLE_BODY = """John Smith
john.smith@example.com
+974 5566 7788

Address: Doha, Qatar
Nationality: British

Skills
Python, FastAPI, PostgreSQL, AWS

Expected salary: QAR 25,000 per month
Notice period: 1 month
"""


def test_parse_preview_returns_extracted_fields(client, db_session: Session):
    response = client.post(
        PREVIEW,
        files={
            "file": (
                "cv.docx",
                _docx_bytes(SAMPLE_BODY),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parsed"] is True
    assert body["parser_version"]
    assert body["full_name"] == "John Smith"
    assert body["email"] == "john.smith@example.com"
    assert body["mobile"]  # any non-empty string
    assert body["nationality"] == "British"
    assert "Python" in (body["skills"] or "")

    # No candidate/application/document row was created.
    assert db_session.execute(select(Candidate)).scalars().first() is None
    assert (
        db_session.execute(select(CandidateJobApplication)).scalars().first() is None
    )
    assert db_session.execute(select(CandidateDocument)).scalars().first() is None


def test_parse_preview_rejects_legacy_doc(client):
    response = client.post(
        PREVIEW,
        files={
            "file": ("cv.doc", b"PK\x03\x04 fake", "application/msword"),
        },
    )
    assert response.status_code == 400
    assert "PDF or DOCX" in response.json()["detail"]


def test_parse_preview_rejects_empty_file(client):
    response = client.post(
        PREVIEW,
        files={"file": ("cv.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    assert "Empty" in response.json()["detail"]


def test_parse_preview_rejects_unsupported_extension(client):
    response = client.post(
        PREVIEW,
        files={"file": ("cv.exe", b"garbage", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_parse_preview_returns_parsed_false_on_unparseable_pdf(client):
    """A PDF-looking buffer that pypdf can't read returns parsed=false."""
    response = client.post(
        PREVIEW,
        files={"file": ("cv.pdf", b"not really a pdf", "application/pdf")},
    )
    # The endpoint catches CvParseError and returns parsed:false with a
    # warning message rather than 500.
    assert response.status_code == 200
    body = response.json()
    assert body["parsed"] is False
    assert body["warnings"]
