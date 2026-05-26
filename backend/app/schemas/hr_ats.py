"""Pydantic schemas for the HR ATS Job Opening surface (Phase 9)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


JOB_STATUS_PATTERN = r"^(open|on_hold|closed)$"
EMPLOYMENT_TYPE_PATTERN = r"^(full_time|part_time|contract)$"
APPROVAL_STATUS_PATTERN = r"^(draft|pending_approval|approved|rejected|revision_required)$"
PUBLISH_STATUS_PATTERN = r"^(draft|published|unpublished)$"
AUTO_REVIEW_DECISION_PATTERN = (
    r"^(auto_shortlisted|hr_review_pending|auto_rejected|duplicate|selected)$"
)


class JobOpeningBase(BaseModel):
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1, max_length=255)
    department: str = Field(min_length=1, max_length=120)
    division: Optional[str] = Field(default=None, max_length=120)
    company: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=255)
    employment_type: str = Field(default="full_time", pattern=EMPLOYMENT_TYPE_PATTERN)

    min_experience: int = Field(default=0, ge=0, le=60)
    max_experience: int = Field(default=0, ge=0, le=60)
    required_education: Optional[str] = Field(default=None, max_length=255)

    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)
    visa_requirement: Optional[str] = Field(default=None, max_length=120)
    nationality_preference: Optional[str] = Field(default=None, max_length=255)
    language_requirement: Optional[str] = Field(default=None, max_length=255)
    notice_period_preference: Optional[str] = Field(default=None, max_length=120)

    description: Optional[str] = None
    responsibilities: Optional[str] = None  # newline-separated
    requirements: Optional[str] = None  # newline-separated
    required_skills: Optional[str] = None  # comma-separated
    preferred_skills: Optional[str] = None  # comma-separated

    status: str = Field(default="open", pattern=JOB_STATUS_PATTERN)


class JobOpeningCreate(JobOpeningBase):
    pass


class JobOpeningUpdate(BaseModel):
    slug: Optional[str] = Field(default=None, pattern=r"^[a-z0-9-]+$")
    title: Optional[str] = None
    department: Optional[str] = None
    division: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = Field(default=None, pattern=EMPLOYMENT_TYPE_PATTERN)

    min_experience: Optional[int] = Field(default=None, ge=0, le=60)
    max_experience: Optional[int] = Field(default=None, ge=0, le=60)
    required_education: Optional[str] = None

    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)
    visa_requirement: Optional[str] = None
    nationality_preference: Optional[str] = None
    language_requirement: Optional[str] = None
    notice_period_preference: Optional[str] = None

    description: Optional[str] = None
    responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    required_skills: Optional[str] = None
    preferred_skills: Optional[str] = None

    status: Optional[str] = Field(default=None, pattern=JOB_STATUS_PATTERN)


class JobOpeningRead(JobOpeningBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    posted_at: datetime
    closed_at: Optional[datetime] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    # Approval workflow (advanced module — back-fill rows return defaults)
    approval_status: str = "draft"
    publish_status: str = "draft"
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    submitted_for_approval_by_id: Optional[int] = None
    submitted_for_approval_at: Optional[datetime] = None
    rejected_by_id: Optional[int] = None
    rejected_at: Optional[datetime] = None
    approval_remarks: Optional[str] = None
    active_revision_id: Optional[int] = None
    has_pending_revision: bool = False


class JobOpeningList(BaseModel):
    """Lightweight list payload — same fields, used as the response model
    of the list endpoint. Kept as a thin alias so we can later switch
    to a paginated wrapper without touching consumers."""

    items: List[JobOpeningRead]


# ---------------------------------------------------------------------------
# Candidates (Phase 10)
# ---------------------------------------------------------------------------


class CandidateDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_path: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    is_primary: bool
    uploaded_by_id: Optional[int] = None
    created_at: datetime


class CandidateScoreBreakdownRead(BaseModel):
    """Per-component score breakdown (Phase 12)."""

    model_config = ConfigDict(from_attributes=True)

    relevant_experience: int = 0
    required_skills: int = 0
    education: int = 0
    industry_experience: int = 0
    gcc_qatar_experience: int = 0
    salary_fit: int = 0
    notice_period: int = 0
    visa_status: int = 0
    language_match: int = 0
    notes: Optional[Dict[str, str]] = None


class CandidateScoreRead(BaseModel):
    """Total + breakdown + override metadata (Phase 12)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    total: int
    is_manual_override: bool = False
    override_reason: Optional[str] = None
    overridden_by_id: Optional[int] = None
    overridden_at: Optional[datetime] = None
    breakdown: Optional[CandidateScoreBreakdownRead] = None
    updated_at: Optional[datetime] = None


