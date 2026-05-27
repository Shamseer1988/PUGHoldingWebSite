"""Semantic candidate search (Feature F5)."""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.models.hr_ats import Candidate, CandidateExtractedData
from app.services import semantic_search as ss


HR_LOGIN = "/api/v1/hr/auth/login"
BASE = "/api/v1/hr/candidates/semantic-search"


def _login(client: TestClient, email: str, password: str) -> dict:
    r = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Pure math
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self):
        v = [1.0, 2.0, 3.0]
        assert ss.cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_zero(self):
        assert ss.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors_score_minus_one(self):
        assert ss.cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_zero_vector_yields_zero(self):
        assert ss.cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_mismatched_lengths_yield_zero(self):
        # Stale vectors from a model upgrade shouldn't crash search.
        assert ss.cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0


# ---------------------------------------------------------------------------
# Profile text builder
# ---------------------------------------------------------------------------


class TestProfileText:
    def test_assembles_headline_and_skills(self, db_session):
        cand = Candidate(
            full_name="Embed Me",
            current_designation="Senior Backend Engineer",
            current_company="Acme",
            total_experience_years=8,
            current_location="Doha, Qatar",
        )
        db_session.add(cand)
        db_session.flush()
        extracted = CandidateExtractedData(
            candidate_id=cand.id,
            skills="python, fastapi, aws, kubernetes",
            full_text="Worked on payment systems serving 1M users/day.",
        )
        db_session.add(extracted)
        db_session.commit()

        text = ss.build_candidate_profile_text(cand, extracted)
        assert "Senior Backend Engineer" in text
        assert "Acme" in text
        assert "8 years" in text
        assert "python" in text
        assert "Doha" in text

    def test_handles_no_extracted_data(self, db_session):
        cand = Candidate(full_name="No CV Yet")
        db_session.add(cand)
        db_session.commit()
        text = ss.build_candidate_profile_text(cand, None)
        # Doesn't crash; can be empty string or minimal.
        assert isinstance(text, str)

    def test_clips_oversized_full_text(self, db_session):
        cand = Candidate(full_name="Talky", current_designation="Verbose Dev")
        db_session.add(cand)
        db_session.flush()
        extracted = CandidateExtractedData(
            candidate_id=cand.id,
            full_text="X" * 50000,  # 50 KB CV body
        )
        db_session.add(extracted)
        db_session.commit()
        text = ss.build_candidate_profile_text(cand, extracted)
        assert len(text) <= 8000


# ---------------------------------------------------------------------------
# compute_query_embedding (with no AI configured)
# ---------------------------------------------------------------------------


class TestQueryEmbeddingNoAi:
    def test_returns_none_when_ai_disabled(self):
        # In the test env, ai_enabled is False -> no embedding.
        assert ss.compute_query_embedding("Hello world") is None


# ---------------------------------------------------------------------------
# semantic_search_candidates (with mocked embedding fn)
# ---------------------------------------------------------------------------


def _mk_candidate_with_embedding(db_session, name: str, vec: list[float]) -> int:
    cand = Candidate(full_name=name)
    db_session.add(cand)
    db_session.flush()
    db_session.add(
        CandidateExtractedData(
            candidate_id=cand.id,
            skills="test skills",
            embedding=vec,
            embedding_model="test-model",
        )
    )
    db_session.commit()
    return cand.id


class TestSemanticSearchCandidates:
    def test_raises_when_ai_unavailable(self, db_session):
        with pytest.raises(ss.SemanticSearchError):
            ss.semantic_search_candidates(db_session, "any query")

    def test_returns_ranked_hits_with_mocked_embedding(
        self, db_session, monkeypatch
    ):
        # Seed three candidates with deliberately different vectors:
        # closest, middle, far. The query is [1, 0, 0].
        close_id = _mk_candidate_with_embedding(db_session, "Closest", [1.0, 0.0, 0.0])
        mid_id = _mk_candidate_with_embedding(db_session, "Middle", [0.7, 0.7, 0.0])
        far_id = _mk_candidate_with_embedding(db_session, "Far", [0.0, 0.0, 1.0])
        # And one with no embedding — should be skipped.
        no_embed = Candidate(full_name="No Embed")
        db_session.add(no_embed)
        db_session.flush()
        db_session.add(
            CandidateExtractedData(candidate_id=no_embed.id, skills="x")
        )
        db_session.commit()

        monkeypatch.setattr(
            ss, "compute_query_embedding", lambda q: [1.0, 0.0, 0.0]
        )
        hits = ss.semantic_search_candidates(db_session, "find me X")
        ids = [h.candidate_id for h in hits]
        # Closest first, then middle, then far. No-embed not present.
        assert ids[0] == close_id
        assert ids[1] == mid_id
        assert ids[2] == far_id
        assert no_embed.id not in ids
        # And the scores are descending.
        assert hits[0].score > hits[1].score > hits[2].score

    def test_min_score_filters_low_matches(self, db_session, monkeypatch):
        _mk_candidate_with_embedding(db_session, "High", [1.0, 0.0])
        _mk_candidate_with_embedding(db_session, "Low", [0.1, 0.99])
        monkeypatch.setattr(
            ss, "compute_query_embedding", lambda q: [1.0, 0.0]
        )
        hits = ss.semantic_search_candidates(
            db_session, "x", min_score=0.5
        )
        assert len(hits) == 1
        assert hits[0].score >= 0.5

    def test_limit_caps_result_count(self, db_session, monkeypatch):
        for i in range(10):
            _mk_candidate_with_embedding(
                db_session, f"Cand-{i}", [1.0, float(i) / 10]
            )
        monkeypatch.setattr(
            ss, "compute_query_embedding", lambda q: [1.0, 0.0]
        )
        hits = ss.semantic_search_candidates(db_session, "x", limit=3)
        assert len(hits) == 3


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestEndpoint:
    def test_anon_is_401(self, client: TestClient):
        r = client.post(BASE, json={"query": "python developer"})
        assert r.status_code == 401

    def test_503_when_ai_not_configured(
        self, client: TestClient, seed_auth
    ):
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        r = client.post(
            BASE, headers=headers, json={"query": "python developer"}
        )
        assert r.status_code == 503
        assert "AI" in r.json()["detail"]

    def test_endpoint_returns_ranked_results_with_mocked_embedding(
        self, client: TestClient, seed_auth, db_session, monkeypatch
    ):
        # Patch the embedding fn so the endpoint runs without a real
        # provider connection.
        from app.services import semantic_search as ss

        cand_id = _mk_candidate_with_embedding(
            db_session, "Embedded Candidate", [1.0, 0.0]
        )
        monkeypatch.setattr(
            ss, "compute_query_embedding", lambda q: [1.0, 0.0]
        )

        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        r = client.post(
            BASE,
            headers=headers,
            json={"query": "test query", "limit": 5},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["hit_count"] >= 1
        assert body["hits"][0]["candidate_id"] == cand_id
        # Score normalized to 4 decimal places — should be close to 1.
        assert body["hits"][0]["score"] >= 0.99

    def test_short_query_is_422(self, client: TestClient, seed_auth):
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        r = client.post(BASE, headers=headers, json={"query": "x"})
        assert r.status_code == 422
