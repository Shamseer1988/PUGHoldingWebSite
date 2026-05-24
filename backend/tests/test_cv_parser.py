"""Tests for the Phase 11 CV parser heuristics."""
from __future__ import annotations

import io

import pytest

from app.services.cv_parser import (
    PARSER_VERSION,
    CvParseError,
    extract_text,
    parse_text,
)


SAMPLE_CV = """
Ahmed Al Hassan
ahmed.al-hassan@example.com
+974 5500 1122

Address: Doha, Qatar
Nationality: Qatari

Summary
Senior project engineer with 12 years of experience across the GCC, including
8 years in Qatar managing MEP works for hypermarket fit-outs.

Experience
Project Manager — Core Engineering and Construction, Doha — Jan 2020 – Present
- Led a portfolio of 12 commercial fit-out projects worth QAR 45M.
- Coordinated MEP, civil and procurement teams.

Senior Engineer at YellowTech Trading and Contracting WLL, Doha — 2016 – 2019
- Delivered turnkey construction packages for industrial clients.

Education
Master of Engineering, Qatar University, 2015
Bachelor of Engineering, ABC University, 2012

Certifications
PMP — Project Management Institute
PRINCE2 Practitioner

Skills
Project Management, MEP, AutoCAD, BOQ, Construction Management, Estimation,
Procurement, Vendor Management

Languages
English, Arabic, Hindi

Expected salary: QAR 32,000 per month
Notice period: 1 month
Visa status: Transferable NOC available
"""


def test_parse_text_extracts_headline_fields():
    parsed = parse_text(SAMPLE_CV)
    assert parsed.parser_version == PARSER_VERSION
    assert parsed.name == "Ahmed Al Hassan"
    assert parsed.email == "ahmed.al-hassan@example.com"
    # Mobile keeps its original formatting.
    assert parsed.mobile is not None and "5500" in parsed.mobile
    assert parsed.nationality == "Qatari"
    assert parsed.current_location is not None
    assert "Doha" in parsed.current_location


def test_parse_text_finds_experience_years():
    parsed = parse_text(SAMPLE_CV)
    # The largest number-of-years hit is 12.
    assert parsed.total_experience_years == 12
    # Region-aware extractors should find 8 years in Qatar and the same in GCC.
    assert parsed.qatar_experience_years == 8
    assert parsed.gcc_experience_years == 12


def test_parse_text_extracts_compensation_and_visa():
    parsed = parse_text(SAMPLE_CV)
    assert parsed.expected_salary == 32000
    assert parsed.notice_period and "month" in parsed.notice_period.lower()
    assert parsed.visa_status is not None
    assert "noc" in parsed.visa_status.lower() or "transferable" in parsed.visa_status.lower()


def test_parse_text_extracts_skills_languages_education():
    parsed = parse_text(SAMPLE_CV)

    skills_lower = {s.lower() for s in parsed.skills}
    assert "autocad" in skills_lower
    assert "mep" in skills_lower
    assert "project management" in skills_lower

    assert "English" in parsed.languages
    assert "Arabic" in parsed.languages
    assert "Hindi" in parsed.languages

    assert any("Master of" in e.raw for e in parsed.education)
    masters = next(e for e in parsed.education if "Master of" in e.raw)
    assert masters.year == 2015
    assert masters.institution is not None
    assert "Qatar University" in masters.institution


def test_parse_text_extracts_companies():
    parsed = parse_text(SAMPLE_CV)
    assert len(parsed.previous_companies) >= 1
    first = parsed.previous_companies[0]
    assert "Core Engineering" in (first.name or "")
    # Current company / designation are mirrored from the most-recent role.
    assert parsed.current_company and "Core Engineering" in parsed.current_company
    assert parsed.current_designation == "Project Manager"


def test_parse_text_handles_minimal_input():
    parsed = parse_text("No structure here, just a name: Jane Doe")
    # No reliable name in the first line; the helper bails out gracefully.
    assert parsed.email is None
    assert parsed.mobile is None
    assert parsed.skills == []
    assert parsed.education == []


def test_parse_text_email_fallback_name():
    cv = "first.last@pug.example.com\n\nSome other content goes here."
    parsed = parse_text(cv)
    assert parsed.email == "first.last@pug.example.com"
    assert parsed.name == "First Last"


def test_extract_text_rejects_legacy_doc(tmp_path):
    p = tmp_path / "old.doc"
    p.write_bytes(b"\xd0\xcf\x11\xe0")  # Old OLE header — not a DOCX/PDF.
    with pytest.raises(CvParseError):
        extract_text(p)


def test_extract_text_missing_file(tmp_path):
    with pytest.raises(CvParseError):
        extract_text(tmp_path / "does-not-exist.pdf")


def test_extract_text_unsupported_extension(tmp_path):
    p = tmp_path / "cv.xyz"
    p.write_text("hello")
    with pytest.raises(CvParseError):
        extract_text(p)


def test_extract_text_from_real_docx(tmp_path):
    """Confirm the DOCX path actually walks paragraphs."""
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("Jane Doe")
    document.add_paragraph("jane.doe@pug.example.com")
    document.add_paragraph("Skills: Python, FastAPI, React")
    p = tmp_path / "jane.docx"
    document.save(str(p))

    text = extract_text(p)
    assert "Jane Doe" in text
    assert "jane.doe@pug.example.com" in text

    parsed = parse_text(text)
    assert parsed.email == "jane.doe@pug.example.com"
    assert "Python" in parsed.skills
    assert "FastAPI" in parsed.skills
    assert "React" in parsed.skills


def test_extract_text_from_real_pdf(tmp_path):
    """Use pypdf's own writer to round-trip a tiny PDF and ensure
    extract_text doesn't crash. (We don't assert text content because
    the writer creates an empty page; the goal is to exercise the
    error-handling path on pages with no text layer.)"""
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    p = tmp_path / "blank.pdf"
    with p.open("wb") as fp:
        writer.write(fp)

    text = extract_text(p)
    assert isinstance(text, str)
