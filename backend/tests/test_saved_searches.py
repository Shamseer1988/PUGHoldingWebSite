"""Saved candidate searches / talent pool (Feature F1)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.models.hr_ats import SavedCandidateSearch


BASE = "/api/v1/hr/saved-searches"
HR_LOGIN = "/api/v1/hr/auth/login"


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


class TestAccess:
    def test_anonymous_is_401(self, client: TestClient):
        resp = client.get(BASE)
        assert resp.status_code == 401

    def test_website_only_user_is_403(self, client: TestClient, seed_auth):
        # webadmin has the website scope, not HR — no candidate-list perm.
        # Sign in via the admin (website) login flow first, then verify
        # they can't reach the HR-only saved-search endpoints.
        resp = client.post(
            "/api/v1/admin/auth/login",
            json={
                "email": "webadmin@pug.example.com",
                "password": seed_auth["password"],
            },
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        r2 = client.get(BASE, headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 403


# ---------------------------------------------------------------------------
# CRUD lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_create_list_update_delete_cycle(
        self, client: TestClient, seed_auth, db_session
    ):
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])

        # Create
        body = {
            "name": "QA leads in Doha",
            "description": "Saved for the QA wave",
            "filters": {
                "q": "QA",
                "location": "Doha",
                "experience_min": 5,
            },
            "scope": "private",
            "pinned": True,
        }
        resp = client.post(BASE, headers=headers, json=body)
        assert resp.status_code == 201, resp.text
        created = resp.json()
        assert created["name"] == "QA leads in Doha"
        assert created["scope"] == "private"
        assert created["pinned"] is True
        assert created["is_owner"] is True
        ssid = created["id"]

        # Listing returns it (and only it for the HR user — no team
        # search shared by anyone else).
        resp = client.get(BASE, headers=headers)
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()]
        assert "QA leads in Doha" in names

        # Update via PATCH
        resp = client.patch(
            f"{BASE}/{ssid}",
            headers=headers,
            json={"name": "QA leads in Qatar", "scope": "team"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["name"] == "QA leads in Qatar"
        assert resp.json()["scope"] == "team"

        # Delete
        resp = client.delete(f"{BASE}/{ssid}", headers=headers)
        assert resp.status_code == 204

        # 404 on subsequent fetch
        resp = client.patch(
            f"{BASE}/{ssid}", headers=headers, json={"name": "x"}
        )
        assert resp.status_code == 404

    def test_duplicate_name_per_owner_rejected(
        self, client: TestClient, seed_auth
    ):
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        body = {"name": "Sales SDRs", "filters": {}}
        assert client.post(BASE, headers=headers, json=body).status_code == 201
        # Same name, same owner -> 409
        resp = client.post(BASE, headers=headers, json=body)
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Scope visibility
# ---------------------------------------------------------------------------


class TestScopeVisibility:
    def test_team_scope_visible_to_other_hr_users(
        self, client: TestClient, seed_auth
    ):
        owner_headers = _login(
            client, "hradmin@pug.example.com", seed_auth["password"]
        )
        other_headers = _login(
            client, "hrexec@pug.example.com", seed_auth["password"]
        )

        # Owner creates a team-scoped search
        resp = client.post(
            BASE,
            headers=owner_headers,
            json={
                "name": "Open Eng reqs",
                "filters": {"department": "Engineering"},
                "scope": "team",
            },
        )
        assert resp.status_code == 201, resp.text

        # Other HR user can see it but is_owner=False
        resp = client.get(BASE, headers=other_headers)
        rows = resp.json()
        match = next((r for r in rows if r["name"] == "Open Eng reqs"), None)
        assert match is not None
        assert match["is_owner"] is False

    def test_private_scope_hidden_from_other_users(
        self, client: TestClient, seed_auth
    ):
        owner_headers = _login(
            client, "hradmin@pug.example.com", seed_auth["password"]
        )
        other_headers = _login(
            client, "hrexec@pug.example.com", seed_auth["password"]
        )

        resp = client.post(
            BASE,
            headers=owner_headers,
            json={"name": "My drafts", "filters": {}, "scope": "private"},
        )
        ssid = resp.json()["id"]

        # Other user does not see it in the listing
        rows = client.get(BASE, headers=other_headers).json()
        assert all(r["id"] != ssid for r in rows)

        # And they can't run it (403)
        run = client.post(f"{BASE}/{ssid}/run", headers=other_headers)
        assert run.status_code == 403


# ---------------------------------------------------------------------------
# Edit guard
# ---------------------------------------------------------------------------


class TestEditGuard:
    def test_non_owner_cannot_edit_team_search(
        self, client: TestClient, seed_auth
    ):
        owner_headers = _login(
            client, "hradmin@pug.example.com", seed_auth["password"]
        )
        other_headers = _login(
            client, "hrexec@pug.example.com", seed_auth["password"]
        )
        ssid = client.post(
            BASE,
            headers=owner_headers,
            json={"name": "Team thing", "filters": {}, "scope": "team"},
        ).json()["id"]

        resp = client.patch(
            f"{BASE}/{ssid}",
            headers=other_headers,
            json={"name": "Hijacked"},
        )
        assert resp.status_code == 403

        resp = client.delete(f"{BASE}/{ssid}", headers=other_headers)
        assert resp.status_code == 403

    def test_superuser_can_edit_anyone(self, client: TestClient, seed_auth):
        owner_headers = _login(
            client, "hradmin@pug.example.com", seed_auth["password"]
        )
        # Superusers use the website login flow (they have system scope).
        admin_login = client.post(
            "/api/v1/admin/auth/login",
            json={
                "email": "superadmin@pug.example.com",
                "password": seed_auth["password"],
            },
        )
        super_headers = {
            "Authorization": f"Bearer {admin_login.json()['access_token']}"
        }
        ssid = client.post(
            BASE,
            headers=owner_headers,
            json={"name": "Owned by HR", "filters": {}, "scope": "team"},
        ).json()["id"]

        resp = client.patch(
            f"{BASE}/{ssid}",
            headers=super_headers,
            json={"description": "Reclaimed after staff churn"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Run endpoint
# ---------------------------------------------------------------------------


class TestRun:
    def test_run_empty_filter_returns_empty_list_when_no_candidates(
        self, client: TestClient, seed_auth
    ):
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        ssid = client.post(
            BASE,
            headers=headers,
            json={"name": "All candidates", "filters": {}, "scope": "private"},
        ).json()["id"]

        resp = client.post(f"{BASE}/{ssid}/run", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["saved_search_id"] == ssid
        assert body["result_count"] == 0
        assert body["candidate_ids"] == []

    def test_run_updates_last_run_metadata(
        self, client: TestClient, seed_auth, db_session
    ):
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        ssid = client.post(
            BASE,
            headers=headers,
            json={
                "name": "Run me",
                "filters": {"q": "nothing-will-match"},
                "scope": "private",
            },
        ).json()["id"]
        assert (
            client.post(f"{BASE}/{ssid}/run", headers=headers).status_code
            == 200
        )

        row = db_session.get(SavedCandidateSearch, ssid)
        assert row.last_run_at is not None
        assert row.last_result_count == 0
