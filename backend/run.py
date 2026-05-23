"""
Paris United Group Holding - Backend entry point.

Run locally:
    python run.py

Or with uvicorn directly:
    uvicorn app.main:app --reload
"""
from __future__ import annotations

import uvicorn

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
