"""HR ATS models (Phase 7).

A single domain module covering every HR table called out in the master
prompt. Tables introduced:

- hr_job_openings
- hr_candidates
- hr_candidate_documents
- hr_candidate_extracted_data        (1:1 with candidate)
- hr_candidate_tags
- hr_candidate_notes
- hr_candidate_job_applications      (the link table; carries pipeline state)
- hr_candidate_scores                (1:1 with application)
- hr_candidate_score_breakdowns      (1:1 with score)
- hr_candidate_ai_reviews            (1:1 with application)
- hr_candidate_status_history
- hr_interviews
- hr_interview_feedback
- hr_offer_tracking

The cross-cutting audit log (logins, settings changes, etc.) keeps using
the existing ``audit_logs`` table — HR write actions populate it with
``scope='hr'`` and rich ``details`` JSON.

Status / mode strings are exposed as constants so every later phase
shares the same vocabulary and the values stored in PostgreSQL remain
stable.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

# Job opening status
JOB_STATUS_OPEN = "open"
JOB_STATUS_ON_HOLD = "on_hold"
JOB_STATUS_CLOSED = "closed"
JOB_STATUSES = (JOB_STATUS_OPEN, JOB_STATUS_ON_HOLD, JOB_STATUS_CLOSED)

# Employment type
EMPLOYMENT_FULL_TIME = "full_time"
EMPLOYMENT_PART_TIME = "part_time"
EMPLOYMENT_CONTRACT = "contract"
EMPLOYMENT_TYPES = (EMPLOYMENT_FULL_TIME, EMPLOYMENT_PART_TIME, EMPLOYMENT_CONTRACT)

# Candidate / application status (per master prompt). Phase 3 added
# waiting_list, recommended_for_offer, and not_joined.
STATUS_CV_RECEIVED = "cv_received"
STATUS_AI_REVIEWED = "ai_reviewed"
STATUS_HR_REVIEW_PENDING = "hr_review_pending"
STATUS_SHORTLISTED = "shortlisted"
STATUS_FIRST_INTERVIEW = "first_interview"
STATUS_TECHNICAL_INTERVIEW = "technical_interview"
STATUS_FINAL_INTERVIEW = "final_interview"
STATUS_WAITING_LIST = "waiting_list"
STATUS_RECOMMENDED_FOR_OFFER = "recommended_for_offer"
STATUS_SELECTED = "selected"
STATUS_OFFER_SENT = "offer_sent"
STATUS_JOINED = "joined"
STATUS_NOT_JOINED = "not_joined"
STATUS_REJECTED = "rejected"
STATUS_BLACKLISTED = "blacklisted"

APPLICATION_STATUSES = (
    STATUS_CV_RECEIVED,
    STATUS_AI_REVIEWED,
    STATUS_HR_REVIEW_PENDING,
    STATUS_SHORTLISTED,
    STATUS_FIRST_INTERVIEW,
    STATUS_TECHNICAL_INTERVIEW,
    STATUS_FINAL_INTERVIEW,
    STATUS_WAITING_LIST,
    STATUS_RECOMMENDED_FOR_OFFER,
    STATUS_SELECTED,
    STATUS_OFFER_SENT,
    STATUS_JOINED,
    STATUS_NOT_JOINED,
    STATUS_REJECTED,
    STATUS_BLACKLISTED,
)

# Statuses that require a mandatory reason on transition.
STATUSES_REQUIRING_REASON = (STATUS_REJECTED, STATUS_BLACKLISTED)

# Interview mode
INTERVIEW_MODE_ONLINE = "online"
INTERVIEW_MODE_PHONE = "phone"
INTERVIEW_MODE_IN_PERSON = "in_person"
INTERVIEW_MODES = (INTERVIEW_MODE_ONLINE, INTERVIEW_MODE_PHONE, INTERVIEW_MODE_IN_PERSON)

# Interview status
INTERVIEW_SCHEDULED = "scheduled"
INTERVIEW_COMPLETED = "completed"
INTERVIEW_CANCELLED = "cancelled"
INTERVIEW_RESCHEDULED = "rescheduled"
INTERVIEW_NO_SHOW = "no_show"
INTERVIEW_STATUSES = (
    INTERVIEW_SCHEDULED,
    INTERVIEW_COMPLETED,
    INTERVIEW_CANCELLED,
    INTERVIEW_RESCHEDULED,
    INTERVIEW_NO_SHOW,
)

# Offer status
OFFER_DRAFT = "draft"
OFFER_SENT = "sent"
OFFER_ACCEPTED = "accepted"
OFFER_DECLINED = "declined"
OFFER_WITHDRAWN = "withdrawn"
OFFER_JOINED = "joined"
OFFER_STATUSES = (
    OFFER_DRAFT,
    OFFER_SENT,
    OFFER_ACCEPTED,
    OFFER_DECLINED,
    OFFER_WITHDRAWN,
    OFFER_JOINED,
)

# AI recommendation
AI_HIGHLY_RECOMMENDED = "highly_recommended"
AI_RECOMMENDED = "recommended"
AI_NEUTRAL = "neutral"
AI_NOT_RECOMMENDED = "not_recommended"
AI_RECOMMENDATIONS = (
    AI_HIGHLY_RECOMMENDED,
    AI_RECOMMENDED,
    AI_NEUTRAL,
    AI_NOT_RECOMMENDED,
)

# Score weights (out of 100). Mirrored on the breakdown columns and used
# by the Phase 12 scoring engine.
SCORE_WEIGHTS = {
    "relevant_experience": 25,
    "required_skills": 20,
    "education": 10,
    "industry_experience": 10,
    "gcc_qatar_experience": 10,
    "salary_fit": 10,
    "notice_period": 5,
    "visa_status": 5,
    "language_match": 5,
}
assert sum(SCORE_WEIGHTS.values()) == 100, "Score weights must sum to 100"

# Application / candidate source
SOURCE_PUBLIC_FORM = "public_form"
SOURCE_MANUAL_UPLOAD = "manual_upload"
SOURCE_BULK_UPLOAD = "bulk_upload"


# ---------------------------------------------------------------------------
# Job approval workflow constants (Advanced HR module)
# ---------------------------------------------------------------------------

APPROVAL_STATUS_DRAFT = "draft"
APPROVAL_STATUS_PENDING = "pending_approval"
APPROVAL_STATUS_APPROVED = "approved"
APPROVAL_STATUS_REJECTED = "rejected"
APPROVAL_STATUS_REVISION_REQUIRED = "revision_required"
APPROVAL_STATUSES = (
    APPROVAL_STATUS_DRAFT,
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_REJECTED,
    APPROVAL_STATUS_REVISION_REQUIRED,
)

PUBLISH_STATUS_DRAFT = "draft"
PUBLISH_STATUS_PUBLISHED = "published"
PUBLISH_STATUS_UNPUBLISHED = "unpublished"
PUBLISH_STATUSES = (
    PUBLISH_STATUS_DRAFT,
    PUBLISH_STATUS_PUBLISHED,
    PUBLISH_STATUS_UNPUBLISHED,
)

# Job approval history actions
APPROVAL_ACTION_CREATED = "created"
APPROVAL_ACTION_SUBMITTED = "submitted"
APPROVAL_ACTION_APPROVED = "approved"
APPROVAL_ACTION_REJECTED = "rejected"
APPROVAL_ACTION_REVISION_REQUESTED = "revision_requested"
APPROVAL_ACTION_REVISION_SUBMITTED = "revision_submitted"
APPROVAL_ACTION_PUBLISHED = "published"
APPROVAL_ACTION_UNPUBLISHED = "unpublished"
APPROVAL_ACTIONS = (
    APPROVAL_ACTION_CREATED,
    APPROVAL_ACTION_SUBMITTED,
    APPROVAL_ACTION_APPROVED,
    APPROVAL_ACTION_REJECTED,
    APPROVAL_ACTION_REVISION_REQUESTED,
    APPROVAL_ACTION_REVISION_SUBMITTED,
    APPROVAL_ACTION_PUBLISHED,
    APPROVAL_ACTION_UNPUBLISHED,
)

# Revision status
REVISION_STATUS_PENDING = "pending"
REVISION_STATUS_APPROVED = "approved"
REVISION_STATUS_REJECTED = "rejected"
REVISION_STATUSES = (
    REVISION_STATUS_PENDING,
    REVISION_STATUS_APPROVED,
    REVISION_STATUS_REJECTED,
)

# Auto-review decision
AUTO_REVIEW_SHORTLISTED = "auto_shortlisted"
AUTO_REVIEW_HR_PENDING = "hr_review_pending"
AUTO_REVIEW_REJECTED = "auto_rejected"
AUTO_REVIEW_DUPLICATE = "duplicate"
AUTO_REVIEW_SELECTED = "selected"
AUTO_REVIEW_DECISIONS = (
    AUTO_REVIEW_SHORTLISTED,
    AUTO_REVIEW_HR_PENDING,
    AUTO_REVIEW_REJECTED,
    AUTO_REVIEW_DUPLICATE,
    AUTO_REVIEW_SELECTED,
)

# Email log status
EMAIL_LOG_PENDING = "pending"
EMAIL_LOG_SENT = "sent"
EMAIL_LOG_FAILED = "failed"
EMAIL_LOG_STATUSES = (EMAIL_LOG_PENDING, EMAIL_LOG_SENT, EMAIL_LOG_FAILED)

# Calendar providers
CALENDAR_PROVIDER_NONE = "none"
CALENDAR_PROVIDER_GOOGLE = "google"
CALENDAR_PROVIDERS = (CALENDAR_PROVIDER_NONE, CALENDAR_PROVIDER_GOOGLE)


# ---------------------------------------------------------------------------
# Job opening
# ---------------------------------------------------------------------------


class JobOpening(Base, TimestampMixin):
    __tablename__ = "hr_job_openings"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    division: Mapped[Optional[str]] = mapped_column(String(120))
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    employment_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EMPLOYMENT_FULL_TIME, server_default=EMPLOYMENT_FULL_TIME
    )

    min_experience: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_experience: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    required_education: Mapped[Optional[str]] = mapped_column(String(255))

    salary_min: Mapped[Optional[int]] = mapped_column(Integer)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)
    visa_requirement: Mapped[Optional[str]] = mapped_column(String(120))
    nationality_preference: Mapped[Optional[str]] = mapped_column(String(255))
    language_requirement: Mapped[Optional[str]] = mapped_column(String(255))
    notice_period_preference: Mapped[Optional[str]] = mapped_column(String(120))

    description: Mapped[Optional[str]] = mapped_column(Text)
    responsibilities: Mapped[Optional[str]] = mapped_column(Text)
    requirements: Mapped[Optional[str]] = mapped_column(Text)
    required_skills: Mapped[Optional[str]] = mapped_column(Text)
    preferred_skills: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=JOB_STATUS_OPEN,
        server_default=JOB_STATUS_OPEN,
        index=True,
    )
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    # --- Approval workflow (advanced HR module) ---------------------------
    approval_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=APPROVAL_STATUS_DRAFT,
        server_default=APPROVAL_STATUS_DRAFT,
        index=True,
    )
    publish_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PUBLISH_STATUS_DRAFT,
        server_default=PUBLISH_STATUS_DRAFT,
        index=True,
    )
    approved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    submitted_for_approval_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    submitted_for_approval_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    rejected_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    approval_remarks: Mapped[Optional[str]] = mapped_column(Text)
    # Phase-2 denormalised audit columns. Populated by the corresponding
    # endpoint handler (request_revision / publish / unpublish) so listing
    # screens can sort + filter without joining hr_job_approval_history.
    changes_requested_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    changes_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    changes_requested_notes: Mapped[Optional[str]] = mapped_column(Text)
    published_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    active_revision_id: Mapped[Optional[int]] = mapped_column(Integer)

    applications: Mapped[List["CandidateJobApplication"]] = relationship(
        back_populates="job_opening", lazy="selectin"
    )
    approval_history: Mapped[List["JobApprovalHistory"]] = relationship(
        back_populates="job_opening",
        cascade="all, delete-orphan",
        order_by="JobApprovalHistory.created_at.desc()",
        lazy="selectin",
    )
    revisions: Mapped[List["JobRevision"]] = relationship(
        back_populates="job_opening",
        cascade="all, delete-orphan",
        order_by="JobRevision.created_at.desc()",
        lazy="selectin",
    )
    auto_review_rule: Mapped[Optional["JobAutoReviewRule"]] = relationship(
        back_populates="job_opening",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Candidate (master record)
# ---------------------------------------------------------------------------


class Candidate(Base, TimestampMixin):
    __tablename__ = "hr_candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(120))
    current_location: Mapped[Optional[str]] = mapped_column(String(255))
    current_designation: Mapped[Optional[str]] = mapped_column(String(255))
    current_company: Mapped[Optional[str]] = mapped_column(String(255))

    total_experience_years: Mapped[Optional[float]] = mapped_column(Float)
    gcc_experience_years: Mapped[Optional[float]] = mapped_column(Float)
    qatar_experience_years: Mapped[Optional[float]] = mapped_column(Float)

    expected_salary: Mapped[Optional[int]] = mapped_column(Integer)
    notice_period: Mapped[Optional[str]] = mapped_column(String(120))
    visa_status: Mapped[Optional[str]] = mapped_column(String(120))
    availability: Mapped[Optional[str]] = mapped_column(String(120))

    is_blacklisted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    blacklist_reason: Mapped[Optional[str]] = mapped_column(Text)
    blacklisted_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    blacklisted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    source: Mapped[Optional[str]] = mapped_column(String(32))

    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    documents: Mapped[List["CandidateDocument"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CandidateDocument.id",
    )
    extracted_data: Mapped[Optional["CandidateExtractedData"]] = relationship(
        back_populates="candidate",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    applications: Mapped[List["CandidateJobApplication"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    notes: Mapped[List["CandidateNote"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateNote.created_at.desc()",
    )
    tags: Mapped[List["CandidateTag"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateTag.tag",
    )


class CandidateDocument(Base, TimestampMixin):
    __tablename__ = "hr_candidate_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    candidate: Mapped[Candidate] = relationship(back_populates="documents")


class CandidateExtractedData(Base, TimestampMixin):
    __tablename__ = "hr_candidate_extracted_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidates.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    skills: Mapped[Optional[str]] = mapped_column(Text)
    education: Mapped[Optional[dict]] = mapped_column(JSON)
    certifications: Mapped[Optional[dict]] = mapped_column(JSON)
    languages: Mapped[Optional[dict]] = mapped_column(JSON)
    previous_companies: Mapped[Optional[dict]] = mapped_column(JSON)
    full_text: Mapped[Optional[str]] = mapped_column(Text)
    parser_version: Mapped[Optional[str]] = mapped_column(String(40))

    candidate: Mapped[Candidate] = relationship(back_populates="extracted_data")


class CandidateNote(Base, TimestampMixin):
    __tablename__ = "hr_candidate_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    candidate: Mapped[Candidate] = relationship(back_populates="notes")


class CandidateTag(Base):
    __tablename__ = "hr_candidate_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    candidate: Mapped[Candidate] = relationship(back_populates="tags")

    __table_args__ = (
        UniqueConstraint("candidate_id", "tag", name="uq_hr_tags_candidate_tag"),
    )


# ---------------------------------------------------------------------------
# Application (candidate ↔ job opening with pipeline state)
# ---------------------------------------------------------------------------


class CandidateJobApplication(Base, TimestampMixin):
    __tablename__ = "hr_candidate_job_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_opening_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("hr_job_openings.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=STATUS_CV_RECEIVED,
        server_default=STATUS_CV_RECEIVED,
        index=True,
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    source: Mapped[Optional[str]] = mapped_column(String(32))
    cover_letter: Mapped[Optional[str]] = mapped_column(Text)

    # Last-known rejection reason for quick rendering — full history lives
    # in hr_candidate_status_history.
    last_rejection_reason: Mapped[Optional[str]] = mapped_column(Text)

    candidate: Mapped[Candidate] = relationship(back_populates="applications")
    job_opening: Mapped[Optional[JobOpening]] = relationship(back_populates="applications")

    score: Mapped[Optional["CandidateScore"]] = relationship(
        back_populates="application",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    ai_review: Mapped[Optional["CandidateAIReview"]] = relationship(
        back_populates="application",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    status_history: Mapped[List["CandidateStatusHistory"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="CandidateStatusHistory.created_at",
        lazy="selectin",
    )
    interviews: Mapped[List["Interview"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="Interview.scheduled_at",
        lazy="selectin",
    )
    offer: Mapped[Optional["OfferTracking"]] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        # A candidate applies once per (open) job opening — duplicate
        # submissions are merged at the application layer in Phase 10.
        UniqueConstraint(
            "candidate_id", "job_opening_id", name="uq_hr_applications_candidate_job"
        ),
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class CandidateScore(Base, TimestampMixin):
    __tablename__ = "hr_candidate_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    is_manual_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    override_reason: Mapped[Optional[str]] = mapped_column(Text)
    overridden_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    overridden_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    application: Mapped[CandidateJobApplication] = relationship(back_populates="score")
    breakdown: Mapped[Optional["CandidateScoreBreakdown"]] = relationship(
        back_populates="score",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CandidateScoreBreakdown(Base):
    __tablename__ = "hr_candidate_score_breakdowns"

    id: Mapped[int] = mapped_column(primary_key=True)
    score_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidate_scores.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # /25
    relevant_experience: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # /20
    required_skills: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # /10
    education: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    industry_experience: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    gcc_qatar_experience: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    salary_fit: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # /5
    notice_period: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    visa_status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    language_match: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Per-component explanation strings keyed by component name.
    notes: Mapped[Optional[dict]] = mapped_column(JSON)

    score: Mapped[CandidateScore] = relationship(back_populates="breakdown")


# ---------------------------------------------------------------------------
# AI review
# ---------------------------------------------------------------------------


class CandidateAIReview(Base, TimestampMixin):
    __tablename__ = "hr_candidate_ai_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    summary: Mapped[Optional[str]] = mapped_column(Text)
    strengths: Mapped[Optional[str]] = mapped_column(Text)
    weaknesses: Mapped[Optional[str]] = mapped_column(Text)
    missing_information: Mapped[Optional[str]] = mapped_column(Text)
    risk_points: Mapped[Optional[str]] = mapped_column(Text)
    suggested_questions: Mapped[Optional[str]] = mapped_column(Text)
    recommendation: Mapped[Optional[str]] = mapped_column(String(40))

    model_name: Mapped[Optional[str]] = mapped_column(String(120))
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    application: Mapped[CandidateJobApplication] = relationship(back_populates="ai_review")


# ---------------------------------------------------------------------------
# Status history
# ---------------------------------------------------------------------------


class CandidateStatusHistory(Base):
    __tablename__ = "hr_candidate_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[Optional[str]] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    changed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    blacklist_approval: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    application: Mapped[CandidateJobApplication] = relationship(back_populates="status_history")


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------


class Interview(Base, TimestampMixin):
    __tablename__ = "hr_interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    round_name: Mapped[str] = mapped_column(String(120), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60"
    )

    mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default=INTERVIEW_MODE_ONLINE, server_default=INTERVIEW_MODE_ONLINE
    )
    location_or_link: Mapped[Optional[str]] = mapped_column(String(500))

    interviewer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=INTERVIEW_SCHEDULED,
        server_default=INTERVIEW_SCHEDULED,
        index=True,
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    # --- Calendar + invitation extras (advanced HR module) ---------------
    calendar_event_id: Mapped[Optional[str]] = mapped_column(String(255))
    meeting_link: Mapped[Optional[str]] = mapped_column(String(500))
    calendar_provider: Mapped[Optional[str]] = mapped_column(String(32))
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    email_delivery_status: Mapped[Optional[str]] = mapped_column(String(32))
    additional_attendee_emails: Mapped[Optional[list]] = mapped_column(JSON)
    cc_emails: Mapped[Optional[list]] = mapped_column(JSON)
    bcc_emails: Mapped[Optional[list]] = mapped_column(JSON)
    candidate_email_override: Mapped[Optional[str]] = mapped_column(String(255))
    email_subject: Mapped[Optional[str]] = mapped_column(String(500))
    email_note: Mapped[Optional[str]] = mapped_column(Text)
    # Phase 5 — captured by the reschedule dialog; surfaced in the
    # rescheduled email and on the row.
    reschedule_reason: Mapped[Optional[str]] = mapped_column(Text)

    application: Mapped[CandidateJobApplication] = relationship(back_populates="interviews")
    feedback: Mapped[List["InterviewFeedback"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewFeedback.created_at.desc()",
        lazy="selectin",
    )


class InterviewFeedback(Base, TimestampMixin):
    __tablename__ = "hr_interview_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("hr_interviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submitted_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1–5
    recommendation: Mapped[Optional[str]] = mapped_column(String(20))  # hire / no_hire / maybe
    feedback: Mapped[Optional[str]] = mapped_column(Text)

    technical_score: Mapped[Optional[int]] = mapped_column(Integer)
    communication_score: Mapped[Optional[int]] = mapped_column(Integer)
    cultural_fit_score: Mapped[Optional[int]] = mapped_column(Integer)

    # Phase 4 — structured free-text fields used by the quick-update modal.
    strengths: Mapped[Optional[str]] = mapped_column(Text)
    weaknesses: Mapped[Optional[str]] = mapped_column(Text)
    next_action: Mapped[Optional[str]] = mapped_column(Text)

    interview: Mapped[Interview] = relationship(back_populates="feedback")


# ---------------------------------------------------------------------------
# Offer tracking
# ---------------------------------------------------------------------------


class OfferTracking(Base, TimestampMixin):
    __tablename__ = "hr_offer_tracking"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    salary_offered: Mapped[Optional[int]] = mapped_column(Integer)
    joining_date: Mapped[Optional[date]] = mapped_column(Date)
    benefits_summary: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OFFER_DRAFT,
        server_default=OFFER_DRAFT,
        index=True,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    decline_reason: Mapped[Optional[str]] = mapped_column(Text)

    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    application: Mapped[CandidateJobApplication] = relationship(back_populates="offer")


# ---------------------------------------------------------------------------
# AI settings (Phase 13 — single row, id=1)
# ---------------------------------------------------------------------------


# Mode values: "disabled" → never call AI; "mock" → return deterministic
# synthetic review (great for dev/CI/no-key); "live" → call Azure OpenAI.
AI_MODE_DISABLED = "disabled"
AI_MODE_MOCK = "mock"
AI_MODE_LIVE = "live"
AI_MODES = (AI_MODE_DISABLED, AI_MODE_MOCK, AI_MODE_LIVE)


class AISetting(Base, TimestampMixin):
    """Runtime-tunable AI settings.

    The .env-supplied Azure credentials still bootstrap the application,
    but a system-scope admin can flip the mode, swap the deployment, or
    tune the model parameters at runtime without a redeploy. The Azure
    API key always stays in the .env — never in the database.
    """

    __tablename__ = "hr_ai_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AI_MODE_DISABLED,
        server_default=AI_MODE_DISABLED,
    )
    azure_endpoint: Mapped[Optional[str]] = mapped_column(String(500))
    azure_deployment: Mapped[Optional[str]] = mapped_column(String(120))
    azure_api_version: Mapped[Optional[str]] = mapped_column(String(40))
    # Free-form model name written to the audit record / displayed in the
    # UI. For Azure this is usually the deployment name; we keep it
    # separate so it stays human-readable even when deployments change.
    model_name: Mapped[Optional[str]] = mapped_column(String(120))
    temperature: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.2, server_default="0.2"
    )
    max_output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=900, server_default="900"
    )
    request_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=45, server_default="45"
    )
    # Extra system-prompt context: company values, locale notes, etc.
    extra_system_prompt: Mapped[Optional[str]] = mapped_column(Text)
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    # Phase 17 — Public "Ask PUG AI" assistant. Decoupled from the HR
    # `mode` above so admins can disable the public chat without
    # touching the HR review flow. The same Azure deployment +
    # temperature settings are shared (saves Azure billing complexity).
    public_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    public_extra_system_prompt: Mapped[Optional[str]] = mapped_column(Text)


class PublicAIQuery(Base):
    """A single Ask-PUG-AI exchange logged for audit + analytics."""

    __tablename__ = "public_ai_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Client-generated UUID so multi-message conversations from the
    # same user can be grouped without requiring login.
    session_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    model_name: Mapped[Optional[str]] = mapped_column(String(120))
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    was_fallback: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


# ---------------------------------------------------------------------------
# Job approval history
# ---------------------------------------------------------------------------


class JobApprovalHistory(Base):
    """One row per approval/publish/revision action on a JobOpening."""

    __tablename__ = "hr_job_approval_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_opening_id: Mapped[int] = mapped_column(
        ForeignKey("hr_job_openings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    old_approval_status: Mapped[Optional[str]] = mapped_column(String(32))
    new_approval_status: Mapped[Optional[str]] = mapped_column(String(32))
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_email: Mapped[Optional[str]] = mapped_column(String(255))
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    changed_fields: Mapped[Optional[dict]] = mapped_column(JSON)
    revision_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    job_opening: Mapped[JobOpening] = relationship(back_populates="approval_history")


# ---------------------------------------------------------------------------
# Job revision (pending edit of an approved job)
# ---------------------------------------------------------------------------


class JobRevision(Base, TimestampMixin):
    """A pending edit on an approved job — stored separately so the public
    job content is not changed until HR Manager approves the revision."""

    __tablename__ = "hr_job_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_opening_id: Mapped[int] = mapped_column(
        ForeignKey("hr_job_openings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=REVISION_STATUS_PENDING,
        server_default=REVISION_STATUS_PENDING,
        index=True,
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    job_opening: Mapped[JobOpening] = relationship(back_populates="revisions")


# ---------------------------------------------------------------------------
# Email delivery log
# ---------------------------------------------------------------------------


class EmailLog(Base):
    """Outbound email log — one row per branded send attempt."""

    __tablename__ = "hr_email_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    template_key: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    to_emails: Mapped[Optional[list]] = mapped_column(JSON)
    cc_emails: Mapped[Optional[list]] = mapped_column(JSON)
    bcc_emails: Mapped[Optional[list]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=EMAIL_LOG_PENDING,
        server_default=EMAIL_LOG_PENDING,
        index=True,
    )
    provider_response: Mapped[Optional[dict]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    related_type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    related_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


# ---------------------------------------------------------------------------
# Auto-review rule (one per job)
# ---------------------------------------------------------------------------


class JobAutoReviewRule(Base, TimestampMixin):
    """Per-job auto-shortlist / auto-review configuration."""

    __tablename__ = "hr_auto_review_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_opening_id: Mapped[int] = mapped_column(
        ForeignKey("hr_job_openings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # Optional auto-reject when score below threshold. Default False so we
    # only flag for HR review (HR confirms rejection) unless explicitly
    # enabled per job.
    auto_reject_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    min_score: Mapped[Optional[int]] = mapped_column(Integer)
    required_skills: Mapped[Optional[list]] = mapped_column(JSON)
    preferred_skills: Mapped[Optional[list]] = mapped_column(JSON)
    min_experience: Mapped[Optional[float]] = mapped_column(Float)
    max_expected_salary: Mapped[Optional[int]] = mapped_column(Integer)
    visa_keywords: Mapped[Optional[list]] = mapped_column(JSON)
    location_keywords: Mapped[Optional[list]] = mapped_column(JSON)
    nationality_keywords: Mapped[Optional[list]] = mapped_column(JSON)
    notice_period_keywords: Mapped[Optional[list]] = mapped_column(JSON)
    auto_shortlist_threshold: Mapped[Optional[int]] = mapped_column(Integer)
    auto_reject_threshold: Mapped[Optional[int]] = mapped_column(Integer)

    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    job_opening: Mapped[JobOpening] = relationship(back_populates="auto_review_rule")


# ---------------------------------------------------------------------------
# Candidate auto-review result
# ---------------------------------------------------------------------------


class CandidateAutoReview(Base, TimestampMixin):
    """Auto-review outcome for one application (1:1 with application)."""

    __tablename__ = "hr_candidate_auto_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidate_job_applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("hr_auto_review_rules.id", ondelete="SET NULL")
    )
    score: Mapped[Optional[int]] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    matched_skills: Mapped[Optional[list]] = mapped_column(JSON)
    missing_skills: Mapped[Optional[list]] = mapped_column(JSON)
    risk_flags: Mapped[Optional[list]] = mapped_column(JSON)
    reason_summary: Mapped[Optional[str]] = mapped_column(Text)
    recommendation_source: Mapped[Optional[str]] = mapped_column(String(64))
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_by_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