class CandidateScoreOverride(BaseModel):
    """Payload for POST .../score/override — reason is mandatory."""

    total: int = Field(ge=0, le=100)
    reason: str = Field(min_length=4, max_length=2000)


class CandidateAIReviewPreview(BaseModel):
    """Compact AI-review summary embedded in application listings."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    recommendation: Optional[str] = None
    model_name: Optional[str] = None
    generated_at: datetime
    updated_at: Optional[datetime] = None


class InterviewSummaryForApplication(BaseModel):
    """Compact interview row embedded inside the application summary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    round_name: str
    round_number: int
    scheduled_at: datetime
    duration_minutes: int
    mode: str
    mode_label: str
    location_or_link: Optional[str] = None
    status: str
    status_label: str
    interviewer_id: Optional[int] = None
    interviewer_email: Optional[str] = None
    interviewer_name: Optional[str] = None
    has_feedback: bool = False
    latest_recommendation: Optional[str] = None


class CandidateApplicationSummary(BaseModel):
    """Application row shown alongside the candidate (e.g. in lists)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    status_label: Optional[str] = None
    job_opening_id: Optional[int] = None
    job_title: Optional[str] = None
    applied_at: datetime
    source: Optional[str] = None
    last_rejection_reason: Optional[str] = None
    score: Optional[CandidateScoreRead] = None
    ai_review: Optional[CandidateAIReviewPreview] = None
    history_count: int = 0
    allowed_next_statuses: List[str] = Field(default_factory=list)
    interviews: List[InterviewSummaryForApplication] = Field(default_factory=list)
    interview_count: int = 0
    next_interview_at: Optional[datetime] = None


class CandidateExtractedDataRead(BaseModel):
    """Structured CV extraction (Phase 11)."""

    model_config = ConfigDict(from_attributes=True)

    skills: Optional[str] = None
    education: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    previous_companies: Optional[List[Dict[str, Any]]] = None
    full_text: Optional[str] = None
    parser_version: Optional[str] = None
    updated_at: Optional[datetime] = None


class CandidateExtractedDataUpdate(BaseModel):
    """Manual HR correction of the structured CV data."""

    skills: Optional[str] = None
    education: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    previous_companies: Optional[List[Dict[str, Any]]] = None
    full_text: Optional[str] = None


class CandidateUpdate(BaseModel):
    """HR manual edit of the headline candidate fields (Phase 11)."""

    full_name: Optional[str] = Field(default=None, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    mobile: Optional[str] = Field(default=None, max_length=40)
    nationality: Optional[str] = Field(default=None, max_length=120)
    current_location: Optional[str] = Field(default=None, max_length=255)
    current_designation: Optional[str] = Field(default=None, max_length=255)
    current_company: Optional[str] = Field(default=None, max_length=255)
    total_experience_years: Optional[float] = Field(default=None, ge=0, le=70)
    gcc_experience_years: Optional[float] = Field(default=None, ge=0, le=70)
    qatar_experience_years: Optional[float] = Field(default=None, ge=0, le=70)
    expected_salary: Optional[int] = Field(default=None, ge=0)
    notice_period: Optional[str] = Field(default=None, max_length=120)
    visa_status: Optional[str] = Field(default=None, max_length=120)
    availability: Optional[str] = Field(default=None, max_length=120)


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    nationality: Optional[str] = None
    current_location: Optional[str] = None
    current_designation: Optional[str] = None
    current_company: Optional[str] = None
    total_experience_years: Optional[float] = None
    gcc_experience_years: Optional[float] = None
    qatar_experience_years: Optional[float] = None
    expected_salary: Optional[int] = None
    notice_period: Optional[str] = None
    visa_status: Optional[str] = None
    availability: Optional[str] = None
    is_blacklisted: bool
    is_archived: bool
    source: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    documents: List[CandidateDocumentRead] = Field(default_factory=list)
    extracted_data: Optional[CandidateExtractedDataRead] = None
    applications: List[CandidateApplicationSummary] = Field(default_factory=list)
    top_score: Optional[int] = None


class CvReparseResult(BaseModel):
    candidate: CandidateRead
    parsed: bool
    parser_version: Optional[str] = None
    detail: Optional[str] = None


class CandidateListItem(BaseModel):
    """Trimmed candidate row for the HR list view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    current_designation: Optional[str] = None
    total_experience_years: Optional[float] = None
    source: Optional[str] = None
    is_blacklisted: bool
    is_archived: bool
    created_at: datetime
    top_score: Optional[int] = None
    latest_status: Optional[str] = None
    latest_status_label: Optional[str] = None


