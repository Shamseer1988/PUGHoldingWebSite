"""Public "Ask PUG AI" assistant (Phase 17).

Public-facing chat that answers questions about Paris United Group
Holding using only public CMS content as context. Reuses the Phase-13
AISetting + resolve_config + AzureOpenAI plumbing so we don't run two
Azure clients in parallel.

Hard guardrails enforced by the system prompt AND by what we expose
in the context:

  - Only PUBLIC data is fetched (active companies, leadership shown
    on the public site, published news, public site settings, open
    public jobs). Candidate / employee / admin data never enters the
    prompt — it isn't even loaded.
  - The system prompt forbids discussing internal HR, candidates,
    interview feedback, salaries, hiring decisions, or anything not
    in the supplied context.
  - The model cannot write to the DB — this service is read-only.
  - When admin disables the public AI, the endpoint returns a friendly
    canned response with the contact details from site settings.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.ai.candidate_review import (
    AI_MODE_DISABLED,
    AI_MODE_LIVE,
    AI_MODE_MOCK,
    AIConfigError,
    AIProviderError,
    ResolvedAIConfig,
    resolve_config,
)
from app.models.cms import Company, LeadershipMessage, NewsItem, SiteSetting
from app.models.hr_ats import (
    JOB_STATUS_OPEN,
    AISetting,
    JobOpening,
    PublicAIQuery,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result + context shapes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AskResult:
    answer: str
    mode: str
    model_name: Optional[str] = None
    was_fallback: bool = False
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


@dataclass(slots=True)
class PublicContext:
    site_name: str
    tagline: Optional[str]
    contact_phone: Optional[str]
    contact_email: Optional[str]
    contact_address: Optional[str]
    whatsapp_number: Optional[str]
    companies: List[Dict[str, Any]] = field(default_factory=list)
    leadership: List[Dict[str, Any]] = field(default_factory=list)
    news: List[Dict[str, Any]] = field(default_factory=list)
    jobs: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public context loader
# ---------------------------------------------------------------------------


def load_public_context(db: Session) -> PublicContext:
    """Snapshot every piece of CMS data the public site renders.

    Strict allow-list: candidates / users / scores / interviews are
    never queried.
    """
    settings = db.get(SiteSetting, 1)

    companies = (
        db.execute(
            select(Company)
            .where(Company.is_active.is_(True))
            .order_by(Company.display_order, Company.name)
        )
        .scalars()
        .all()
    )
    leadership = (
        db.execute(
            select(LeadershipMessage)
            .where(LeadershipMessage.is_active.is_(True))
            .order_by(LeadershipMessage.display_order, LeadershipMessage.id)
        )
        .scalars()
        .all()
    )
    news = (
        db.execute(
            select(NewsItem)
            .where(NewsItem.is_published.is_(True))
            .order_by(desc(NewsItem.published_at))
            .limit(8)
        )
        .scalars()
        .all()
    )
    jobs = (
        db.execute(
            select(JobOpening)
            .where(JobOpening.status == JOB_STATUS_OPEN)
            .order_by(desc(JobOpening.posted_at))
            .limit(20)
        )
        .scalars()
        .all()
    )

    return PublicContext(
        site_name=settings.site_name if settings else "Paris United Group Holding",
        tagline=settings.tagline if settings else None,
        contact_phone=settings.contact_phone if settings else None,
        contact_email=settings.contact_email if settings else None,
        contact_address=settings.contact_address if settings else None,
        whatsapp_number=settings.whatsapp_number if settings else None,
        companies=[
            {
                "name": c.name,
                "slug": c.slug,
                "category": c.category,
                "short_description": c.short_description,
                "branches": c.branches,
                "services": [s.name for s in c.services],
            }
            for c in companies
        ],
        leadership=[
            {
                "name": l.name,
                "role": l.role,
                "short_message": l.short_message,
            }
            for l in leadership
        ],
        news=[
            {
                "title": n.title,
                "summary": n.summary,
                "category": n.category,
                "published_at": n.published_at.date().isoformat()
                if n.published_at
                else None,
            }
            for n in news
        ],
        jobs=[
            {
                "title": j.title,
                "department": j.department,
                "company": j.company,
                "location": j.location,
                "employment_type": j.employment_type,
                "min_experience": j.min_experience,
                "max_experience": j.max_experience,
                "slug": j.slug,
            }
            for j in jobs
        ],
    )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """You are Ask PUG AI, the public assistant for Paris United Group Holding (PUG).

