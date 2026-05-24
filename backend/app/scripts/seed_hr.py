"""Seed the HR ATS tables with the same dummy job openings the public
careers page shows in Phase 4 (still on dummy data through Phase 8).
Phase 9 will wire the public site to read from this table.

Run from /backend with the venv active and migrations applied:

    python -m app.scripts.seed_hr

The script is idempotent: rerunning it refreshes existing jobs by slug
rather than duplicating data.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.hr_ats import EMPLOYMENT_FULL_TIME, JOB_STATUS_OPEN, JobOpening


JOBS = [
    {
        "slug": "store-manager-paris-hyper-lusail",
        "title": "Store Manager",
        "department": "Retail Operations",
        "division": "Retail",
        "company": "Paris Hyper Market",
        "location": "Lusail, Qatar",
        "employment_type": EMPLOYMENT_FULL_TIME,
        "min_experience": 6,
        "max_experience": 10,
        "required_education": "Bachelor's degree (business / retail preferred)",
        "salary_min": 18000,
        "salary_max": 25000,
        "visa_requirement": "Transferable / new visa",
        "language_requirement": "English; Arabic is a plus",
        "notice_period_preference": "1 month or less",
        "description": (
            "Lead the day-to-day operations of a new flagship hypermarket. "
            "You will own customer experience, sales performance, P&L, "
            "inventory accuracy, and a team of 80+."
        ),
        "responsibilities": (
            "Own daily store operations and KPIs\n"
            "Lead, coach, and develop department managers\n"
            "Drive sales, margin, and customer satisfaction\n"
            "Manage inventory, shrinkage, and supplier relationships\n"
            "Ensure compliance with health & safety and brand standards"
        ),
        "requirements": (
            "6+ years in retail with at least 2 years as Store Manager\n"
            "Strong P&L, planning, and people leadership skills\n"
            "GCC retail experience preferred"
        ),
        "required_skills": "Retail operations, Team management, P&L, Inventory",
        "preferred_skills": "Hypermarket experience, Arabic language",
        "posted_at": datetime(2026, 5, 10, tzinfo=timezone.utc),
    },
    {
        "slug": "fmcg-sales-executive",
        "title": "FMCG Sales Executive",
        "department": "Sales",
        "division": "Distribution",
        "company": "Paris Food International",
        "location": "Doha, Qatar",
        "employment_type": EMPLOYMENT_FULL_TIME,
        "min_experience": 2,
        "max_experience": 5,
        "required_education": "Bachelor's degree",
        "salary_min": 7000,
        "salary_max": 11000,
        "description": (
            "Develop and grow assigned FMCG accounts across department "
            "stores and HORECA. Manage promotions, in-store activations, "
            "and weekly sell-out reporting."
        ),
        "responsibilities": (
            "Manage assigned key accounts\n"
            "Negotiate annual contracts and promotions\n"
            "Drive in-store activations and brand visibility\n"
            "Maintain accurate weekly sell-out reporting"
        ),
        "requirements": (
            "2-5 years FMCG field sales experience\n"
            "GCC market exposure preferred\n"
            "Valid Qatar driving licence is a plus"
        ),
        "required_skills": "FMCG sales, Key accounts, Negotiation, Reporting",
        "posted_at": datetime(2026, 5, 5, tzinfo=timezone.utc),
    },
    {
        "slug": "warehouse-supervisor",
        "title": "Warehouse Supervisor",
        "department": "Supply Chain",
        "division": "Distribution",
        "company": "Paris Food International",
        "location": "Industrial Area, Doha",
        "employment_type": EMPLOYMENT_FULL_TIME,
        "min_experience": 3,
        "max_experience": 7,
        "description": (
            "Supervise a temperature-controlled distribution warehouse, "
            "ensuring SLAs for inbound, putaway, picking, and outbound "
            "operations."
        ),
        "responsibilities": (
            "Supervise warehouse shifts and operations\n"
            "Maintain WMS data accuracy and stock counts\n"
            "Coordinate inbound and outbound fleets\n"
            "Enforce safety and food handling standards"
        ),
        "requirements": (
            "3+ years warehouse / DC supervision experience\n"
            "WMS familiarity (SAP / Oracle / equivalent)\n"
            "Cold-chain experience preferred"
        ),
        "required_skills": "Warehouse ops, WMS, Cold chain, Team supervision",
        "posted_at": datetime(2026, 4, 30, tzinfo=timezone.utc),
    },
    {
        "slug": "ev-technician",
        "title": "EV Technician",
        "department": "Vehicle Service",
        "division": "Services",
        "company": "YellowTech Garage",
        "location": "Doha, Qatar",
        "employment_type": EMPLOYMENT_FULL_TIME,
        "min_experience": 3,
        "max_experience": 8,
        "description": (
            "Service and repair electric vehicles in our newly opened EV "
            "bays. OEM certification training will be provided."
        ),
        "responsibilities": (
            "Diagnose and repair EV systems\n"
            "Follow high-voltage safety protocols\n"
            "Document service jobs and update WIP\n"
            "Mentor junior technicians"
        ),
        "requirements": (
            "3+ years vehicle technician experience\n"
            "Existing EV or hybrid experience preferred\n"
            "Strong attention to safety"
        ),
        "required_skills": "EV diagnostics, High-voltage safety, OEM tools",
        "preferred_skills": "BEV certification, Multi-brand experience",
        "posted_at": datetime(2026, 4, 22, tzinfo=timezone.utc),
    },
    {
        "slug": "real-estate-broker",
        "title": "Senior Real Estate Broker",
        "department": "Real Estate",
        "division": "Services",
        "company": "Greentech Real Estate Broker",
        "location": "Doha, Qatar",
        "employment_type": EMPLOYMENT_FULL_TIME,
        "min_experience": 4,
        "max_experience": 9,
        "description": (
            "Advise clients on residential and commercial property in "
            "Qatar. Build a strong pipeline of buyers, sellers, and "
            "tenants through proactive outreach and referrals."
        ),
        "responsibilities": (
            "Source and qualify leads\n"
            "Conduct viewings and negotiate offers\n"
            "Maintain CRM hygiene and pipeline reporting\n"
            "Build long-term client relationships"
        ),
        "requirements": (
            "4+ years brokerage experience\n"
            "Strong Qatar market knowledge\n"
            "Valid driving licence"
        ),
        "required_skills": "Sales, Negotiation, Qatar market, CRM",
        "posted_at": datetime(2026, 4, 18, tzinfo=timezone.utc),
    },
    {
        "slug": "civil-engineer",
        "title": "Civil Engineer",
        "department": "Engineering",
        "division": "Services",
        "company": "Core Engineering and Construction",
        "location": "Doha, Qatar",
        "employment_type": EMPLOYMENT_FULL_TIME,
        "min_experience": 5,
        "max_experience": 12,
        "required_education": "B.Sc. Civil Engineering",
        "description": (
            "Lead site execution for commercial fit-out projects. "
            "Coordinate MEP subcontractors, supervise quality, and "
            "report progress against schedule."
        ),
        "responsibilities": (
            "Lead project execution on site\n"
            "Coordinate subcontractors and consultants\n"
            "Track progress, quality, and safety\n"
            "Prepare BOQs and progress reports"
        ),
        "requirements": (
            "B.Sc. Civil Engineering\n"
            "5+ years project execution experience\n"
            "GCC fit-out experience preferred"
        ),
        "required_skills": "Project management, BOQ, MEP coordination",
        "posted_at": datetime(2026, 4, 12, tzinfo=timezone.utc),
    },
    {
        "slug": "cashier-paris-express",
        "title": "Cashier",
        "department": "Retail Operations",
        "division": "Retail",
        "company": "Paris Express",
        "location": "Doha, Qatar",
        "employment_type": EMPLOYMENT_FULL_TIME,
        "min_experience": 1,
        "max_experience": 3,
        "description": (
            "Provide fast, friendly service at the till and maintain "
            "accurate cash handling."
        ),
        "responsibilities": (
            "Operate POS and process transactions\n"
            "Provide warm customer service\n"
            "Maintain till accuracy and shift reports"
        ),
        "requirements": (
            "1-3 years cashier experience\n"
            "Good spoken English; Arabic is a plus"
        ),
        "required_skills": "POS, Customer service, Cash handling",
        "posted_at": datetime(2026, 4, 5, tzinfo=timezone.utc),
    },
    {
        "slug": "hr-business-partner",
        "title": "HR Business Partner",
        "department": "Human Resources",
        "division": "Corporate",
        "company": "Paris United Group Holding",
        "location": "Doha, Qatar",
        "employment_type": EMPLOYMENT_FULL_TIME,
        "min_experience": 5,
        "max_experience": 10,
        "description": (
            "Partner with division leaders across retail and distribution "
            "to drive workforce planning, employee engagement, and talent "
            "development."
        ),
        "responsibilities": (
            "Act as trusted HR partner to senior leaders\n"
            "Lead workforce planning and engagement\n"
            "Coach managers on performance and development"
        ),
        "requirements": (
            "5+ years HRBP experience in retail or FMCG\n"
            "Strong stakeholder management skills"
        ),
        "required_skills": "HRBP, Employee relations, Performance management",
        "posted_at": datetime(2026, 3, 28, tzinfo=timezone.utc),
    },
]


def _upsert_jobs(db: Session) -> int:
    existing = {j.slug: j for j in db.execute(select(JobOpening)).scalars()}
    for data in JOBS:
        slug = data["slug"]
        job = existing.get(slug)
        if job is None:
            job = JobOpening(status=JOB_STATUS_OPEN, **data)
            db.add(job)
        else:
            for k, v in data.items():
                setattr(job, k, v)
            job.status = JOB_STATUS_OPEN
    db.flush()
    return len(JOBS)


def seed(db: Session) -> None:
    count = _upsert_jobs(db)
    db.commit()

    print("HR seed complete.")
    print(f"  hr_job_openings : {count}")


def main(argv: Sequence[str] | None = None) -> int:
    db = SessionLocal()
    try:
        seed(db)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
