"""HR AI candidate review service (Phase 13).

Generates an *advisory* review for a candidate-application pair using
Azure OpenAI. The service has three modes:

- ``disabled`` — AI is off. Calls raise ``AIDisabledError`` so the UI
  can show a clear "AI is disabled" state.
- ``mock`` — returns a deterministic synthetic review based on the
  candidate's stored data. No network call. Perfect for dev / CI / a
  staging environment without Azure credentials.
- ``live`` — calls Azure OpenAI Chat Completions with a JSON schema
  prompt and parses the structured response.

Hard rules (enforced both in the prompt and the response normaliser):

- The AI **may not** select or reject a candidate.
- The AI only produces an advisory recommendation in the set
  ``{strong_fit, possible_fit, weak_fit, needs_more_info}``.
- Any other recommendation value (incl. ``select`` / ``reject``
  / ``hire`` / ``no_hire``) is rewritten to ``needs_more_info``.
- The final hiring decision is always made by an HR user.

The full provider response (`raw_response`) is persisted alongside the
parsed fields so HR can audit exactly what the model produced.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.models.hr_ats import (
    AI_MODE_DISABLED,
    AI_MODE_LIVE,
    AI_MODE_MOCK,
    AISetting,
    Candidate,
    CandidateAIReview,
    CandidateJobApplication,
    JobOpening,
)


logger = logging.getLogger(__name__)


RECOMMENDATION_STRONG_FIT = "strong_fit"
RECOMMENDATION_POSSIBLE_FIT = "possible_fit"
RECOMMENDATION_WEAK_FIT = "weak_fit"
RECOMMENDATION_NEEDS_MORE_INFO = "needs_more_info"
ALLOWED_RECOMMENDATIONS = {
    RECOMMENDATION_STRONG_FIT,
    RECOMMENDATION_POSSIBLE_FIT,
    RECOMMENDATION_WEAK_FIT,
    RECOMMENDATION_NEEDS_MORE_INFO,
}

# Aliases the model occasionally emits that we map back to safe values.
RECOMMENDATION_ALIASES = {
    "strong_match": RECOMMENDATION_STRONG_FIT,
    "good_fit": RECOMMENDATION_STRONG_FIT,
    "great_fit": RECOMMENDATION_STRONG_FIT,
    "maybe": RECOMMENDATION_POSSIBLE_FIT,
    "possible_match": RECOMMENDATION_POSSIBLE_FIT,
    "weak_match": RECOMMENDATION_WEAK_FIT,
    "poor_fit": RECOMMENDATION_WEAK_FIT,
    "unfit": RECOMMENDATION_WEAK_FIT,
    "not_enough_info": RECOMMENDATION_NEEDS_MORE_INFO,
    "missing_info": RECOMMENDATION_NEEDS_MORE_INFO,
}

# Recommendations the AI MUST NOT emit. If it does, we coerce to
# needs_more_info — the final decision stays with HR.
FORBIDDEN_RECOMMENDATIONS = {
    "select", "selected", "approve", "approved", "hire", "hired",
    "reject", "rejected", "no_hire", "do_not_hire", "blacklist",
}


# ---------------------------------------------------------------------------
# Exceptions + result classes
# ---------------------------------------------------------------------------


class AIError(Exception):
    """Base class for AI-review failures."""


class AIDisabledError(AIError):
    """Raised when AI mode is 'disabled'."""


class AIConfigError(AIError):
    """Raised when 'live' mode is selected but Azure is not configured."""


class AIProviderError(AIError):
    """Raised on transient / API failures from Azure."""


@dataclass(slots=True)
class AIReviewResult:
    summary: str
    strengths: str
    weaknesses: str
    missing_information: str
    risk_points: str
    suggested_questions: str
    recommendation: str
    model_name: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    raw_response: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ResolvedAIConfig:
    mode: str
    azure_endpoint: Optional[str]
    azure_deployment: Optional[str]
    azure_api_key: Optional[str]
    azure_api_version: Optional[str]
    model_name: Optional[str]
    temperature: float
    max_output_tokens: int
    request_timeout_seconds: int
    extra_system_prompt: Optional[str]


def resolve_config(setting: Optional[AISetting]) -> ResolvedAIConfig:
    """Merge the .env-supplied bootstrap config with the DB row.

    DB values win when present; .env is used as the fallback (and for
    secrets like the API key, which intentionally never live in the DB).
    """
    env = get_settings()
    if setting is None:
        # Fall back entirely to .env defaults.
        mode = AI_MODE_LIVE if env.ai_enabled else AI_MODE_DISABLED
        return ResolvedAIConfig(
            mode=mode,
            azure_endpoint=env.azure_openai_endpoint,
            azure_deployment=env.azure_openai_deployment,
            azure_api_key=env.azure_openai_api_key,
            azure_api_version=env.azure_openai_api_version,
            model_name=env.azure_openai_deployment,
            temperature=0.2,
            max_output_tokens=900,
            request_timeout_seconds=45,
            extra_system_prompt=None,
        )
    return ResolvedAIConfig(
        mode=setting.mode,
        azure_endpoint=setting.azure_endpoint or env.azure_openai_endpoint,
        azure_deployment=setting.azure_deployment or env.azure_openai_deployment,
        azure_api_key=env.azure_openai_api_key,
        azure_api_version=setting.azure_api_version or env.azure_openai_api_version,
        model_name=(
            setting.model_name
            or setting.azure_deployment
            or env.azure_openai_deployment
        ),
        temperature=setting.temperature,
        max_output_tokens=setting.max_output_tokens,
        request_timeout_seconds=setting.request_timeout_seconds,
        extra_system_prompt=setting.extra_system_prompt,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_review(
    *,
    candidate: Candidate,
    application: CandidateJobApplication,
    job: Optional[JobOpening],
    config: ResolvedAIConfig,
) -> AIReviewResult:
    """Generate an AI advisory review for this candidate / application."""
    if config.mode == AI_MODE_DISABLED:
        raise AIDisabledError(
            "AI candidate review is disabled. Enable it from the AI settings."
        )

    prompt_context = _build_prompt_context(candidate, application, job)

    if config.mode == AI_MODE_MOCK:
        result = _generate_mock(prompt_context, config)
    elif config.mode == AI_MODE_LIVE:
        result = _generate_live(prompt_context, config)
    else:
        raise AIConfigError(f"Unknown AI mode: {config.mode!r}")

    _enforce_advisory_rules(result)
    return result


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """You are an HR analyst supporting a recruiter at Paris United Group Holding.
Your job is to produce a structured, advisory review of a single candidate against a single job opening.