Your job is to help visitors of the public website learn about:
  - The group's companies and services
  - Leadership (names + roles only — NEVER discuss salaries, hiring decisions, or anything internal)
  - News + events
  - Current open job openings (titles, departments, locations only — NEVER discuss specific applicants)
  - How to contact the group

HARD RULES (non-negotiable):
1. ONLY use facts present in the CONTEXT provided below. If the answer is not in the context, politely say you don't have that information and point the visitor to the contact details.
2. You MUST NEVER discuss: internal HR data, candidate profiles, employees by name (other than the leadership listed in the context), salaries, scores, interview feedback, or any internal admin information.
3. You MUST NEVER claim to take actions like "I'll forward your CV", "I'll book an interview", or "I've updated your application". You cannot modify any data.
4. Keep answers concise (2–5 sentences for most questions). Use friendly, professional, corporate tone.
5. For job-related questions, list relevant open roles from the context and direct candidates to apply through the careers page.
6. If asked about something outside the group's scope (e.g. politics, opinions, generic chit-chat), gently decline and redirect to what you can help with."""


def _build_user_prompt(question: str, ctx: PublicContext, history: Optional[List[Dict[str, str]]]) -> str:
    history_block = ""
    if history:
        recent = history[-6:]  # cap at last 3 turns
        lines = [
            f"{turn.get('role', 'user').upper()}: {turn.get('content', '').strip()}"
            for turn in recent
            if turn.get("content")
        ]
        if lines:
            history_block = "RECENT CONVERSATION:\n" + "\n".join(lines) + "\n\n"

    import json

    context_block = json.dumps(
        {
            "site": {
                "name": ctx.site_name,
                "tagline": ctx.tagline,
                "contact": {
                    "phone": ctx.contact_phone,
                    "email": ctx.contact_email,
                    "whatsapp": ctx.whatsapp_number,
                    "address": ctx.contact_address,
                },
            },
            "companies": ctx.companies,
            "leadership": ctx.leadership,
            "news": ctx.news,
            "open_jobs": ctx.jobs,
        },
        indent=2,
        default=str,
    )

    return (
        f"{history_block}"
        f"CONTEXT:\n{context_block}\n\n"
        f"QUESTION: {question.strip()}\n\n"
        "Answer using only the CONTEXT above. If the answer isn't in there, "
        "say so and point to the contact details."
    )


# ---------------------------------------------------------------------------
# Mode dispatchers
# ---------------------------------------------------------------------------


def answer_question(
    db: Session,
    *,
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
    setting: Optional[AISetting] = None,
) -> AskResult:
    """Top-level orchestrator.

    1. Pulls public context from CMS tables (no candidate/user data).
    2. Picks a generator based on `AISetting.public_enabled` + the
       shared `mode` (disabled / mock / live).
    3. Always returns a usable `AskResult` — never raises.
    """
    question = (question or "").strip()
    if not question:
        return AskResult(
            answer="Please ask me something about Paris United Group.",
            mode=AI_MODE_DISABLED,
            was_fallback=True,
        )

    setting = setting if setting is not None else db.get(AISetting, 1)
    config = resolve_config(setting)
    public_enabled = setting.public_enabled if setting is not None else True
    extra_public_prompt = (
        setting.public_extra_system_prompt if setting is not None else None
    )

    context = load_public_context(db)

    if not public_enabled or config.mode == AI_MODE_DISABLED:
        return _fallback_answer(context, mode=AI_MODE_DISABLED, fallback=True)

    if config.mode == AI_MODE_MOCK:
        return _mock_answer(question, context)

    # Live mode
    try:
        return _live_answer(
            question=question,
            context=context,
            history=history,
            config=config,
            extra_public_prompt=extra_public_prompt,
        )
    except (AIConfigError, AIProviderError) as exc:
        logger.warning("Public AI live mode failed; falling back: %s", exc)
        result = _fallback_answer(context, mode=config.mode, fallback=True)
        result.answer = (
            "Sorry — I couldn't reach the AI service right now. "
            + result.answer
        )
        return result


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def _fallback_answer(ctx: PublicContext, *, mode: str, fallback: bool) -> AskResult:
    bits = [
        "The AI assistant is currently unavailable. In the meantime, "
        "the team is happy to help directly."
    ]
    if ctx.contact_phone:
        bits.append(f"Phone: {ctx.contact_phone}")
    if ctx.contact_email:
        bits.append(f"Email: {ctx.contact_email}")
    if ctx.whatsapp_number:
        bits.append(f"WhatsApp: {ctx.whatsapp_number}")
    return AskResult(
        answer=" ".join(bits),
        mode=mode,
        was_fallback=fallback,
    )


