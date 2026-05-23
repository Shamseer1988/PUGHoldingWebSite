"""SQLAlchemy ORM models.

Phase 1 only registers the shared base mixins. Domain models for the
website CMS and HR ATS modules are introduced in later phases.
"""
from app.models.base import TimestampMixin

__all__ = ["TimestampMixin"]
