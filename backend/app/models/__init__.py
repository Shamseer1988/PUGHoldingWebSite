"""SQLAlchemy ORM models.

Importing this package registers every table on ``Base.metadata`` so
Alembic can autogenerate against it.
"""
from app.models.base import TimestampMixin
from app.models.auth import (
    AuditLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.models.cms import (
    Company,
    CompanyService,
    ContactMessage,
    HeroSlide,
    LeadershipMessage,
    NewsItem,
    NewsletterSubscriber,
    SiteSetting,
)
from app.models.hr_ats import (
    Candidate,
    CandidateAIReview,
    CandidateDocument,
    CandidateExtractedData,
    CandidateJobApplication,
    CandidateNote,
    CandidateScore,
    CandidateScoreBreakdown,
    CandidateStatusHistory,
    CandidateTag,
    Interview,
    InterviewFeedback,
    JobOpening,
    OfferTracking,
)
from app.models.seo import (
    SeoSetting,
    SeoVerification,
    TrackingIntegration,
)

__all__ = [
    "TimestampMixin",
    # Auth
    "AuditLog",
    "Permission",
    "Role",
    "RolePermission",
    "User",
    "UserRole",
    # CMS
    "Company",
    "CompanyService",
    "ContactMessage",
    "HeroSlide",
    "LeadershipMessage",
    "NewsItem",
    "NewsletterSubscriber",
    "SiteSetting",
    # HR ATS
    "Candidate",
    "CandidateAIReview",
    "CandidateDocument",
    "CandidateExtractedData",
    "CandidateJobApplication",
    "CandidateNote",
    "CandidateScore",
    "CandidateScoreBreakdown",
    "CandidateStatusHistory",
    "CandidateTag",
    "Interview",
    "InterviewFeedback",
    "JobOpening",
    "OfferTracking",
    # SEO
    "SeoSetting",
    "SeoVerification",
    "TrackingIntegration",
]
