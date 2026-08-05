"""Divisions + per-branch QR codes (Marketing → QR Codes).

Covers:

* Division CRUD, slug derivation from name, slug conflicts.
* Auto-created "Primary" QR on division create.
* QR CRUD + slug immutability (the feature's core guarantee).
* ``GET /q/{slug}`` — 302 to the current target, scan counter, scan
  events, and the fallback chain that keeps printed codes from
  dead-ending.
* Permission isolation: viewer can read, cannot write.
* Analytics payload shape + target history from the audit log.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.marketing_qr import MarketingQrCode, MarketingQrScanEvent


ADMIN_LOGIN = "/api/v1/admin/auth/login"
DIVISIONS = "/api/v1/admin/marketing/divisions"
QR_CODES = "/api/v1/admin/marketing/qr-codes"
PUBLIC = "/api/v1/q"


def _auth(client: TestClient, password: str, email: str = "superadmin@pug.example.com") -> dict[str, str]:
    r = client.post(ADMIN_LOGIN, json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_division(
    client: TestClient, headers: dict[str, str], name: str = "Paris Hyper Market Al Atiyah", **extra
) -> dict:
    payload = {"name": name}
    payload.update(extra)
    r = client.post(DIVISIONS, headers=headers, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Divisions
# ---------------------------------------------------------------------------


def test_create_division_derives_slug_and_primary_qr(client: TestClient, seed_auth):
    """The one-form-submit path: a division arrives with a usable code."""
    headers = _auth(client, seed_auth["password"])
    body = _make_division(client, headers, city="Doha")

    assert body["slug"] == "paris-hyper-market-al-atiyah"
    assert body["name"] == "Paris Hyper Market Al Atiyah"
    assert body["city"] == "Doha"
    assert body["is_active"] is True

    assert len(body["qr_codes"]) == 1
    qr = body["qr_codes"][0]
    assert qr["label"] == "Primary"
    assert qr["slug"] == "paris-hyper-market-al-atiyah"
    # No target yet — the code is printable before marketing decides.
    assert qr["target_url"] is None
    assert qr["scan_count"] == 0


def test_create_division_without_primary_qr(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    body = _make_division(client, headers, name="Al Khor", create_primary_qr=False)
    assert body["qr_codes"] == []


def test_division_slug_conflict_is_409(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    _make_division(client, headers, name="Al Wakra", slug="al-wakra")
    r = client.post(
        DIVISIONS, headers=headers, json={"name": "Al Wakra Two", "slug": "al-wakra"}
    )
    assert r.status_code == 409, r.text


def test_duplicate_names_get_suffixed_slugs(client: TestClient, seed_auth):
    """Two branches with the same name must not collide on slug."""
    headers = _auth(client, seed_auth["password"])
    a = _make_division(client, headers, name="Umm Salal")
    b = _make_division(client, headers, name="Umm Salal")
    assert a["slug"] == "umm-salal"
    assert b["slug"] == "umm-salal-2"
    # Their auto-created QR slugs must be distinct too.
    assert a["qr_codes"][0]["slug"] != b["qr_codes"][0]["slug"]


def test_list_divisions_nests_qr_codes(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    _make_division(client, headers, name="Al Khor")
    _make_division(client, headers, name="Al Wakra")

    r = client.get(DIVISIONS, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    assert all(len(d["qr_codes"]) == 1 for d in body["items"])


def test_update_division_does_not_touch_qr_slugs(client: TestClient, seed_auth):
    """Renaming a branch must never invalidate its printed artwork."""
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    original_qr_slug = division["qr_codes"][0]["slug"]

    r = client.patch(
        f"{DIVISIONS}/{division['id']}",
        headers=headers,
        json={"name": "Paris Hyper Market Al Khor", "slug": "phm-al-khor"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["slug"] == "phm-al-khor"
    assert body["qr_codes"][0]["slug"] == original_qr_slug


def test_delete_division_cascades_to_qr_codes(
    client: TestClient, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr_id = division["qr_codes"][0]["id"]

    r = client.delete(f"{DIVISIONS}/{division['id']}", headers=headers)
    assert r.status_code == 204, r.text
    assert db_session.get(MarketingQrCode, qr_id) is None


# ---------------------------------------------------------------------------
# QR codes
# ---------------------------------------------------------------------------


def test_add_second_qr_code_to_division(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")

    r = client.post(
        f"{DIVISIONS}/{division['id']}/qr-codes",
        headers=headers,
        json={
            "label": "Shelf Talker",
            "target_url": "https://instagram.com/p/abc",
            "target_kind": "instagram",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slug"] == "al-khor-shelf-talker"
    assert body["target_kind"] == "instagram"
    assert body["target_updated_at"] is not None


def test_qr_slug_is_immutable(client: TestClient, seed_auth):
    """The load-bearing guarantee: no request body can change a slug.

    ``QrCodeUpdate`` has ``extra="forbid"`` and no ``slug`` field, so
    an attempt is a loud 422 rather than a silent no-op.
    """
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]

    r = client.patch(
        f"{QR_CODES}/{qr['id']}", headers=headers, json={"slug": "something-else"}
    )
    assert r.status_code == 422, r.text

    # And the stored slug is untouched.
    r = client.get(f"{QR_CODES}/{qr['id']}", headers=headers)
    assert r.json()["slug"] == qr["slug"]


def test_repoint_qr_target_keeps_slug_and_scan_count(
    client: TestClient, db_session: Session, seed_auth
):
    """Re-pointing is the whole feature — verify it changes only the target."""
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]

    client.patch(
        f"{QR_CODES}/{qr['id']}",
        headers=headers,
        json={"target_url": "https://pug.qa/offers/ramadan", "target_kind": "catalogue"},
    )
    client.get(f"{PUBLIC}/{qr['slug']}", follow_redirects=False)

    r = client.patch(
        f"{QR_CODES}/{qr['id']}",
        headers=headers,
        json={"target_url": "https://youtube.com/watch?v=xyz", "target_kind": "youtube"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["slug"] == qr["slug"]
    assert body["target_url"] == "https://youtube.com/watch?v=xyz"
    # Scan history survives a re-point.
    assert body["scan_count"] == 1


@pytest.mark.parametrize(
    "bad_url",
    [
        "javascript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "ftp://example.com/file",
        "not-a-url",
    ],
)
def test_rejects_non_http_targets(client: TestClient, seed_auth, bad_url: str):
    """Scheme allow-list is a security control — a scan must not run script."""
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]

    r = client.patch(
        f"{QR_CODES}/{qr['id']}", headers=headers, json={"target_url": bad_url}
    )
    assert r.status_code == 422, r.text


def test_rejects_unknown_target_kind(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]
    r = client.patch(
        f"{QR_CODES}/{qr['id']}", headers=headers, json={"target_kind": "carrier-pigeon"}
    )
    assert r.status_code == 422, r.text


def test_qr_slug_conflict_is_409(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    r = client.post(
        f"{DIVISIONS}/{division['id']}/qr-codes",
        headers=headers,
        json={"label": "Duplicate", "slug": division["qr_codes"][0]["slug"]},
    )
    assert r.status_code == 409, r.text


# ---------------------------------------------------------------------------
# Rendered artwork
# ---------------------------------------------------------------------------


def test_qr_png_renders_and_encodes_permanent_url(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]

    r = client.get(f"{QR_CODES}/{qr['id']}/qr-code.png", headers=headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert qr["slug"] in r.headers["content-disposition"]


def test_qr_png_rejects_unsupported_size(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]
    r = client.get(f"{QR_CODES}/{qr['id']}/qr-code.png?size=99999", headers=headers)
    assert r.status_code == 400, r.text


def test_qr_png_download_flag_sets_attachment(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]
    r = client.get(
        f"{QR_CODES}/{qr['id']}/qr-code.png?download=true&size=2048", headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-disposition"].startswith("attachment")


# ---------------------------------------------------------------------------
# Public resolver
# ---------------------------------------------------------------------------


def test_scan_redirects_and_counts(
    client: TestClient, db_session: Session, seed_auth
):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]
    client.patch(
        f"{QR_CODES}/{qr['id']}",
        headers=headers,
        json={"target_url": "https://pug.qa/offers/ramadan"},
    )

    r = client.get(f"{PUBLIC}/{qr['slug']}", follow_redirects=False)
    assert r.status_code == 302, r.text
    assert r.headers["location"] == "https://pug.qa/offers/ramadan"

    db_session.expire_all()
    row = db_session.get(MarketingQrCode, qr["id"])
    assert row.scan_count == 1
    assert row.last_scan_at is not None

    events = (
        db_session.query(MarketingQrScanEvent)
        .filter(MarketingQrScanEvent.qr_code_id == qr["id"])
        .all()
    )
    assert len(events) == 1
    # The snapshot is what keeps history honest after a re-point.
    assert events[0].resolved_url == "https://pug.qa/offers/ramadan"
    # IP is never stored — only a one-way hash.
    assert events[0].session_hash is not None
    assert len(events[0].session_hash) == 64


def test_scan_follows_updated_target(client: TestClient, seed_auth):
    """Same printed code, new destination — the point of the feature."""
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]

    client.patch(
        f"{QR_CODES}/{qr['id']}", headers=headers, json={"target_url": "https://a.example.com/one"}
    )
    first = client.get(f"{PUBLIC}/{qr['slug']}", follow_redirects=False)
    assert first.headers["location"] == "https://a.example.com/one"

    client.patch(
        f"{QR_CODES}/{qr['id']}", headers=headers, json={"target_url": "https://b.example.com/two"}
    )
    second = client.get(f"{PUBLIC}/{qr['slug']}", follow_redirects=False)
    assert second.headers["location"] == "https://b.example.com/two"


def test_inactive_qr_falls_back_instead_of_404(client: TestClient, seed_auth):
    """A printed code must degrade gracefully, never dead-end."""
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]

    client.patch(
        f"{QR_CODES}/{qr['id']}",
        headers=headers,
        json={
            "target_url": "https://a.example.com/live",
            "fallback_url": "https://pug.qa/offers",
            "is_active": False,
        },
    )
    r = client.get(f"{PUBLIC}/{qr['slug']}", follow_redirects=False)
    assert r.status_code == 302, r.text
    assert r.headers["location"] == "https://pug.qa/offers"


def test_falls_back_to_division_url(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(
        client, headers, name="Al Khor", fallback_url="https://pug.qa/branches/al-khor"
    )
    qr = division["qr_codes"][0]

    # No target set at all, and no per-code fallback.
    r = client.get(f"{PUBLIC}/{qr['slug']}", follow_redirects=False)
    assert r.status_code == 302, r.text
    assert r.headers["location"] == "https://pug.qa/branches/al-khor"


def test_inactive_division_disables_its_codes_but_keeps_fallback(
    client: TestClient, seed_auth
):
    """Closing a branch shouldn't need every code disabled by hand."""
    headers = _auth(client, seed_auth["password"])
    division = _make_division(
        client, headers, name="Al Khor", fallback_url="https://pug.qa/branches"
    )
    qr = division["qr_codes"][0]
    client.patch(
        f"{QR_CODES}/{qr['id']}", headers=headers, json={"target_url": "https://a.example.com/live"}
    )
    client.patch(f"{DIVISIONS}/{division['id']}", headers=headers, json={"is_active": False})

    r = client.get(f"{PUBLIC}/{qr['slug']}", follow_redirects=False)
    assert r.status_code == 302, r.text
    assert r.headers["location"] == "https://pug.qa/branches"