HARD RULES (these are non-negotiable):
1. You are NEVER to select, reject, hire, or blacklist a candidate. Final decisions are always made by a human HR user.
2. Your `recommendation` value must be one of: "strong_fit", "possible_fit", "weak_fit", or "needs_more_info". No other values are permitted.
3. You only describe observations; never instruct the recruiter what to do with the candidate.
4. If essential information is missing (e.g. no experience years stated), prefer "needs_more_info".
5. Keep every section concise and factual — no marketing language, no superlatives, no speculation about protected attributes.

Output: a single JSON object with these string keys, no other keys:
  - summary               : one-paragraph snapshot of the candidate vs the role
  - strengths             : 2–5 short bullet sentences separated by newlines
  - weaknesses            : 2–5 short bullet sentences separated by newlines
  - missing_information   : 1–4 bullet sentences for fields you would ask HR to confirm
  - risk_points           : 1–4 bullet sentences (e.g. visa, notice, salary mismatch). Never reference protected attributes.
  - suggested_questions   : 3–6 short interview questions, one per line
  - recommendation        : exactly one of the four allowed strings"""


def _build_prompt_context(
    candidate: Candidate,
    application: CandidateJobApplication,
    job: Optional[JobOpening],
) -> Dict[str, Any]:
    extracted = candidate.extracted_data
    return {
        "candidate": {
            "full_name": candidate.full_name,
            "nationality": candidate.nationality,
            "current_location": candidate.current_location,
            "current_designation": candidate.current_designation,
            "current_company": candidate.current_company,
            "total_experience_years": candidate.total_experience_years,
            "gcc_experience_years": candidate.gcc_experience_years,
            "qatar_experience_years": candidate.qatar_experience_years,
            "expected_salary": candidate.expected_salary,
            "notice_period": candidate.notice_period,
            "visa_status": candidate.visa_status,
            "skills": (extracted.skills if extracted else None),
            "languages": (extracted.languages if extracted else None),
            "education": (extracted.education if extracted else None),
            "certifications": (extracted.certifications if extracted else None),
            "previous_companies": (
                extracted.previous_companies if extracted else None
            ),
        },
        "job": _job_payload(job),
        "application": {
            "status": application.status,
            "cover_letter": application.cover_letter,
        },
    }


def _job_payload(job: Optional[JobOpening]) -> Optional[Dict[str, Any]]:
    if job is None:
        return None
    return {
        "title": job.title,
        "department": job.department,
        "company": job.company,
        "location": job.location,
        "employment_type": job.employment_type,
        "min_experience": job.min_experience,
        "max_experience": job.max_experience,
        "required_education": job.required_education,
        "required_skills": job.required_skills,
        "preferred_skills": job.preferred_skills,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "visa_requirement": job.visa_requirement,
        "language_requirement": job.language_requirement,
        "notice_period_preference": job.notice_period_preference,
        "description": (job.description or "")[:2000],
        "responsibilities": (job.responsibilities or "")[:2000],
        "requirements": (job.requirements or "")[:2000],
    }


def _build_user_prompt(context: Dict[str, Any]) -> str:
    return (
        "Review this candidate against the job opening. Reply ONLY with a "
        "JSON object — no preamble, no markdown fences.\n\n"
        f"CANDIDATE:\n{json.dumps(context['candidate'], indent=2, default=str)}\n\n"
        f"JOB:\n{json.dumps(context['job'], indent=2, default=str)}\n\n"
        f"APPLICATION:\n{json.dumps(context['application'], indent=2, default=str)}\n"
    )


# ---------------------------------------------------------------------------
# Mock mode (deterministic — no Azure needed)
# ---------------------------------------------------------------------------


def _generate_mock(context: Dict[str, Any], config: ResolvedAIConfig) -> AIReviewResult:
    candidate = context["candidate"]
    job = context["job"]
    name = candidate.get("full_name") or "The candidate"
    title = (job or {}).get("title") or "the role"

    years = candidate.get("total_experience_years")
    qatar_years = candidate.get("qatar_experience_years") or 0
    min_exp = (job or {}).get("min_experience") or 0
    max_exp = (job or {}).get("max_experience") or 0

    summary_bits: List[str] = [f"{name} has applied to {title}."]
    if years is not None:
        summary_bits.append(f"Total experience: {years:g} years.")
    if qatar_years:
        summary_bits.append(f"Qatar experience: {qatar_years:g} years.")
    if candidate.get("expected_salary"):
        summary_bits.append(f"Expected salary: {candidate['expected_salary']:,}.")
    summary = " ".join(summary_bits)

    strengths: List[str] = []
    if years is not None and min_exp and years >= min_exp:
        strengths.append(f"- Meets the {min_exp}-year experience minimum.")
    if qatar_years and qatar_years >= 1:
        strengths.append("- Has Qatar-based work experience.")
    if candidate.get("skills"):
        strengths.append("- CV lists relevant skills (see extracted data).")
    if candidate.get("visa_status"):
        strengths.append(f"- Visa status declared: {candidate['visa_status']}.")
    if not strengths:
        strengths.append("- No clear strengths surfaced from the extracted data.")

    weaknesses: List[str] = []
    if years is not None and min_exp and years < min_exp:
        weaknesses.append(
            f"- Below the {min_exp}-year minimum ({years:g} years recorded)."
        )
    if max_exp and years is not None and years > max_exp + 2:
        weaknesses.append(
            f"- Significantly above the {max_exp}-year cap — possibly overqualified."
        )
    if candidate.get("expected_salary") and (job or {}).get("salary_max"):
        if candidate["expected_salary"] > job["salary_max"]:
            weaknesses.append(
                f"- Expected salary {candidate['expected_salary']:,} exceeds "
                f"the band ceiling of {job['salary_max']:,}."
            )
    if not weaknesses:
        weaknesses.append("- No obvious weaknesses surfaced from the extracted data.")

    missing: List[str] = []
    for field, label in (
        ("nationality", "Nationality"),
        ("current_location", "Current location"),
        ("visa_status", "Visa status"),
        ("notice_period", "Notice period"),
        ("expected_salary", "Expected salary"),
    ):
        if not candidate.get(field):
            missing.append(f"- {label} is not recorded on the candidate.")
    if not missing:
        missing.append("- All basic fields are populated.")

    risks: List[str] = []
    if (job or {}).get("visa_requirement") and not candidate.get("visa_status"):
        risks.append("- Visa requirement on the job but candidate visa status missing.")
    if (job or {}).get("notice_period_preference") and not candidate.get("notice_period"):
        risks.append("- Job has a notice-period preference but candidate's is blank.")
    if not risks:
        risks.append("- No specific risk points detected automatically.")

    questions = [
        f"Walk me through your most recent role at {candidate.get('current_company') or 'your current employer'}.",
        f"What attracted you to {title}?",
        "Describe a challenging project where you applied your core skills.",
        f"What's your current notice period and earliest joining date?",
        "How comfortable are you with the salary band published for this role?",
    ]

    # Recommendation = simple band based on score-style heuristics.
    if years is not None and min_exp and years >= min_exp and qatar_years >= 1:
        rec = RECOMMENDATION_STRONG_FIT
    elif years is not None and min_exp and years >= min_exp * 0.7:
        rec = RECOMMENDATION_POSSIBLE_FIT
    elif years is None or not candidate.get("visa_status"):
        rec = RECOMMENDATION_NEEDS_MORE_INFO
    else:
        rec = RECOMMENDATION_WEAK_FIT

    return AIReviewResult(
        summary=summary,
        strengths="\n".join(strengths),
        weaknesses="\n".join(weaknesses),
        missing_information="\n".join(missing),
        risk_points="\n".join(risks),
        suggested_questions="\n".join(questions),
        recommendation=rec,
        model_name="mock@phase13",
        prompt_tokens=None,
        completion_tokens=None,
        raw_response={"mode": "mock", "note": "Deterministic synthetic review."},
    )


# ---------------------------------------------------------------------------
# Live mode (Azure OpenAI)
# ---------------------------------------------------------------------------


def _generate_live(context: Dict[str, Any], config: ResolvedAIConfig) -> AIReviewResult:
    # Phase C-6: provider abstraction. ``get_chat_provider`` raises a
    # ``ProviderConfigError`` when endpoint / deployment / API key are
    # unset — we wrap it as ``AIConfigError`` to preserve the existing
    # error vocabulary the orchestrator catches.
    from app.ai.providers import ProviderError, get_chat_provider
    from app.ai.providers.factory import ProviderConfigError

    try:
        provider = get_chat_provider(config)
    except ProviderConfigError as exc:
        raise AIConfigError(str(exc)) from exc

    system_prompt = SYSTEM_PROMPT
    if config.extra_system_prompt:
        system_prompt = f"{system_prompt}\n\nAdditional context:\n{config.extra_system_prompt}"

    user_prompt = _build_user_prompt(context)

    try:
        completion = provider.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config.temperature,
            max_tokens=config.max_output_tokens,
            response_format={"type": "json_object"},
        )
    except ProviderError as exc:
        raise AIProviderError(str(exc)) from exc

    raw = completion.model_dump()
    content = ""
    try:
        content = completion.choices[0].message.content or ""
    except (IndexError, AttributeError):
        content = ""

    parsed = _parse_response_json(content)

    usage = raw.get("usage") or {}
    return AIReviewResult(
        summary=str(parsed.get("summary", "")).strip(),
        strengths=str(parsed.get("strengths", "")).strip(),
        weaknesses=str(parsed.get("weaknesses", "")).strip(),
        missing_information=str(parsed.get("missing_information", "")).strip(),
        risk_points=str(parsed.get("risk_points", "")).strip(),
        suggested_questions=str(parsed.get("suggested_questions", "")).strip(),
        recommendation=str(parsed.get("recommendation", "")).strip().lower(),
        model_name=config.model_name or config.azure_deployment,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        raw_response=raw,
    )


def _parse_response_json(content: str) -> Dict[str, Any]:
    """Defensively parse the model's JSON output.

    The system prompt + response_format='json_object' should produce
    valid JSON, but we still try to recover from the occasional code
    fence or trailing commentary.
    """
    if not content:
        return {}
    text = content.strip()
    # Strip markdown fences if any.
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last-ditch: try to find the first JSON object in the string.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    logger.warning("AI returned non-JSON content: %s", text[:500])
    return {
        "summary": text[:500],
        "recommendation": RECOMMENDATION_NEEDS_MORE_INFO,
    }


# ---------------------------------------------------------------------------
# Rule enforcement
# ---------------------------------------------------------------------------


def _enforce_advisory_rules(result: AIReviewResult) -> None:
    """Mutate the result in-place to enforce hard policy rules.

    Specifically:
    - Drop forbidden recommendation values (`select`, `reject`, etc.)
      and coerce them to `needs_more_info`.
    - Map known aliases (`good_fit`, `not_enough_info`, …) to the
      allowed vocabulary.
    - Default an empty value to `needs_more_info`.
    """
    rec = (result.recommendation or "").strip().lower().replace("-", "_").replace(" ", "_")
    if rec in FORBIDDEN_RECOMMENDATIONS:
        logger.warning(
            "AI returned forbidden recommendation %r; coercing to needs_more_info.",
            result.recommendation,
        )
        rec = RECOMMENDATION_NEEDS_MORE_INFO
    elif rec in RECOMMENDATION_ALIASES:
        rec = RECOMMENDATION_ALIASES[rec]
    elif rec not in ALLOWED_RECOMMENDATIONS:
        rec = RECOMMENDATION_NEEDS_MORE_INFO
    result.recommendation = rec


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def persist_review(
    application: CandidateJobApplication, result: AIReviewResult
) -> CandidateAIReview:
    """Save (or update) the AI review row for an application."""
    review = application.ai_review
    if review is None:
        review = CandidateAIReview(application_id=application.id)
    review.summary = result.summary or None
    review.strengths = result.strengths or None
    review.weaknesses = result.weaknesses or None
    review.missing_information = result.missing_information or None
    review.risk_points = result.risk_points or None
    review.suggested_questions = result.suggested_questions or None
    review.recommendation = result.recommendation
    review.model_name = result.model_name
    review.prompt_tokens = result.prompt_tokens
    review.completion_tokens = result.completion_tokens
    review.raw_response = result.raw_response
    application.ai_review = review
    return review