_GREETING_RE = re.compile(r"\b(hi|hello|hey|salam|salaam|greetings)\b", re.IGNORECASE)


def _mock_answer(question: str, ctx: PublicContext) -> AskResult:
    """Deterministic keyword-routed answer used when no Azure key.

    Cheap, safe, never hallucinates — picks the most relevant chunk of
    the public context and stitches a short, helpful sentence.
    """
    q = question.lower()

    if _GREETING_RE.search(q):
        return AskResult(
            answer=(
                f"Hi! I'm Ask PUG AI — happy to help you learn about "
                f"{ctx.site_name}. Try asking me about our group companies, "
                "leadership, current job openings, or how to get in touch."
            ),
            mode=AI_MODE_MOCK,
            model_name="mock",
        )

    # Contact details
    if any(k in q for k in ("contact", "phone", "email", "whatsapp", "address")):
        bits = [
            f"You can reach {ctx.site_name} via:"
        ]
        if ctx.contact_phone:
            bits.append(f"📞 {ctx.contact_phone}")
        if ctx.contact_email:
            bits.append(f"✉️ {ctx.contact_email}")
        if ctx.whatsapp_number:
            bits.append(f"💬 WhatsApp {ctx.whatsapp_number}")
        if ctx.contact_address:
            bits.append(f"📍 {ctx.contact_address}")
        return AskResult(answer="\n".join(bits), mode=AI_MODE_MOCK, model_name="mock")

    # Jobs / careers
    if any(k in q for k in ("job", "vacancy", "vacancies", "career", "hiring", "apply", "position")):
        if not ctx.jobs:
            return AskResult(
                answer=(
                    "There are no public openings listed right now. "
                    "Check the Careers page or send your CV via the contact form."
                ),
                mode=AI_MODE_MOCK,
                model_name="mock",
            )
        top = ctx.jobs[:5]
        lines = [
            f"We currently have {len(ctx.jobs)} open role"
            f"{'s' if len(ctx.jobs) != 1 else ''}. A few highlights:"
        ]
        for j in top:
            lines.append(
                f"• {j['title']} — {j['department']} at {j['company']} ({j['location']})"
            )
        lines.append("Apply via the Careers page on the website.")
        return AskResult(answer="\n".join(lines), mode=AI_MODE_MOCK, model_name="mock")

    # Companies / group
    if any(k in q for k in ("compan", "subsidiar", "brand", "group", "business")):
        if not ctx.companies:
            return AskResult(
                answer=(
                    f"{ctx.site_name} operates across retail, distribution, and services. "
                    "Visit the Companies page for the latest list."
                ),
                mode=AI_MODE_MOCK,
                model_name="mock",
            )
        categories: Dict[str, List[str]] = {}
        for c in ctx.companies:
            categories.setdefault(c["category"], []).append(c["name"])
        lines = [
            f"{ctx.site_name} runs {len(ctx.companies)} companies across "
            f"{len(categories)} sectors:"
        ]
        for cat, names in categories.items():
            lines.append(
                f"• {cat.capitalize()}: {', '.join(names[:6])}"
                + (f" and {len(names) - 6} more" if len(names) > 6 else "")
            )
        return AskResult(answer="\n".join(lines), mode=AI_MODE_MOCK, model_name="mock")

    # Leadership
    if any(k in q for k in ("chairman", "ceo", "founder", "leader", "directors", "managing director", "md")):
        if not ctx.leadership:
            return AskResult(
                answer="Visit the About page to read messages from our leadership team.",
                mode=AI_MODE_MOCK,
                model_name="mock",
            )
        lines = ["Our leadership team:"]
        for l in ctx.leadership[:4]:
            lines.append(f"• {l['name']} — {l['role']}")
        return AskResult(answer="\n".join(lines), mode=AI_MODE_MOCK, model_name="mock")

    # News
    if any(k in q for k in ("news", "update", "event", "latest", "press", "csr")):
        if not ctx.news:
            return AskResult(
                answer="Check the News & Events page for the latest updates.",
                mode=AI_MODE_MOCK,
                model_name="mock",
            )
        lines = ["A few recent updates from the group:"]
        for n in ctx.news[:3]:
            lines.append(
                f"• {n['title']}"
                + (f" — {n['summary']}" if n.get("summary") else "")
            )
        return AskResult(answer="\n".join(lines), mode=AI_MODE_MOCK, model_name="mock")

    # Default — point them to the resources we do have.
    return AskResult(
        answer=(
            f"I can help with questions about {ctx.site_name}'s companies, "
            "leadership, news, careers, and contact details. For anything "
            "more specific, please reach the team through the contact page."
        ),
        mode=AI_MODE_MOCK,
        model_name="mock",
    )


