"""Marketing role tier coverage.

Two new seeded roles unlock the marketing surface for non-superuser
operators:

* ``Marketing Manager``  — full read + manage on campaigns +
  catalogues, plus the analytics dashboard.
* ``Marketing Viewer``   — read-only access to campaigns +
  catalogues, plus the analytics dashboard.

Tests confirm the dependency split: viewers can list / read but
get a 403 on every mutation, managers can do both, and a user
with no marketing key at all (the existing webadmin) still hits
403 across the board.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


ADMIN_LOGIN = "/api/v1/admin/auth/login"
ADMIN_MARKETING = "/api/v1/admin/marketing"


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post(ADMIN_LOGIN, json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Marketing Viewer — read everything, mutate nothing
# ---------------------------------------------------------------------------


def test_viewer_can_read_campaigns(client: TestClient, seed_auth):
    headers = _login(
        client,
        "marketingviewer@pug.example.com",
        seed_auth["password"],
    )
    r = client.get(f"{ADMIN_MARKETING}/campaigns", headers=headers)
    assert r.status_code == 200


def test_viewer_can_read_catalogues(client: TestClient, seed_auth):
    headers = _login(
        client,
        "marketingviewer@pug.example.com",
        seed_auth["password"],
    )
    r = client.get(f"{ADMIN_MARKETING}/catalogues", headers=headers)
    assert r.status_code == 200


def test_viewer_can_see_dashboard(client: TestClient, seed_auth):
    headers = _login(
        client,
        "marketingviewer@pug.example.com",
        seed_auth["password"],
    )
    r = client.get(f"{ADMIN_MARKETING}/dashboard", headers=headers)
    assert r.status_code == 200


def test_viewer_cannot_create_campaign(client: TestClient, seed_auth):
    headers = _login(
        client,
        "marketingviewer@pug.example.com",
        seed_auth["password"],
    )
    r = client.post(
        f"{ADMIN_MARKETING}/campaigns",
        json={"slug": "test", "title": "Nope"},
        headers=headers,
    )
    assert r.status_code == 403


def test_viewer_cannot_reconcile_counters(
    client: TestClient, seed_auth
):
    headers = _login(
        client,
        "marketingviewer@pug.example.com",
        seed_auth["password"],
    )
    r = client.post(
        f"{ADMIN_MARKETING}/catalogues/reconcile-counters",
        headers=headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Marketing Manager — read + manage
# ---------------------------------------------------------------------------


def test_manager_can_read_and_see_dashboard(
    client: TestClient, seed_auth
):
    headers = _login(
        client,
        "marketingmgr@pug.example.com",
        seed_auth["password"],
    )
    for path in ("/campaigns", "/catalogues", "/dashboard"):
        r = client.get(f"{ADMIN_MARKETING}{path}", headers=headers)
        assert r.status_code == 200, f"{path}: {r.text}"


def test_manager_can_create_campaign(client: TestClient, seed_auth):
    headers = _login(
        client,
        "marketingmgr@pug.example.com",
        seed_auth["password"],
    )
    r = client.post(
        f"{ADMIN_MARKETING}/campaigns",
        json={
            "slug": "manager-can-create",
            "title": "Created by marketing manager",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["slug"] == "manager-can-create"


def test_manager_can_reconcile_counters(client: TestClient, seed_auth):
    headers = _login(
        client,
        "marketingmgr@pug.example.com",
        seed_auth["password"],
    )
    r = client.post(
        f"{ADMIN_MARKETING}/catalogues/reconcile-counters",
        headers=headers,
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Webadmin — still has NO marketing access at all
# ---------------------------------------------------------------------------


def test_webadmin_with_no_marketing_perm_is_locked_out(
    client: TestClient, seed_auth
):
    headers = _login(
        client, "webadmin@pug.example.com", seed_auth["password"]
    )
    for path in ("/campaigns", "/catalogues", "/dashboard"):
        r = client.get(f"{ADMIN_MARKETING}{path}", headers=headers)
        assert r.status_code == 403, f"{path}: {r.text}"
