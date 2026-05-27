"""Semantic candidate search (Feature F5).

Builds an embedding-based "find candidates like this query" lookup on
top of the existing CV-parsed structured data. Two layers:

1. ``compute_query_embedding(text)`` — calls Azure OpenAI's embeddings
   endpoint and returns a list[float], or None if AI is disabled /
   misconfigured / the call fails. Keeping this layer separate makes
   the service mockable from tests.

2. ``semantic_search_candidates(db, query, limit)`` — embeds the query,
   pulls every candidate that has a stored embedding, computes cosine
   similarity in Python, and returns the top-K ranked rows.

Storage: each candidate's embedding lives in
``hr_candidate_extracted_data.embedding`` as a JSON list of floats.
That works on every DB the app already supports (SQLite for tests,
Postgres for prod) at the cost of doing the similarity scan in
Python. For thousand-scale candidate pools this is fast enough
(<100ms); a pgvector column + ANN index is the natural upgrade
when the pool grows past tens of thousands.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.hr_ats import Candidate, CandidateExtractedData


logger = logging.getLogger(__name__)


# The default Azure deployment name to use for embeddings. Operators
# can override via the AZURE_OPENAI_EMBEDDING_DEPLOYMENT env var; the
# fallback is the OpenAI-canonical name for the small, cheap model.
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


class SemanticSearchError(Exception):
    """Raised when embedding generation fails for a reason callers
    should surface (e.g. AI not configured, provider error)."""


# ---------------------------------------------------------------------------
# Profile text
# ---------------------------------------------------------------------------


def build_candidate_profile_text(
    candidate: Candidate, extracted: Optional[CandidateExtractedData]
) -> str:
    """Assemble the free-text blob we feed into the embedding model.

    Order matters: putting the most signal-dense fields first makes
    short embeddings (the default is 1536 dims, sufficient even when
    the input is truncated). We include:

      * Current designation + company + total experience
      * Extracted skills (parsed CV)
      * Education + certifications + languages
      * The first ~4 KB of full_text (CV plain text)
    """
    parts: list[str] = []

    # --- Headline identity ---
    head_bits = [candidate.current_designation, candidate.current_company]
    head = " at ".join(b for b in head_bits if b)
    if head:
        parts.append(head)
    if candidate.total_experience_years is not None:
        parts.append(f"{candidate.total_experience_years} years of experience")
    if candidate.current_location:
        parts.append(f"Location: {candidate.current_location}")
    if candidate.nationality:
        parts.append(f"Nationality: {candidate.nationality}")

    # --- Structured CV data ---
    if extracted is not None:
        if extracted.skills:
            parts.append(f"Skills: {extracted.skills}")
        if isinstance(extracted.education, list) and extracted.education:
            edu_lines = []
            for item in extracted.education:
                if isinstance(item, dict):
                    bits = [
                        str(item.get("degree") or ""),
                        str(item.get("institution") or ""),
                        str(item.get("raw") or ""),
                    ]
                    edu_lines.append(" ".join(b for b in bits if b))
                else:
                    edu_lines.append(str(item))
            parts.append("Education: " + "; ".join(edu_lines))
        if extracted.certifications:
            parts.append(f"Certifications: {extracted.certifications}")
        if extracted.languages:
            parts.append(f"Languages: {extracted.languages}")
        if extracted.previous_companies:
            parts.append(f"Past companies: {extracted.previous_companies}")
        if extracted.full_text:
            parts.append(extracted.full_text[:4000])

    # 8000 chars is well under the embedding API's input cap (~8k
    # tokens) and keeps the request small.
    return "\n".join(parts).strip()[:8000]


# ---------------------------------------------------------------------------
# Provider integration
# ---------------------------------------------------------------------------


def _ai_configured() -> bool:
    settings = get_settings()
    return bool(
        settings.ai_enabled
        and settings.azure_openai_endpoint
        and settings.azure_openai_api_key
    )


def compute_query_embedding(text: str) -> Optional[list[float]]:
    """Embed ``text`` via Azure OpenAI. Returns None if AI is not
    configured; raises :class:`SemanticSearchError` on provider error.

    Mocked from tests — patch this function rather than the OpenAI
    client. ``import openai`` is lazy so the module imports cleanly
    in environments where the SDK isn't installed.
    """
    if not _ai_configured():
        return None
    if not text.strip():
        return None

    import os

    settings = get_settings()
    deployment = (
        os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        or settings.azure_openai_deployment
        or DEFAULT_EMBEDDING_MODEL
    )
    try:
        from openai import AzureOpenAI  # lazy import
    except ImportError as exc:
        raise SemanticSearchError(
            "openai package is not installed."
        ) from exc

    client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint,
        timeout=30,
    )
    try:
        resp = client.embeddings.create(input=text, model=deployment)
    except Exception as exc:  # noqa: BLE001 — surface as a clean error
        raise SemanticSearchError(
            f"Embedding provider call failed: {exc}"
        ) from exc

    if not resp.data:
        raise SemanticSearchError("Embedding provider returned no data.")
    return list(resp.data[0].embedding)


# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------


def cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    """Standard cosine. Returns 0.0 when either vector is zero or
    the dimensions disagree (defensive — a stale vector from a model
    upgrade shouldn't crash the search)."""
    a_list = list(a)
    b_list = list(b)
    if not a_list or not b_list or len(a_list) != len(b_list):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a_list, b_list):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


