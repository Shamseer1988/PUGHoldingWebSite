"""Offer letter PDF generation (Feature F3).

Renders a single-file PDF from an :class:`OfferTracking` row plus the
related ``Candidate`` and ``JobOpening``. Uses ``reportlab`` (already
in requirements for the HR Excel exports) so we don't need a new
dependency or a binary like wkhtmltopdf.

The template is intentionally simple and self-contained — a company
header, recipient block, the offer body, a benefits / terms section,
and a signature line. Customising the layout later is a matter of
editing :func:`build_offer_letter_pdf`; the API surface stays
stable.

If a field on the offer is missing (e.g. ``salary_offered`` not yet
filled in), that line is dropped from the PDF rather than rendering
"None". Producing a partial-but-readable letter is more useful than
refusing to render until every field is populated.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.hr_ats import Candidate, JobOpening, OfferTracking


# Company branding lives in one place so a rebrand is a one-line edit.
COMPANY_NAME = "Paris United Group Holding"
COMPANY_TAGLINE = "Building tomorrow's Qatar"
# A real deploy would pull these from EmailSettings or a SiteSettings
# table; for now they're constants matching the existing branding the
# email templates use.
COMPANY_ADDRESS_LINES = (
    "Paris United Group Holding W.L.L.",
    "Doha, Qatar",
)


def _money(value: Optional[int], currency: str = "QAR") -> Optional[str]:
    if value is None:
        return None
    return f"{currency} {value:,}"


def _format_date(value: Optional[date]) -> Optional[str]:
    if value is None:
        return None
    return value.strftime("%d %B %Y")


def build_offer_letter_pdf(
    offer: OfferTracking,
    candidate: Candidate,
    job: Optional[JobOpening],
) -> bytes:
    """Render the offer-letter PDF and return the raw bytes.

    The caller is responsible for streaming the bytes back; this
    function is pure (no I/O, no DB access). Easy to unit-test.
    """
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "OfferH1",
        parent=styles["Heading1"],
        alignment=TA_CENTER,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#5a4a17"),
        spaceAfter=4,
    )
    h_tag = ParagraphStyle(
        "OfferTag",
        parent=styles["Italic"],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.HexColor("#7a6a37"),
        spaceAfter=18,
    )
    h2 = ParagraphStyle(
        "OfferH2",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
        fontSize=14,
        leading=18,
        spaceBefore=6,
        spaceAfter=12,
        textColor=colors.HexColor("#1f2937"),
    )
    body = ParagraphStyle(
        "OfferBody",
        parent=styles["BodyText"],
        alignment=TA_LEFT,
        fontSize=10.5,
        leading=15,
        spaceAfter=8,
    )
    small = ParagraphStyle(
        "OfferSmall",
        parent=styles["BodyText"],
        alignment=TA_LEFT,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4b5563"),
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Offer Letter — {candidate.full_name}",
        author=COMPANY_NAME,
    )

    story: list = []

    # --- Company header --------------------------------------------------
    story.append(Paragraph(COMPANY_NAME, h1))
    story.append(Paragraph(COMPANY_TAGLINE, h_tag))
    for line in COMPANY_ADDRESS_LINES:
        story.append(Paragraph(line, small))
    story.append(Spacer(1, 10 * mm))

    # --- Letter title ----------------------------------------------------
    title_bits = ["LETTER OF EMPLOYMENT OFFER"]
    if offer.offer_letter_number:
        title_bits.append(f"Reference: {offer.offer_letter_number}")
    story.append(Paragraph(title_bits[0], h2))
    if len(title_bits) > 1:
        story.append(Paragraph(title_bits[1], small))
    today = _format_date(date.today())
    story.append(Paragraph(f"Date: {today}", small))
    story.append(Spacer(1, 6 * mm))

    # --- Recipient block ------------------------------------------------
    story.append(Paragraph(f"<b>{candidate.full_name}</b>", body))
    addr_lines = [
        candidate.email,
        candidate.mobile,
        candidate.current_location,
    ]
    for line in addr_lines:
        if line:
            story.append(Paragraph(line, small))
    story.append(Spacer(1, 6 * mm))

    # --- Salutation + opening -------------------------------------------
    first_name = (candidate.full_name or "Candidate").split()[0]
    story.append(Paragraph(f"Dear {first_name},", body))
    position_phrase = (
        offer.position
        or (job.title if job is not None else None)
        or "the position"
    )
    company_phrase = (
        (job.company if job is not None and job.company else COMPANY_NAME)
    )
    story.append(
        Paragraph(
            f"We are delighted to extend this offer of employment for the "
            f"role of <b>{position_phrase}</b> with <b>{company_phrase}</b>. "
            f"Below are the principal terms of your engagement.",
            body,
        )
    )
    story.append(Spacer(1, 4 * mm))

    # --- Offer terms table ----------------------------------------------
    rows: list[tuple[str, str]] = []
    if offer.position or (job and job.title):
        rows.append(("Position", offer.position or job.title))
    if job and job.department:
        rows.append(("Department", job.department))
    if offer.work_location:
        rows.append(("Work location", offer.work_location))
    elif job and job.location:
        rows.append(("Work location", job.location))
    if offer.reporting_manager:
        rows.append(("Reporting manager", offer.reporting_manager))
    if offer.joining_date:
        rows.append(("Expected joining date", _format_date(offer.joining_date)))
    if offer.salary_offered is not None:
        rows.append(("Monthly basic salary", _money(offer.salary_offered)))
    if offer.allowances:
        rows.append(("Allowances", offer.allowances))
    if offer.probation_period:
        rows.append(("Probation period", offer.probation_period))

    if rows:
        table = Table(
            [(Paragraph(f"<b>{k}</b>", small), Paragraph(str(v), small)) for k, v in rows],
            colWidths=[55 * mm, None],
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (0, -1),
                        colors.HexColor("#f8f5ec"),
                    ),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.HexColor("#e5e0cc"),
                    ),
                    (
                        "INNERGRID",
                        (0, 0),
                        (-1, -1),
                        0.25,
                        colors.HexColor("#e5e0cc"),
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 5 * mm))

    # --- Benefits / notes -----------------------------------------------
    if offer.benefits_summary:
        story.append(Paragraph("<b>Benefits</b>", body))
        story.append(Paragraph(offer.benefits_summary, body))

    if offer.remarks:
        story.append(Paragraph("<b>Additional notes</b>", body))
        story.append(Paragraph(offer.remarks, body))

    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            "Your engagement is subject to the company's standard terms "
            "and conditions of employment, satisfactory reference checks, "
            "and verification of credentials. Detailed terms will be "
            "covered in the full employment contract issued on or before "
            "your joining date.",
            body,
        )
    )

    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            "Please confirm your acceptance by signing below and returning "
            "a copy to our HR office. We look forward to welcoming you to "
            f"{company_phrase}.",
            body,
        )
    )

    # --- Signature block ------------------------------------------------
    story.append(Spacer(1, 14 * mm))
    sig_table = Table(
        [
            [
                Paragraph("<b>For the Company</b>", small),
                Paragraph("<b>Accepted by</b>", small),
            ],
            [
                Paragraph("________________________", small),
                Paragraph("________________________", small),
            ],
            [
                Paragraph("Human Resources Department", small),
                Paragraph(candidate.full_name, small),
            ],
            [
                Paragraph(COMPANY_NAME, small),
                Paragraph("Date: ____ / ____ / ________", small),
            ],
        ],
        colWidths=[None, None],
        hAlign="LEFT",
    )
    sig_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(sig_table)

    doc.build(story)
    return buf.getvalue()


def offer_pdf_filename(offer: OfferTracking, candidate: Candidate) -> str:
    """Predictable filename for the Content-Disposition header."""
    safe_name = "_".join((candidate.full_name or "candidate").split()) or "candidate"
    ref = offer.offer_letter_number or f"offer-{offer.id}"
    return f"offer_letter_{safe_name}_{ref}.pdf"


__all__ = ["build_offer_letter_pdf", "offer_pdf_filename"]
