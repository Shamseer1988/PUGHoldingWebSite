"""Interview scorecard templates (Feature F2)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.scorecard import (
    ScorecardError,
    compute_weighted_total,
    validate_template_dimensions,
)


HR_LOGIN = "/api/v1/hr/auth/login"
ADMIN_LOGIN = "/api/v1/admin/auth/login"
TEMPL = "/api/v1/hr/scorecard-templates"


def _login(client: TestClient, email: str, password: str, *, admin: bool = False) -> dict:
    url = ADMIN_LOGIN if admin else HR_LOGIN
    r = client.post(url, json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _superuser_headers(client: TestClient, password: str) -> dict:
    return _login(client, "superadmin@pug.example.com", password, admin=True)


GOOD_DIMS = [
    {
        "key": "system_design",
        "label": "System design",
        "description": "Scale, failure modes",
        "max_score": 5,
        "weight": 50,
    },
    {
        "key": "communication",
        "label": "Communication",
        "max_score": 5,
        "weight": 50,
    },
]


# ---------------------------------------------------------------------------
# Pure service tests
# ---------------------------------------------------------------------------


class TestValidateDimensions:
    def test_accepts_valid(self):
        validate_template_dimensions(GOOD_DIMS)  # no raise

    def test_rejects_empty(self):
        with pytest.raises(ScorecardError):
            validate_template_dimensions([])

    def test_rejects_duplicate_keys(self):
        bad = [
            {"key": "a", "label": "A", "max_score": 5, "weight": 50},
            {"key": "a", "label": "A2", "max_score": 5, "weight": 50},
        ]
        with pytest.raises(ScorecardError) as excinfo:
            validate_template_dimensions(bad)
        assert "Duplicate" in str(excinfo.value)

    def test_rejects_weights_not_summing_to_100(self):
        bad = [
            {"key": "a", "label": "A", "max_score": 5, "weight": 30},
            {"key": "b", "label": "B", "max_score": 5, "weight": 40},
        ]
        with pytest.raises(ScorecardError) as excinfo:
            validate_template_dimensions(bad)
        assert "sum to 100" in str(excinfo.value)


class TestWeightedTotal:
    def test_full_marks_all_dimensions(self):
        scores = {
            "system_design": {"score": 5},
            "communication": {"score": 5},
        }
        assert compute_weighted_total(GOOD_DIMS, scores) == 100

    def test_zero_when_no_scores(self):
        assert compute_weighted_total(GOOD_DIMS, {}) == 0

    def test_partial_weighted(self):
        # system_design 3/5 (weight 50) + communication 5/5 (weight 50)
        # = (0.6 * 50) + (1.0 * 50) = 30 + 50 = 80
        scores = {
            "system_design": {"score": 3},
            "communication": {"score": 5},
        }
        assert compute_weighted_total(GOOD_DIMS, scores) == 80

    def test_clamps_over_max_score(self):
        # Submitting 15 on a max_score=5 dimension should clamp to 5.
        scores = {
            "system_design": {"score": 15},
            "communication": {"score": 5},
        }
        assert compute_weighted_total(GOOD_DIMS, scores) == 100

    def test_ignores_unknown_dimension_keys(self):
        scores = {
            "system_design": {"score": 5},
            "communication": {"score": 5},
            "made_up": {"score": 100},  # not in the template
        }
        assert compute_weighted_total(GOOD_DIMS, scores) == 100


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestTemplateCRUD:
    def test_create_requires_dim_weights_sum_to_100(
        self, client: TestClient, seed_auth
    ):
        # Super Admin -> can do everything; goes through admin login.
        headers = _superuser_headers(client, seed_auth["password"])
        bad = {
            "name": "Bad weights",
            "scope": "global",
            "dimensions": [
                {"key": "a", "label": "A", "max_score": 5, "weight": 30},
            ],
        }
        resp = client.post(TEMPL, headers=headers, json=bad)
        assert resp.status_code == 422
        assert "sum to 100" in resp.json()["detail"]

    def test_create_global_template_and_listing(
        self, client: TestClient, seed_auth
    ):
        headers = _superuser_headers(client, seed_auth["password"])
        body = {
            "name": "Default eng rubric",
            "scope": "global",
            "dimensions": GOOD_DIMS,
            "is_default": True,
        }
        r = client.post(TEMPL, headers=headers, json=body)
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["is_default"] is True
        assert len(created["dimensions"]) == 2

        listing = client.get(TEMPL, headers=headers).json()
        assert any(t["id"] == created["id"] for t in listing)

    def test_job_scope_requires_job_id(
        self, client: TestClient, seed_auth
    ):
        headers = _superuser_headers(client, seed_auth["password"])
        body = {
            "name": "Job rubric without job id",
            "scope": "job",
            "dimensions": GOOD_DIMS,
        }
        r = client.post(TEMPL, headers=headers, json=body)
        assert r.status_code == 422
        assert "job_opening_id" in r.json()["detail"]

    def test_setting_default_flips_previous_default(
        self, client: TestClient, seed_auth
    ):
        headers = _superuser_headers(client, seed_auth["password"])
        a = client.post(
            TEMPL,
            headers=headers,
            json={
                "name": "Default A",
                "scope": "global",
                "dimensions": GOOD_DIMS,
                "is_default": True,
            },
        ).json()
        b = client.post(
            TEMPL,
            headers=headers,
            json={
                "name": "Default B",
                "scope": "global",
                "dimensions": GOOD_DIMS,
                "is_default": True,
            },
        ).json()
        assert b["is_default"] is True

        # Re-fetch A — it should no longer be the default.
        r = client.get(f"{TEMPL}/{a['id']}", headers=headers)
        assert r.json()["is_default"] is False

    def test_deactivate_marks_inactive_not_deleted(
        self, client: TestClient, seed_auth
    ):
        headers = _superuser_headers(client, seed_auth["password"])
        t = client.post(
            TEMPL,
            headers=headers,
            json={
                "name": "To soft-archive",
                "scope": "global",
                "dimensions": GOOD_DIMS,
            },
        ).json()
        assert client.delete(f"{TEMPL}/{t['id']}", headers=headers).status_code == 204

        # Inactive — does not appear in default listing
        active_listing = client.get(TEMPL, headers=headers).json()
        assert all(x["id"] != t["id"] for x in active_listing)
        # ...but include_inactive=true shows it
        all_listing = client.get(
            f"{TEMPL}?include_inactive=true", headers=headers
        ).json()
        assert any(x["id"] == t["id"] for x in all_listing)


class TestTemplateAccess:
    def test_anon_is_401(self, client: TestClient):
        assert client.get(TEMPL).status_code == 401

    def test_interviewer_can_list(self, client: TestClient, seed_auth):
        headers = _login(
            client, "interviewer@pug.example.com", seed_auth["password"]
        )
        # Returns 200 (possibly empty list) — interviewers need read.
        assert client.get(TEMPL, headers=headers).status_code == 200

    def test_interviewer_cannot_create(
        self, client: TestClient, seed_auth
    ):
        headers = _login(
            client, "interviewer@pug.example.com", seed_auth["password"]
        )
        body = {
            "name": "Sneaky",
            "scope": "global",
            "dimensions": GOOD_DIMS,
        }
        assert client.post(TEMPL, headers=headers, json=body).status_code == 403