class ApplicationSubmissionResponse(BaseModel):
    """Returned from POST /public/candidate-applications and the HR
    single-upload endpoint."""

    candidate_id: int
    application_id: int
    was_existing_candidate: bool
    job_title: Optional[str] = None
    job_slug: Optional[str] = None


class BulkUploadSkip(BaseModel):
    name: str
    reason: str


class BulkUploadResult(BaseModel):
    total_files: int
    created_candidates: int
    matched_existing_candidates: int
    duplicate_applications_skipped: int
    skipped_files: List[BulkUploadSkip] = Field(default_factory=list)
    candidate_ids: List[int] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Candidate workflow / status pipeline (Phase 14)
# ---------------------------------------------------------------------------


class CandidateStatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    old_status: Optional[str] = None
    new_status: str
    changed_by_id: Optional[int] = None
    changed_by_email: Optional[str] = None
    remarks: Optional[str] = None
    rejection_reason: Optional[str] = None
    blacklist_approval: Optional[str] = None
    created_at: datetime


class CandidateStatusChange(BaseModel):
    new_status: str = Field(min_length=1, max_length=40)
    remarks: Optional[str] = Field(default=None, max_length=2000)
    rejection_reason: Optional[str] = Field(default=None, max_length=2000)
    blacklist_approval: Optional[str] = Field(default=None, max_length=2000)


class StatusOption(BaseModel):
    """Status descriptor returned by the meta endpoint."""

    value: str
    label: str
    is_final: bool = False


class StatusPipelineMeta(BaseModel):
    statuses: List[StatusOption]
    transitions: Dict[str, List[str]]


# ---------------------------------------------------------------------------
# AI candidate review (Phase 13)
# ---------------------------------------------------------------------------


AI_MODE_PATTERN = r"^(disabled|mock|live)$"


class CandidateAIReviewRead(BaseModel):
    """Advisory AI review for a candidate-application pair."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    application_id: int
    summary: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    missing_information: Optional[str] = None
    risk_points: Optional[str] = None
    suggested_questions: Optional[str] = None
    recommendation: Optional[str] = None
    model_name: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    generated_at: datetime
    updated_at: Optional[datetime] = None


class AIReviewGenerateResult(BaseModel):
    """Return value of POST .../ai-review — wraps the persisted review."""

    model_config = ConfigDict(protected_namespaces=())

    review: CandidateAIReviewRead
    mode: str
    model_name: Optional[str] = None


class AISettingsRead(BaseModel):
    """Runtime AI configuration (Phase 13)."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    mode: str
    azure_endpoint: Optional[str] = None
    azure_deployment: Optional[str] = None
    azure_api_version: Optional[str] = None
    model_name: Optional[str] = None
    temperature: float
    max_output_tokens: int
    request_timeout_seconds: int
    extra_system_prompt: Optional[str] = None
    updated_by_id: Optional[int] = None
    updated_at: Optional[datetime] = None
    # Diagnostic flags so the UI can warn HR clearly when 'live' mode
    # is selected but credentials aren't actually in the environment.
    has_azure_api_key: bool = False
    effective_mode: Optional[str] = None
    # Public "Ask PUG AI" toggles (Phase 17). Decoupled from the HR
    # mode so admins can disable the public chat without touching the
    # HR review flow.
    public_enabled: bool = True
    public_extra_system_prompt: Optional[str] = None


class AISettingsUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    mode: Optional[str] = Field(default=None, pattern=AI_MODE_PATTERN)
    azure_endpoint: Optional[str] = Field(default=None, max_length=500)
    azure_deployment: Optional[str] = Field(default=None, max_length=120)
    azure_api_version: Optional[str] = Field(default=None, max_length=40)
    model_name: Optional[str] = Field(default=None, max_length=120)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: Optional[int] = Field(default=None, ge=64, le=8000)
    request_timeout_seconds: Optional[int] = Field(default=None, ge=5, le=300)
    extra_system_prompt: Optional[str] = None
    public_enabled: Optional[bool] = None
    public_extra_system_prompt: Optional[str] = None


# ---------------------------------------------------------------------------
# Public AI assistant (Phase 17)
# ---------------------------------------------------------------------------


class PublicAIAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=64)
    history: Optional[List[Dict[str, str]]] = Field(default=None, max_length=20)


class PublicAIAskResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    answer: str
    mode: str
    was_fallback: bool = False
    session_id: Optional[str] = None
    model_name: Optional[str] = None


class PublicAIQueryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    session_id: Optional[str] = None
    question: str
    answer: Optional[str] = None
    mode: str
    model_name: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    was_fallback: bool
    ip_address: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Interview management (Phase 15)
# ---------------------------------------------------------------------------


INTERVIEW_MODE_PATTERN = r"^(online|phone|in_person)$"
INTERVIEW_STATUS_PATTERN = r"^(scheduled|completed|cancelled|rescheduled|no_show)$"
INTERVIEW_RECOMMENDATION_PATTERN = r"^(hire|no_hire|maybe)$"


class InterviewFeedbackBase(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    recommendation: Optional[str] = Field(
        default=None, pattern=INTERVIEW_RECOMMENDATION_PATTERN
    )
    feedback: Optional[str] = Field(default=None, max_length=4000)
    technical_score: Optional[int] = Field(default=None, ge=0, le=10)
    communication_score: Optional[int] = Field(default=None, ge=0, le=10)
    cultural_fit_score: Optional[int] = Field(default=None, ge=0, le=10)


class InterviewFeedbackCreate(InterviewFeedbackBase):
    pass


class InterviewFeedbackRead(InterviewFeedbackBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_id: int
    submitted_by_id: Optional[int] = None
    submitted_by_email: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class InterviewBase(BaseModel):
    round_name: str = Field(min_length=1, max_length=120)
    round_number: int = Field(default=1, ge=1, le=20)
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=5, le=480)
    mode: str = Field(pattern=INTERVIEW_MODE_PATTERN)
    location_or_link: Optional[str] = Field(default=None, max_length=500)
    interviewer_id: Optional[int] = None


class InterviewCreate(InterviewBase):
    application_id: int

    # Advanced module — interview email + Google Meet extras. All
    # optional with safe defaults so existing callers don't break.
    candidate_email_override: Optional[str] = Field(default=None, max_length=255)
    additional_attendee_emails: List[str] = Field(default_factory=list)
    cc_emails: List[str] = Field(default_factory=list)
    bcc_emails: List[str] = Field(default_factory=list)
    email_subject: Optional[str] = Field(default=None, max_length=500)
    email_note: Optional[str] = Field(default=None, max_length=4000)
    send_email_now: bool = False
    create_google_meet: bool = False


class InterviewUpdate(BaseModel):
    round_name: Optional[str] = Field(default=None, max_length=120)
    round_number: Optional[int] = Field(default=None, ge=1, le=20)
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=480)
    mode: Optional[str] = Field(default=None, pattern=INTERVIEW_MODE_PATTERN)
    location_or_link: Optional[str] = Field(default=None, max_length=500)
    interviewer_id: Optional[int] = None


