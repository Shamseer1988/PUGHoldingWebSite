"""Routing rule for the universal HR realtime bump (recruitment overhaul).

``HrDataBumpMiddleware`` turns any successful HR *write* into an
``hr.data.changed`` pulse so consoles refetch. ``should_bump`` encodes that
rule as a pure function; these tests pin it without spinning up the app.
"""
from __future__ import annotations

import pytest

from app.core.hr_data_bump import should_bump


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "post", "delete"])
def test_bumps_on_successful_hr_write(method: str) -> None:
    assert should_bump(method, "/api/v1/hr/jobs/5/publish", 200) is True


def test_bumps_on_201_and_204() -> None:
    assert should_bump("POST", "/api/v1/hr/candidates/bulk-upload", 201) is True
    assert should_bump("DELETE", "/api/v1/hr/interviews/9", 204) is True


def test_no_bump_on_reads() -> None:
    for method in ("GET", "HEAD", "OPTIONS"):
        assert should_bump(method, "/api/v1/hr/jobs", 200) is False


def test_no_bump_on_failed_writes() -> None:
    for code in (400, 409, 422, 500):
        assert should_bump("POST", "/api/v1/hr/jobs", code) is False


def test_no_bump_outside_hr_namespace() -> None:
    assert should_bump("POST", "/api/v1/public/applications", 201) is False
    assert should_bump("POST", "/api/v1/admin/users", 201) is False


def test_no_bump_for_hr_auth() -> None:
    # Authenticating is not a data change.
    assert should_bump("POST", "/api/v1/hr/auth/login", 200) is False
    assert should_bump("POST", "/api/v1/hr/auth/refresh", 200) is False
    # The exclusion is path-boundary precise: a real data resource whose name
    # merely begins with "auth" still bumps (guards an over-broad prefix).
    assert should_bump("POST", "/api/v1/hr/authorizations", 201) is True