def test_no_target_falls_back_to_the_branch_storefront(
    client: TestClient, seed_auth
):
    """The end of the fallback chain is the branch's own offers page.

    A code with nothing configured still lands the shopper somewhere
    relevant — they're standing in that branch — rather than 404ing on
    signage that's already printed.
    """
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]
    r = client.get(f"{PUBLIC}/{qr['slug']}", follow_redirects=False)
    assert r.status_code == 302, r.text
    assert r.headers["location"].endswith(f"/offers/{division['slug']}")


def test_non_public_division_with_no_target_is_404(
    client: TestClient, seed_auth
):
    """No storefront to fall back to → the chain genuinely ends.

    ``is_public=false`` means the branch has no customer-facing page,
    so the automatic fallback must not invent one.
    """
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor", is_public=False)
    qr = division["qr_codes"][0]
    r = client.get(f"{PUBLIC}/{qr['slug']}", follow_redirects=False)
    assert r.status_code == 404, r.text


@pytest.mark.parametrize("slug", ["nope", "a", "UPPER!!", "../etc/passwd"])
def test_unknown_or_malformed_slug_is_404(client: TestClient, slug: str):
    r = client.get(f"{PUBLIC}/{slug}", follow_redirects=False)
    assert r.status_code == 404


def test_scan_is_case_insensitive(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]
    client.patch(
        f"{QR_CODES}/{qr['id']}", headers=headers, json={"target_url": "https://a.example.com/x"}
    )
    r = client.get(f"{PUBLIC}/{qr['slug'].upper()}", follow_redirects=False)
    assert r.status_code == 302, r.text


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