def _live_answer(
    *,
    question: str,
    context: PublicContext,
    history: Optional[List[Dict[str, str]]],
    config: ResolvedAIConfig,
    extra_public_prompt: Optional[str],
) -> AskResult:
    if not (
        config.azure_endpoint
        and config.azure_deployment
        and config.azure_api_key
    ):
        raise AIConfigError(
            "AI is set to 'live' but Azure endpoint / deployment / API key are not configured."
        )

    try:
        from openai import AzureOpenAI  # imported lazily
    except ImportError as exc:  # pragma: no cover
        raise AIConfigError(
            "openai package is not installed. Run `pip install -r requirements.txt`."
        ) from exc

    client = AzureOpenAI(
        api_key=config.azure_api_key,
        api_version=config.azure_api_version or "2024-08-01-preview",
        azure_endpoint=config.azure_endpoint,
        timeout=config.request_timeout_seconds,
    )

    system_prompt = SYSTEM_PROMPT
    if extra_public_prompt and extra_public_prompt.strip():
        system_prompt = f"{system_prompt}\n\nADDITIONAL CONTEXT FROM ADMIN:\n{extra_public_prompt.strip()}"

    user_prompt = _build_user_prompt(question, context, history)

    try:
        completion = client.chat.completions.create(
            model=config.azure_deployment,
            temperature=config.temperature,
            max_tokens=min(config.max_output_tokens, 600),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        raise AIProviderError(f"Azure OpenAI call failed: {exc}") from exc

    raw = completion.model_dump()
    answer = ""
    try:
        answer = (completion.choices[0].message.content or "").strip()
    except (IndexError, AttributeError):
        answer = ""

    if not answer:
        raise AIProviderError("Azure OpenAI returned an empty response.")

    usage = raw.get("usage") or {}
    return AskResult(
        answer=answer,
        mode=AI_MODE_LIVE,
        model_name=config.model_name or config.azure_deployment,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def log_query(
    db: Session,
    *,
    question: str,
    result: AskResult,
    session_id: Optional[str],
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> PublicAIQuery:
    row = PublicAIQuery(
        session_id=session_id,
        question=question[:4000],
        answer=(result.answer or "")[:4000],
        mode=result.mode,
        model_name=result.model_name,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        was_fallback=result.was_fallback,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
