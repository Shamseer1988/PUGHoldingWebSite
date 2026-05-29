"""Phase C-4 — candidate full-text search.

Two contracts to lock in:

1. **Behavioural**: searching by a term that lives ONLY in the CV
   body (``CandidateExtractedData.full_text``) returns the
   candidate on either dialect. The test suite runs SQLite which
   takes the ``ILIKE``-on-``full_text`` fallback — same observable
   match, slower under the hood. Production Postgres takes the
   indexed ``tsvector @@`` path; we verify the SQL routing below.

2. **Dialect routing**: the search builder emits Postgres FTS
   primitives (``to_tsvector`` / ``websearch_to_tsquery`` /
   ``@@``) when bound to a Postgres dialect and falls back to
   ``ILIKE`` on SQLite. We compile the statement against each
   dialect explicitly to prove the branching.

3. **Backwards compat**: candidates without an extracted-data row
   still match by name / email / mobile the way they always did —
   the new code path widens the match, never narrows it.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    Candidate,
    CandidateExtractedData,
    CandidateJobApplication,
    JobOpening,
    STATUS_CV_RECEIVED,
)
from app.services.candidate_search import (
    CandidateFilters,
    _apply_keyword_filter,
    _is_postgres,
    search_candidates,
)


# ---------------------------------------------------------------------------
# Dialect detection helper
# ---------------------------------------------------------------------------


def test_is_postgres_true_for_postgres_engine():
    engine = create_engine("postgresql+psycopg2://x@y/z")
    with Session(engine) as session:
        assert _is_postgres(session) is True


def test_is_postgres_false_for_sqlite(db_session):
    assert _is_postgres(db_session) is False


# ---------------------------------------------------------------------------
# Dialect-aware SQL emission
# ---------------------------------------------------------------------------


def test_keyword_filter_emits_websearch_tsquery_on_postgres():
    """Compile the statement against the Postgres dialect and confirm
    the FTS primitives show up in the rendered SQL."""
    engine = create_engine("postgresql+psycopg2://x@y/z")
    with Session(engine) as session:
        from sqlalchemy import select

        stmt = select(Candidate)
        stmt = _apply_keyword_filter(stmt, session, "rabbitmq")
        compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "websearch_to_tsquery" in compiled
    assert "to_tsvector" in compiled
    assert "@@" in compiled


def test_keyword_filter_falls_back_to_ilike_on_sqlite(db_session):
    """SQLite path: the ``full_text`` column appears inside a
    ``LIKE`` subquery, no FTS primitives at all."""
    from sqlalchemy import select

    stmt = select(Candidate)
    stmt = _apply_keyword_filter(stmt, db_session, "rabbitmq")
    compiled = str(stmt.compile(dialect=sqlite.dialect()))

    assert "websearch_to_tsquery" not in compiled
    assert "to_tsvector" not in compiled
    assert "full_text" in compiled
    assert "like" in compiled.lower()


# ---------------------------------------------------------------------------
# End-to-end behaviour on the test SQLite engine
# ---------------------------------------------------------------------------


def _seed_candidate_with_cv(
    db: Session, *, name: str, email: str, cv_text: str
) -> Candidate:
    candidate = Candidate(full_name=name, email=email, mobile="999")
    db.add(candidate)
    db.flush()
    extracted = CandidateExtractedData(
        candidate_id=candidate.id, full_text=cv_text
    )
    db.add(extracted)
    db.flush()
    return candidate


def test_search_finds_candidate_when_term_only_lives_in_cv_body(db_session):
    """The whole point of FTS: ``q="rabbitmq"`` must hit a candidate
    whose CV body contains it even though name + email don't."""
    _seed_candidate_with_cv(
        db_session,
        name="Ada Lovelace",
        email="ada@example.com",
        cv_text="Experienced backend engineer, deep RabbitMQ + Celery work.",
    )
    decoy = Candidate(
        full_name="Bob Smith", email="bob@example.com", mobile="123"
    )
    db_session.add(decoy)
    db_session.flush()

    results = search_candidates(db_session, CandidateFilters(q="rabbitmq"))
    found = {r.candidate.email for r in results}
    assert "ada@example.com" in found
    assert "bob@example.com" not in found


