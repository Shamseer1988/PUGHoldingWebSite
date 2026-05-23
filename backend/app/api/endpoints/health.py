"""Health-check endpoints used by load balancers and monitoring."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Return service and database status."""
    settings = get_settings()
    database_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_status = "disconnected"

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        database=database_status,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/health/live",
    summary="Liveness probe (no dependencies)",
)
def liveness() -> dict[str, str]:
    """Lightweight liveness check (does not touch the database)."""
    return {"status": "alive"}