def test_analytics_payload(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]

    client.patch(
        f"{QR_CODES}/{qr['id']}", headers=headers, json={"target_url": "https://a.example.com/one"}
    )
    client.patch(
        f"{QR_CODES}/{qr['id']}", headers=headers, json={"target_url": "https://b.example.com/two"}
    )
    client.get(f"{PUBLIC}/{qr['slug']}", follow_redirects=False)

    r = client.get(f"{QR_CODES}/{qr['id']}/analytics?days=7", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["total_scans"] == 1
    assert body["scans_last_30_days"] == 1
    # Zero-filled series — no gaps for the chart to reason about.
    assert len(body["daily"]) == 7
    assert sum(p["scans"] for p in body["daily"]) == 1
    assert len(body["devices"]) == 1

    # Target history is replayed from the audit log, newest first.
    history = body["target_history"]
    assert len(history) == 2
    assert history[0]["to_url"] == "https://b.example.com/two"
    assert history[0]["from_url"] == "https://a.example.com/one"
    assert history[1]["from_url"] is None
    assert history[0]["actor_email"] == "superadmin@pug.example.com"


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_marketing_viewer_can_read_but_not_write(client: TestClient, seed_auth):
    viewer = _auth(
        client, seed_auth["password"], email="marketingviewer@pug.example.com"
    )
    manager = _auth(
        client, seed_auth["password"], email="marketingmgr@pug.example.com"
    )

    created = _make_division(client, manager, name="Al Khor")

    r = client.get(DIVISIONS, headers=viewer)
    assert r.status_code == 200, r.text

    r = client.post(DIVISIONS, headers=viewer, json={"name": "Sneaky Branch"})
    assert r.status_code == 403, r.text

    qr_id = created["qr_codes"][0]["id"]
    r = client.patch(
        f"{QR_CODES}/{qr_id}", headers=viewer, json={"target_url": "https://evil.example.com"}
    )
    assert r.status_code == 403, r.text

    r = client.delete(f"{DIVISIONS}/{created['id']}", headers=viewer)
    assert r.status_code == 403, r.text


def test_marketing_manager_has_full_access(client: TestClient, seed_auth):
    manager = _auth(client, seed_auth["password"], email="marketingmgr@pug.example.com")
    division = _make_division(client, manager, name="Al Wakra")
    qr_id = division["qr_codes"][0]["id"]

    r = client.patch(
        f"{QR_CODES}/{qr_id}", headers=manager, json={"target_url": "https://pug.qa/offers"}
    )
    assert r.status_code == 200, r.text

    r = client.get(f"{QR_CODES}/{qr_id}/qr-code.png", headers=manager)
    assert r.status_code == 200, r.text


def test_public_resolver_needs_no_auth(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    division = _make_division(client, headers, name="Al Khor")
    qr = division["qr_codes"][0]
    client.patch(
        f"{QR_CODES}/{qr['id']}", headers=headers, json={"target_url": "https://a.example.com/x"}
    )
    # No Authorization header at all.
    r = client.get(f"{PUBLIC}/{qr['slug']}", follow_redirects=False)
    assert r.status_code == 302, r.text


# ---------------------------------------------------------------------------
# Branch storefront (public /offers/branch/{slug})
# ---------------------------------------------------------------------------


PUBLIC_OFFERS = "/api/v1/offers"


def test_branch_page_carries_identity_and_contact(client: TestClient, seed_auth):
    """The storefront payload feeds the page header + footer."""
    headers = _auth(client, seed_auth["password"])
    division = _make_division(
        client,
        headers,
        name="Paris Hyper Market Al Attiya",
        city="Industrial Area",
        address="Street 12, Industrial Area, Doha, Qatar",
        phone="+974 4000 0000",
        instagram_url="https://instagram.com/parishypermarket",
        facebook_url="https://facebook.com/parishypermarket",
    )

    r = client.get(f"{PUBLIC_OFFERS}/branch/{division['slug']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Paris Hyper Market Al Attiya"
    assert body["city"] == "Industrial Area"
    assert body["address"].startswith("Street 12")
    assert body["social"]["instagram"] == "https://instagram.com/parishypermarket"
    assert body["social"]["facebook"] == "https://facebook.com/parishypermarket"
    # Unset socials come back as null rather than being omitted, so the
    # client can render a stable set of slots.
    assert body["social"]["tiktok"] is None


def test_branch_page_lists_sibling_branches(client: TestClient, seed_auth):
    """Powers the "switch branch" control without a second request."""
    headers = _auth(client, seed_auth["password"])
    a = _make_division(client, headers, name="Al Attiya")
    _make_division(client, headers, name="Al Khor")
    _make_division(client, headers, name="Al Wakra")

    body = client.get(f"{PUBLIC_OFFERS}/branch/{a['slug']}").json()
    slugs = {b["slug"] for b in body["other_branches"]}
    assert slugs == {"al-khor", "al-wakra"}
    assert a["slug"] not in slugs


def test_branch_page_404s_when_not_public(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    d = _make_division(client, headers, name="Backoffice Only", is_public=False)
    assert client.get(f"{PUBLIC_OFFERS}/branch/{d['slug']}").status_code == 404


def test_branch_page_404s_for_unknown_slug(client: TestClient):
    assert client.get(f"{PUBLIC_OFFERS}/branch/nope-not-here").status_code == 404


def test_branch_picker_lists_divisions(client: TestClient, seed_auth):
    """The picker comes from divisions, not scraped campaign labels.

    A branch with zero campaigns must still be reachable — that's the
    whole point of sourcing this from the branches table.
    """
    headers = _auth(client, seed_auth["password"])
    _make_division(client, headers, name="Al Khor", city="Al Khor")
    _make_division(client, headers, name="Hidden", is_public=False)

    body = client.get(PUBLIC_OFFERS).json()
    picker = {b["slug"]: b for b in body["branches"]}
    assert "al-khor" in picker
    assert picker["al-khor"]["name"] == "Al Khor"
    assert picker["al-khor"]["city"] == "Al Khor"
    # Non-public branches must not be advertised.
    assert "hidden" not in picker

    # Same list is available standalone for clients that only need it.
    standalone = client.get(f"{PUBLIC_OFFERS}/branches").json()
    assert {b["slug"] for b in standalone} == set(picker)


def test_branches_route_is_not_read_as_a_campaign_slug(client: TestClient):
    """Regression: ``/offers/branches`` must not hit ``/offers/{slug}``.

    Both are single-segment paths, so the literal has to be declared
    first or the picker endpoint 404s as a missing campaign.
    """
    r = client.get(f"{PUBLIC_OFFERS}/branches")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_branch_location_qr_encodes_the_maps_link(client: TestClient, seed_auth):
    """The footer QR must open directions, not the branch page.

    A map link is a fixed physical fact about the store, so it's
    encoded directly rather than routed through /q/ — there is nothing
    to re-point later.
    """
    import io

    import cv2
    import numpy as np
    from PIL import Image

    headers = _auth(client, seed_auth["password"])
    maps = "https://maps.app.goo.gl/abc123"
    d = _make_division(client, headers, name="Al Attiya", maps_url=maps)

    r = client.get(f"{PUBLIC_OFFERS}/branch/{d['slug']}/location-qr.png")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png"
    # Public + long-lived: served to every visitor, effectively static.
    assert "public" in r.headers["cache-control"]

    img = np.array(Image.open(io.BytesIO(r.content)).convert("RGB"))[:, :, ::-1]
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    assert decoded == maps, f"expected the maps link, got {decoded!r}"


def test_branch_location_qr_404s_without_a_maps_link(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    d = _make_division(client, headers, name="No Map Branch")
    r = client.get(f"{PUBLIC_OFFERS}/branch/{d['slug']}/location-qr.png")
    assert r.status_code == 404, r.text


def test_branch_location_qr_404s_for_non_public_branch(client: TestClient, seed_auth):
    headers = _auth(client, seed_auth["password"])
    d = _make_division(
        client,
        headers,
        name="Private",
        is_public=False,
        maps_url="https://maps.app.goo.gl/x",
    )
    r = client.get(f"{PUBLIC_OFFERS}/branch/{d['slug']}/location-qr.png")
    assert r.status_code == 404, r.text