# ---------------------------------------------------------------------------
# Search + backfill
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SemanticHit:
    candidate_id: int
    score: float


def semantic_search_candidates(
    db: Session,
    query: str,
    *,
    limit: int = 25,
    min_score: float = 0.0,
) -> list[SemanticHit]:
    """Return the top-``limit`` candidates ranked by similarity to
    ``query``. Raises :class:`SemanticSearchError` if the query
    embedding can't be produced; returns ``[]`` if there are simply
    no embedded candidates yet.
    """
    query_vec = compute_query_embedding(query)
    if query_vec is None:
        raise SemanticSearchError(
            "AI is not enabled — semantic search is unavailable. "
            "Configure Azure OpenAI in /admin/ai-settings to use it."
        )

    rows = db.execute(
        select(
            CandidateExtractedData.candidate_id,
            CandidateExtractedData.embedding,
        ).where(CandidateExtractedData.embedding.is_not(None))
    ).all()
    if not rows:
        return []

    hits: list[SemanticHit] = []
    for candidate_id, embedding in rows:
        if not embedding:
            continue
        score = cosine_similarity(query_vec, embedding)
        if score < min_score:
            continue
        hits.append(SemanticHit(candidate_id=candidate_id, score=score))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[: max(1, limit)]


def refresh_candidate_embedding(
    db: Session, candidate: Candidate
) -> Optional[CandidateExtractedData]:
    """Compute and persist a fresh embedding for ``candidate``.

    Returns the updated CandidateExtractedData row (or None if the
    candidate has no extracted-data row yet). Caller commits.
    """
    extracted = candidate.extracted_data
    if extracted is None:
        return None
    text = build_candidate_profile_text(candidate, extracted)
    if not text:
        return extracted
    try:
        vec = compute_query_embedding(text)
    except SemanticSearchError as exc:
        logger.warning(
            "Embedding refresh failed for candidate %s: %s",
            candidate.id,
            exc,
        )
        return extracted
    if vec is None:
        return extracted

    extracted.embedding = vec
    extracted.embedding_model = DEFAULT_EMBEDDING_MODEL
    extracted.embedding_updated_at = datetime.now(timezone.utc)
    return extracted


def backfill_candidate_embeddings(
    db: Session, *, limit: int = 50
) -> dict:
    """Embed up to ``limit`` candidates that don't yet have a vector.

    Designed to be called from an admin "Rebuild semantic search
    index" button. Single-batch — call repeatedly to chew through a
    large backlog so one HTTP request doesn't time out.
    """
    rows = db.execute(
        select(CandidateExtractedData)
        .where(CandidateExtractedData.embedding.is_(None))
        .limit(limit)
    ).scalars().all()

    refreshed = 0
    skipped = 0
    for extracted in rows:
        candidate = extracted.candidate
        text = build_candidate_profile_text(candidate, extracted)
        if not text:
            skipped += 1
            continue
        try:
            vec = compute_query_embedding(text)
        except SemanticSearchError:
            skipped += 1
            continue
        if vec is None:
            skipped += 1
            continue
        extracted.embedding = vec
        extracted.embedding_model = DEFAULT_EMBEDDING_MODEL
        extracted.embedding_updated_at = datetime.now(timezone.utc)
        refreshed += 1
    db.commit()
    return {
        "refreshed": refreshed,
        "skipped": skipped,
        "remaining_to_visit": (
            db.execute(
                select(CandidateExtractedData.id).where(
                    CandidateExtractedData.embedding.is_(None)
                )
            )
            .scalars()
            .all()
        ),
    }


__all__ = [
    "DEFAULT_EMBEDDING_MODEL",
    "SemanticHit",
    "SemanticSearchError",
    "backfill_candidate_embeddings",
    "build_candidate_profile_text",
    "compute_query_embedding",
    "cosine_similarity",
    "refresh_candidate_embedding",
    "semantic_search_candidates",
]
