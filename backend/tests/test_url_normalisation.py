"""Round-trip: backslash in any *_url field is normalised on write.

Admins occasionally paste a Windows file path (e.g.
``\\images\\foo\\bar.webp``) into an image URL on the admin forms.
The value would otherwise survive the form and reach the public
site, where the browser renders it as a relative URL with backslashes
that 404s. The schemas in :mod:`app.schemas.cms` apply a normalisation
validator that swaps backslashes for forward slashes on every field
ending in ``_url``.
"""
from __future__ import annotations

import pytest

from app.schemas.cms import CompanyCreate, CompanyUpdate, LeadershipCreate, LeadershipUpdate


def _company_payload(**overrides):
    base = {
        "slug": "test-co",
        "name": "Test Co",
        "category": "retail",
        "initials": "TC",
        "accent": "from-pug-green-500 to-pug-gold-500",
    }
    base.update(overrides)
    return base


def test_company_create_normalises_backslashes_in_image_urls():
    payload = _company_payload(
        featured_image_url="\\images\\foo\\bar.webp",
        brand_logo_url="\\uploads\\logo.png",
    )
    model = CompanyCreate(**payload)
    assert model.featured_image_url == "/images/foo/bar.webp"
    assert model.brand_logo_url == "/uploads/logo.png"


def test_company_update_normalises_backslashes_in_image_urls():
    model = CompanyUpdate(featured_image_url="\\images\\Nihad\\Untitled.webp")
    assert model.featured_image_url == "/images/Nihad/Untitled.webp"


def test_leadership_create_normalises_photo_url():
    model = LeadershipCreate(
        slug="ceo",
        name="Test Leader",
        role="CEO",
        initials="TL",
        photo_url="\\photos\\team\\ceo.jpg",
    )
    assert model.photo_url == "/photos/team/ceo.jpg"


def test_leadership_update_normalises_signature_image_url():
    model = LeadershipUpdate(signature_image_url="\\assets\\sig.png")
    assert model.signature_image_url == "/assets/sig.png"


def test_unchanged_when_no_backslash():
    """No-op when the input is already a clean URL."""
    payload = _company_payload(
        featured_image_url="/api/v1/uploads/cms/abc.webp",
        brand_logo_url="https://cdn.example.com/logo.png",
    )
    model = CompanyCreate(**payload)
    assert model.featured_image_url == "/api/v1/uploads/cms/abc.webp"
    assert model.brand_logo_url == "https://cdn.example.com/logo.png"


def test_handles_none_values():
    """Null / missing URLs round-trip as null — validator never crashes."""
    payload = _company_payload(featured_image_url=None, brand_logo_url=None)
    model = CompanyCreate(**payload)
    assert model.featured_image_url is None
    assert model.brand_logo_url is None