class InterviewStatusChange(BaseModel):
    new_status: str = Field(pattern=INTERVIEW_STATUS_PATTERN)


class InterviewRead(InterviewBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    status: str
    status_label: Optional[str] = None
    mode_label: Optional[str] = None
    interviewer_email: Optional[str] = None
    interviewer_name: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    feedback: List[InterviewFeedbackRead] = Field(default_factory=list)

    # Calendar / email fields (advanced module)
    meeting_link: Optional[str] = None
    calendar_event_id: Optional[str] = None
    calendar_provider: Optional[str] = None
    email_sent_at: Optional[datetime] = None
    email_delivery_status: Optional[str] = None
    additional_attendee_emails: Optional[List[str]] = None
    cc_emails: Optional[List[str]] = None
    bcc_emails: Optional[List[str]] = None
    candidate_email_override: Optional[str] = None
    email_subject: Optional[str] = None
    email_note: Optional[str] = None


class InterviewListItem(BaseModel):
    """Row used by the calendar/list page and the candidate timeline."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    candidate_id: int
    candidate_name: str
    job_title: Optional[str] = None
    round_name: str
    round_number: int
    scheduled_at: datetime
    duration_minutes: int
    mode: str
    mode_label: str
    location_or_link: Optional[str] = None
    interviewer_id: Optional[int] = None
    interviewer_email: Optional[str] = None
    interviewer_name: Optional[str] = None
    status: str
    status_label: str
    has_feedback: bool = False
    latest_recommendation: Optional[str] = None


# ---------------------------------------------------------------------------
# Job approval workflow schemas
# ---------------------------------------------------------------------------


class JobApprovalActionRequest(BaseModel):
    """Payload for approve / reject / request-revision / publish endpoints."""

    remarks: Optional[str] = Field(default=None, max_length=2000)


class JobApprovalRejectRequest(BaseModel):
    """Reject requires a non-empty reason."""

    remarks: str = Field(min_length=4, max_length=2000)


class JobApprovalHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_opening_id: int
    action: str
    old_approval_status: Optional[str] = None
    new_approval_status: Optional[str] = None
    actor_id: Optional[int] = None
    actor_email: Optional[str] = None
    remarks: Optional[str] = None
    changed_fields: Optional[Dict[str, Any]] = None
    revision_id: Optional[int] = None
    created_at: datetime


class JobRevisionRead(BaseModel):
    """A pending/approved/rejected job edit."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_opening_id: int
    payload: Dict[str, Any]
    status: str
    created_by_id: Optional[int] = None
    reviewed_by_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Email log schemas
# ---------------------------------------------------------------------------


class EmailLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope: Optional[str] = None
    template_key: Optional[str] = None
    subject: Optional[str] = None
    to_emails: Optional[List[str]] = None
    cc_emails: Optional[List[str]] = None
    bcc_emails: Optional[List[str]] = None
    status: str
    provider_response: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    related_type: Optional[str] = None
    related_id: Optional[str] = None
    created_by_id: Optional[int] = None
    sent_at: Optional[datetime] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Auto-review rule + outcome schemas
# ---------------------------------------------------------------------------


class JobAutoReviewRuleBase(BaseModel):
    is_active: bool = True
    auto_reject_enabled: bool = False
    min_score: Optional[int] = Field(default=None, ge=0, le=100)
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    min_experience: Optional[float] = Field(default=None, ge=0, le=70)
    max_expected_salary: Optional[int] = Field(default=None, ge=0)
    visa_keywords: Optional[List[str]] = None
    location_keywords: Optional[List[str]] = None
    nationality_keywords: Optional[List[str]] = None
    notice_period_keywords: Optional[List[str]] = None
    auto_shortlist_threshold: Optional[int] = Field(default=None, ge=0, le=100)
    auto_reject_threshold: Optional[int] = Field(default=None, ge=0, le=100)


class JobAutoReviewRuleUpdate(JobAutoReviewRuleBase):
    """Same fields, all optional — used for PUT (upsert)."""

    is_active: Optional[bool] = None
    auto_reject_enabled: Optional[bool] = None


class JobAutoReviewRuleRead(JobAutoReviewRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_opening_id: int
    created_by_id: Optional[int] = None
    updated_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class CandidateAutoReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    rule_id: Optional[int] = None
    score: Optional[int] = None
    decision: str
    matched_skills: Optional[List[str]] = None
    missing_skills: Optional[List[str]] = None
    risk_flags: Optional[List[str]] = None
    reason_summary: Optional[str] = None
    recommendation_source: Optional[str] = None
    reviewed_at: datetime
    reviewed_by_system: bool


class JobAutoReviewSummary(BaseModel):
    job_opening_id: int
    total_applications: int
    auto_shortlisted: int = 0
    hr_review_pending: int = 0
    auto_rejected: int = 0
    duplicates: int = 0
    not_reviewed: int = 0


# ---------------------------------------------------------------------------
# Bulk candidate status change schemas
# ---------------------------------------------------------------------------


class BulkCandidateStatusChangeRequest(BaseModel):
    application_ids: List[int] = Field(min_length=1, max_length=500)
    new_status: str = Field(min_length=1, max_length=40)
    remarks: Optional[str] = Field(default=None, max_length=2000)
    rejection_reason: Optional[str] = Field(default=None, max_length=2000)
    blacklist_approval: Optional[str] = Field(default=None, max_length=2000)
    send_email: bool = False
    all_or_nothing: bool = False


class BulkCandidateStatusChangeRow(BaseModel):
    application_id: int
    candidate_id: Optional[int] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    success: bool
    error: Optional[str] = None


class BulkCandidateStatusChangeResult(BaseModel):
    total: int
    success_count: int
    failed_count: int
    rows: List[BulkCandidateStatusChangeRow]


# ---------------------------------------------------------------------------
# Public CV preview schemas
# ---------------------------------------------------------------------------


class PublicCvParsePreview(BaseModel):
    """Parsed CV fields returned by the public Apply form pre-fill endpoint."""

    parsed: bool
    parser_version: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    full_name: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    nationality: Optional[str] = None
    current_location: Optional[str] = None
    current_designation: Optional[str] = None
    current_company: Optional[str] = None
    total_experience_years: Optional[float] = None
    gcc_experience_years: Optional[float] = None
    qatar_experience_years: Optional[float] = None
    expected_salary: Optional[int] = None
    notice_period: Optional[str] = None
    visa_status: Optional[str] = None
    skills: Optional[str] = None
    education: Optional[List[Dict[str, Any]]] = None
    languages: Optional[List[str]] = None
    certifications: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Interview email/Google Meet extras (advanced module)
# ---------------------------------------------------------------------------


class InterviewEmailFields(BaseModel):
    """Optional email/meet fields added to InterviewCreate by the advanced
    module. Composed into a single payload that extends InterviewCreate
    without breaking older callers — every field has a safe default."""

    candidate_email_override: Optional[str] = Field(default=None, max_length=255)
    additional_attendee_emails: List[str] = Field(default_factory=list)
    cc_emails: List[str] = Field(default_factory=list)
    bcc_emails: List[str] = Field(default_factory=list)
    email_subject: Optional[str] = Field(default=None, max_length=500)
    email_note: Optional[str] = Field(default=None, max_length=4000)
    send_email_now: bool = False
    create_google_meet: bool = False
