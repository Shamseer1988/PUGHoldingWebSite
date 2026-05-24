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

__all__ = [
    "TimestampMixin",
    "AuditLog",
    "Permission",
    "Role",
    "RolePermission",
    "User",
    "UserRole",
    "Company",
    "CompanyService",
    "ContactMessage",
    "HeroSlide",
    "LeadershipMessage",
    "NewsItem",
    "NewsletterSubscriber",
    "SiteSetting",
]
