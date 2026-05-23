"""Smoke tests for the Phase 1 health-check endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_liveness_endpoint_returns_alive() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_root_endpoint_returns_service_metadata() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["docs"] == "/docs"
    assert payload["health"] == "/api/v1/health"
