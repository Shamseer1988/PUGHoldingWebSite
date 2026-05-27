"""Scorecard template helpers (Feature F2).

Two small helpers shared between the template-CRUD endpoint and the
interview-feedback submission path:

* ``validate_template_dimensions`` checks that dimension keys are
  unique within a single template and that the weights sum to 100 —
  enforced at template-write time so a half-set-up rubric can't be
  saved.
* ``compute_weighted_total`` produces the cached
  ``InterviewFeedback.scorecard_total`` value, applying each
  dimension's weight to the submitted score on a 0..100 scale.
"""
from __future__ import annotations

from typing import Iterable, Mapping


class ScorecardError(ValueError):
    """Raised for any malformed template / submission."""


def validate_template_dimensions(dimensions: Iterable[dict]) -> None:
    """Refuse a template whose dimensions are duplicated or whose
    weights don't sum to exactly 100."""
    dims = list(dimensions)
    if not dims:
        raise ScorecardError("A template must have at least one dimension.")

    keys = [d["key"] for d in dims]
    if len(keys) != len(set(keys)):
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        raise ScorecardError(
            f"Duplicate dimension keys: {', '.join(dupes)}"
        )

    total_weight = sum(int(d["weight"]) for d in dims)
    if total_weight != 100:
        raise ScorecardError(
            f"Dimension weights must sum to 100 (got {total_weight})."
        )


def compute_weighted_total(
    template_dimensions: Iterable[dict],
    submitted_scores: Mapping[str, Mapping[str, int]],
) -> int:
    """Return a 0..100 weighted total across the submitted dimensions.

    Each dimension's contribution is ``(score / max_score) * weight``.
    Missing dimensions contribute 0 — encourage interviewers to fill
    in every row before submitting, but don't crash if they didn't.
    """
    total = 0.0
    for dim in template_dimensions:
        key = dim["key"]
        max_score = max(1, int(dim.get("max_score", 5)))
        weight = int(dim.get("weight", 0))
        entry = submitted_scores.get(key)
        if not entry:
            continue
        score = int(entry.get("score", 0))
        # Clamp to the dimension's max_score range so a malformed
        # submission (e.g. score=15 on a max=5 dimension) can't inflate.
        score = max(0, min(score, max_score))
        total += (score / max_score) * weight
    return round(total)


__all__ = [
    "ScorecardError",
    "compute_weighted_total",
    "validate_template_dimensions",
]