def test_search_still_matches_name_email_mobile(db_session):
    """Behavioural backwards-compat: candidates with no extracted
    text must still be findable by name / email / mobile."""
    candidate = Candidate(
        full_name="Grace Hopper",
        email="grace@example.com",
        mobile="55512345",
    )
    db_session.add(candidate)
    db_session.flush()

    by_name = search_candidates(db_session, CandidateFilters(q="grace"))
    by_email = search_candidates(db_session, CandidateFilters(q="example.com"))
    by_mobile = search_candidates(db_session, CandidateFilters(q="55512345"))

    for results in (by_name, by_email, by_mobile):
        assert any(r.candidate.id == candidate.id for r in results)


def test_search_with_no_q_returns_all_active_candidates(db_session):
    """The ``q`` filter is opt-in — no filter, no narrowing."""
    a = Candidate(full_name="One", email="one@x.com", mobile="1")
    b = Candidate(full_name="Two", email="two@x.com", mobile="2")
    db_session.add_all([a, b])
    db_session.flush()

    results = search_candidates(db_session, CandidateFilters())
    emails = {r.candidate.email for r in results}
    assert {"one@x.com", "two@x.com"}.issubset(emails)


def test_search_excludes_candidates_with_only_irrelevant_cv_text(db_session):
    """Reverse of the FTS test: a candidate whose CV mentions
    ``python`` must NOT come back for ``q="rabbitmq"``."""
    _seed_candidate_with_cv(
        db_session,
        name="Python Person",
        email="py@example.com",
        cv_text="Python, Django, Flask, FastAPI.",
    )
    results = search_candidates(db_session, CandidateFilters(q="rabbitmq"))
    assert all(r.candidate.email != "py@example.com" for r in results)


def test_search_handles_empty_cv_body_without_crashing(db_session):
    """A candidate row with a NULL ``full_text`` must not break the
    search — ``coalesce`` on both branches keeps the SQL valid."""
    candidate = Candidate(
        full_name="No CV", email="nocv@example.com", mobile="0"
    )
    db_session.add(candidate)
    db_session.flush()
    db_session.add(
        CandidateExtractedData(candidate_id=candidate.id, full_text=None)
    )
    db_session.flush()

    # Just calling it without an exception is the assertion.
    results = search_candidates(db_session, CandidateFilters(q="anything"))
    assert all(r.candidate.email != "nocv@example.com" for r in results)


# ---------------------------------------------------------------------------
# HR endpoint smoke — the candidate list route reads ``q`` from the
# query string and feeds it through the same search helper.
# ---------------------------------------------------------------------------


def test_hr_candidates_endpoint_accepts_q_against_cv_body(
    client, seed_auth, db_session: Session
):
    """End-to-end via the HR list endpoint, confirming the FTS-wired
    search is exercised through the API surface HR actually uses."""
    job = JobOpening(
        slug="c4-job",
        title="Backend Eng",
        department="Eng",
        company="PUG",
        location="Doha",
    )
    db_session.add(job)
    db_session.flush()

    _seed_candidate_with_cv(
        db_session,
        name="Match Me",
        email="match@example.com",
        cv_text="Years of Kubernetes + Helm + ArgoCD experience.",
    )
    decoy = Candidate(
        full_name="Decoy", email="decoy@example.com", mobile="1"
    )
    db_session.add(decoy)
    db_session.flush()
    db_session.add(
        CandidateJobApplication(
            candidate_id=decoy.id,
            job_opening_id=job.id,
            status=STATUS_CV_RECEIVED,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/hr/auth/login",
        json={
            "email": "hr@pug.example.com",
            "password": seed_auth["password"],
        },
    )
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    listing = client.get(
        "/api/v1/hr/candidates?q=kubernetes", headers=headers
    )
    assert listing.status_code == 200, listing.text
    # The endpoint returns a plain list (``List[CandidateListItem]``).
    body = listing.json()
    emails = {item["email"] for item in body}
    assert "match@example.com" in emails
    assert "decoy@example.com" not in emails
