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
    TrustedBrand,
)
from app.models.hr_ats import (
    Candidate,
    CandidateAIReview,
    CandidateAutoReview,
    CandidateDocument,
    CandidateExtractedData,
    CandidateJobApplication,
    CandidateNote,
    CandidateScore,
    CandidateScoreBreakdown,
    CandidateStatusHistory,
    CandidateTag,
    EmailLog,
    Interview,
    InterviewFeedback,
    JobApprovalHistory,
    JobAutoReviewRule,
    JobOpening,
    JobRevision,
    OfferTracking,
)
from app.models.marketing import (
    Catalogue,
    CataloguePage,
    CatalogueViewEvent,
    OfferCampaign,
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
    "TrustedBrand",
    # HR ATS
    "Candidate",
    "CandidateAIReview",
    "CandidateAutoReview",
    "CandidateDocument",
    "CandidateExtractedData",
    "CandidateJobApplication",
    "CandidateNote",
    "CandidateScore",
    "CandidateScoreBreakdown",
    "CandidateStatusHistory",
    "CandidateTag",
    "EmailLog",
    "Interview",
    "InterviewFeedback",
    "JobApprovalHistory",
    "JobAutoReviewRule",
    "JobOpening",
    "JobRevision",
    "OfferTracking",
    # Marketing — Digital Offers & Catalogues
    "Catalogue",
    "CataloguePage",
    "CatalogueViewEvent",
    "OfferCampaign",
    # SEO
    "SeoSetting",
    "SeoVerification",
    "TrackingIntegration",
]
