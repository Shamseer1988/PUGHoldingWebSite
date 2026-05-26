"""Integration tests for the public job-opening endpoints (Phase 9)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.hr_ats import (
    APPROVAL_STATUS_APPROVED,
    JOB_STATUS_CLOSED,
    JOB_STATUS_OPEN,
    JobOpening,
    PUBLISH_STATUS_PUBLISHED,
)


JOBS = "/api/v1/public/jobs"


# Public listings now require approval_status='approved' AND
# publish_status='published'. The legacy fixture seeded only ``status``;
# the advanced HR module adds the approval workflow so we stamp both
# fields on the "open" jobs to mirror what the migration back-fills for
# pre-existing rows in production.
PUBLISHED = {
    "approval_status": APPROVAL_STATUS_APPROVED,
    "publish_status": PUBLISH_STATUS_PUBLISHED,
}


def _seed_jobs(db_session: Session) -> None:
    db_session.add_all(
        [
            JobOpening(
                slug="open-a",
                title="Open A",
                department="Engineering",
                company="Paris United Group Holding",
                location="Doha",
                status=JOB_STATUS_OPEN,
                employment_type="full_time",
                required_skills="Python, FastAPI",
                **PUBLISHED,
            ),
            JobOpening(
                slug="open-b",
                title="Open B",
                department="Sales",
                company="Paris Food International",
                location="Doha",
                status=JOB_STATUS_OPEN,
                employment_type="part_time",
                required_skills="FMCG, Sales",
                **PUBLISHED,
            ),
            JobOpening(
                slug="closed-c",
                title="Closed C",
                department="Engineering",
                company="Paris United Group Holding",
                location="Doha",
                status=JOB_STATUS_CLOSED,
                employment_type="full_time",
                **PUBLISHED,
            ),
        ]
    )
    db_session.commit()


def test_public_jobs_returns_only_open(client, db_session: Session):
    _seed_jobs(db_session)

    response = client.get(JOBS)
    assert response.status_code == 200
    slugs = {j["slug"] for j in response.json()}
    assert slugs == {"open-a", "open-b"}


def test_public_jobs_filters(client, db_session: Session):
    _seed_jobs(db_session)

    by_dept = client.get(f"{JOBS}?department=Sales").json()
    assert [j["slug"] for j in by_dept] == ["open-b"]

    by_type = client.get(f"{JOBS}?employment_type=part_time").json()
    assert [j["slug"] for j in by_type] == ["open-b"]

    by_search = client.get(f"{JOBS}?q=fastapi").json()
    assert [j["slug"] for j in by_search] == ["open-a"]


def test_public_job_detail_only_returns_open(client, db_session: Session):
    _seed_jobs(db_session)

    open_resp = client.get(f"{JOBS}/open-a")
    assert open_resp.status_code == 200
    assert open_resp.json()["title"] == "Open A"

    closed_resp = client.get(f"{JOBS}/closed-c")
    assert closed_resp.status_code == 404

    missing_resp = client.get(f"{JOBS}/nope")
    assert missing_resp.status_code == 404
