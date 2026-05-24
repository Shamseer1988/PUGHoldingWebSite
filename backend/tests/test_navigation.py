"""Tests for the Phase-5 follow-up navigation menu CRUD + public endpoint."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cms import NavigationItem


ADMIN_LOGIN = "/api/v1/admin/auth/login"
ADMIN_NAV = "/api/v1/admin/cms/navigation"
PUBLIC_NAV = "/api/v1/public/navigation"


def _admin_headers(client: TestClient, password: str) -> dict:
    response = client.post(
        ADMIN_LOGIN,
        json={"email": "webadmin@pug.example.com", "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Public endpoint
# ---------------------------------------------------------------------------


def test_public_navigation_returns_empty_when_no_rows(client):
    body = client.get(PUBLIC_NAV).json()
    assert body == []


def test_public_navigation_only_includes_active_items(
    client, db_session: Session
):
    db_session.add_all(
        [
            NavigationItem(
                label="Home", href="/", display_order=1, is_active=True
            ),
            NavigationItem(
                label="Hidden", href="/hidden", display_order=2, is_active=False
            ),
        ]
    )
    db_session.commit()

    body = client.get(PUBLIC_NAV).json()
    labels = [n["label"] for n in body]
    assert labels == ["Home"]


def test_public_navigation_returns_two_level_tree(
    client, db_session: Session
):
    about = NavigationItem(label="About", href="/about", display_order=1)
    db_session.add(about)
    db_session.flush()
    db_session.add_all(
        [
            NavigationItem(
                label="Story",
                href="/about",
                description="Vision + mission",
                parent_id=about.id,
                display_order=1,
            ),
            NavigationItem(
                label="History",
                href="/about#history",
                parent_id=about.id,
                display_order=2,
            ),
        ]
    )
    db_session.commit()

    body = client.get(PUBLIC_NAV).json()
    assert len(body) == 1
    parent = body[0]
    assert parent["label"] == "About"
    assert [c["label"] for c in parent["children"]] == ["Story", "History"]
    # description carried through
    assert parent["children"][0]["description"] == "Vision + mission"


# ---------------------------------------------------------------------------
# Admin CRUD
# ---------------------------------------------------------------------------


def test_admin_can_create_top_level_item(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    response = client.post(
        ADMIN_NAV,
        headers=headers,
        json={
            "label": "Careers",
            "href": "/careers",
            "display_order": 5,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["label"] == "Careers"
    assert body["parent_id"] is None
    assert body["is_active"] is True


def test_admin_can_create_child_and_admin_list_returns_tree(
    client, seed_auth, db_session: Session
):
    headers = _admin_headers(client, seed_auth["password"])
    parent = client.post(
        ADMIN_NAV,
        headers=headers,
        json={"label": "About", "href": "/about", "display_order": 1},
    ).json()
    child_resp = client.post(
        ADMIN_NAV,
        headers=headers,
        json={
            "label": "Story",
            "href": "/about",
            "parent_id": parent["id"],
            "display_order": 1,
        },
    )
    assert child_resp.status_code == 201, child_resp.text

    tree = client.get(ADMIN_NAV, headers=headers).json()
    about = next(n for n in tree if n["label"] == "About")
    assert [c["label"] for c in about["children"]] == ["Story"]


def test_create_child_rejects_two_level_nesting(client, seed_auth):
    headers = _admin_headers(client, seed_auth["password"])
    parent = client.post(
        ADMIN_NAV,
        headers=headers,
        json={"label": "Top", "href": "/top"},
    ).json()
    child = client.post(
        ADMIN_NAV,
        headers=headers,
        json={"label": "Child", "href": "/c", "parent_id": parent["id"]},
    ).json()
    # Try to create a grandchild — should be rejected.
    grand = client.post(
        ADMIN_NAV,
        headers=headers,
        json={"label": "Grand", "href": "/g", "parent_id": child["id"]},
    )
    assert grand.status_code == 422


def test_admin_can_update_item(client, seed_auth, db_session: Session):
    item = NavigationItem(label="Old", href="/old")
    db_session.add(item)
    db_session.commit()

    headers = _admin_headers(client, seed_auth["password"])
    response = client.patch(
        f"{ADMIN_NAV}/{item.id}",
        headers=headers,
        json={"label": "New", "href": "/new", "is_active": False},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["label"] == "New"
    assert body["href"] == "/new"
    assert body["is_active"] is False


def test_admin_cannot_set_self_as_parent(client, seed_auth, db_session: Session):
    item = NavigationItem(label="X", href="/x")
    db_session.add(item)
    db_session.commit()
    headers = _admin_headers(client, seed_auth["password"])
    response = client.patch(
        f"{ADMIN_NAV}/{item.id}",
        headers=headers,
        json={"parent_id": item.id},
    )
    assert response.status_code == 422


def test_admin_can_delete_item(client, seed_auth, db_session: Session):
    item = NavigationItem(label="Doomed", href="/d")
    db_session.add(item)
    db_session.commit()
    item_id = item.id
    # Detach so the API delete doesn't leave a dangling identity-map
    # entry that confuses the subsequent `.get()` below.
    db_session.expunge_all()

    headers = _admin_headers(client, seed_auth["password"])
    response = client.delete(f"{ADMIN_NAV}/{item_id}", headers=headers)
    assert response.status_code == 204

    assert db_session.get(NavigationItem, item_id) is None


def test_delete_cascades_children(client, seed_auth, db_session: Session):
    parent = NavigationItem(label="P", href="/p")
    db_session.add(parent)
    db_session.flush()
    child = NavigationItem(label="C", href="/c", parent_id=parent.id)
    db_session.add(child)
    db_session.commit()
    parent_id = parent.id
    child_id = child.id
    db_session.expunge_all()

    headers = _admin_headers(client, seed_auth["password"])
    response = client.delete(f"{ADMIN_NAV}/{parent_id}", headers=headers)
    assert response.status_code == 204

    assert db_session.get(NavigationItem, parent_id) is None
    assert db_session.get(NavigationItem, child_id) is None


# ---------------------------------------------------------------------------
# Scope isolation
# ---------------------------------------------------------------------------


def test_admin_nav_endpoints_block_hr_only_user(client, seed_auth):
    login = client.post(
        "/api/v1/hr/auth/login",
        json={"email": "hr@pug.example.com", "password": seed_auth["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get(ADMIN_NAV, headers=headers)
    assert response.status_code == 403
