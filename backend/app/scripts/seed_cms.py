"""Seed the CMS tables with the same dummy content the public site
shows in Phase 4 (hero slides, companies, leadership, news, site
settings).

Run from /backend with the venv active and migrations applied:

    python -m app.scripts.seed_cms

The script is idempotent: rerunning it will refresh existing rows
keyed by slug rather than duplicating data.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.cms import (
    Company,
    CompanyService,
    HeroSlide,
    LeadershipMessage,
    NewsItem,
    SiteSetting,
    TrustedBrand,
)


HERO_SLIDES = [
    dict(
        eyebrow="Paris United Group Holding",
        title="Powering everyday life across the GCC.",
        description=(
            "Retail, distribution, FMCG, fashion, packaging, fresh food, "
            "building materials, garages, real estate, and construction — "
            "all under one trusted group."
        ),
        cta_label="Explore the group",
        cta_href="/companies",
        secondary_cta_label="Contact us",
        secondary_cta_href="/contact",
        background_video_url="/video/home/paris_group_banner.mp4",
        background_image_url="/images/home/home_banner.jpg",
        gradient="from-pug-green-800 via-pug-green-600 to-pug-gold-500",
        display_order=1,
        is_active=True,
    ),
    dict(
        eyebrow="Retail · Distribution · Services",
        title="Customer experience is the product.",
        description=(
            "Hypermarkets, minimarts, grocery shops, garages, and real estate "
            "— designed around what families and businesses actually need every day."
        ),
        cta_label="Our companies",
        cta_href="/companies",
        secondary_cta_label="Latest news",
        secondary_cta_href="/news",
        background_image_url="/images/home/offers/home_journey.jpg",
        gradient="from-pug-gold-700 via-pug-gold-500 to-pug-green-500",
        display_order=2,
        is_active=True,
    ),
    dict(
        eyebrow="Build your career",
        title="Talented teams, real impact.",
        description=(
            "Join one of Qatar's most diversified groups. Roles open across "
            "retail operations, FMCG sales, engineering, real estate, and HR."
        ),
        cta_label="View open roles",
        cta_href="/careers",
        secondary_cta_label="About us",
        secondary_cta_href="/about",
        background_image_url="/images/home/career/career_banner.jpg",
        gradient="from-pug-green-600 via-pug-green-500 to-pug-gold-600",
        display_order=3,
        is_active=True,
    ),
]


COMPANIES = [
    {
        "slug": "paris-food-international",
        "name": "Paris Food International",
        "category": "distribution",
        "short_description": "FMCG wholesale, department store supply, and HORECA supply.",
        "long_description": "Paris Food International is the group's flagship FMCG distribution arm…",
        "accent": "from-pug-green-500 to-pug-gold-500",
        "initials": "PF",
        "featured_image_url": "/images/home/services/service_02.jpg",
        "services": ["FMCG wholesale", "Department store supply", "HORECA supply"],
    },
    {
        "slug": "doha-fashion",
        "name": "Doha Fashion",
        "category": "distribution",
        "short_description": "Cosmetics and stationery distribution.",
        "long_description": "Doha Fashion brings global cosmetics and stationery brands to retailers across the region.",
        "accent": "from-pug-gold-500 to-pug-gold-700",
        "initials": "DF",
        "services": ["Cosmetics", "Stationery", "Brand activation"],
    },
    {
        "slug": "paris-packing",
        "name": "Paris Packing",
        "category": "distribution",
        "short_description": "Packing items, pulses, and spices distribution.",
        "long_description": "Paris Packing supplies wholesale and retail customers with packaged pulses, spices, and packing solutions.",
        "accent": "from-pug-gold-600 to-pug-gold-800",
        "initials": "PP",
        "services": ["Packing items", "Pulses", "Spices"],
    },
    {
        "slug": "maharib-fresh-trading",
        "name": "Maharib Fresh Trading",
        "category": "distribution",
        "short_description": "Vegetable supply and fresh produce trading.",
        "long_description": "Maharib Fresh Trading sources vegetables and fresh produce from trusted growers.",
        "accent": "from-pug-green-500 to-pug-green-700",
        "initials": "MF",
        "services": ["Vegetable supply", "Fresh produce", "Cold chain logistics"],
    },
    {
        "slug": "yellowtech-trading",
        "name": "YellowTech Trading and Contracting",
        "category": "distribution",
        "short_description": "Building materials supply and contracting.",
        "long_description": "YellowTech Trading and Contracting supplies building materials and delivers contracting services.",
        "accent": "from-pug-gold-500 to-pug-gold-700",
        "initials": "YT",
        "services": ["Building materials supply", "Contracting", "MEP works"],
    },
    {
        "slug": "paris-hyper-market",
        "name": "Paris Hyper Market",
        "category": "retail",
        "short_description": "Modern hypermarkets serving families across Qatar and KSA.",
        "long_description": "Paris Hyper Market is the group's flagship hypermarket chain.",
        "branches": "4 branches in Qatar · 1 branch in KSA",
        "accent": "from-pug-gold-500 to-pug-gold-700",
        "initials": "PH",
        "featured_image_url": "/images/home/services/service_01.jpg",
        "services": ["Grocery", "Fresh food", "Household", "Electronics"],
    },
    {
        "slug": "paris-express",
        "name": "Paris Express",
        "category": "retail",
        "short_description": "Neighbourhood minimarts for everyday essentials.",
        "long_description": "Paris Express minimarts bring everyday essentials closer to home.",
        "branches": "Above 6 branches",
        "accent": "from-pug-green-500 to-pug-gold-500",
        "initials": "PE",
        "services": ["Minimarts", "Daily essentials", "Convenience"],
    },
    {
        "slug": "al-mihrab-groceries",
        "name": "Al Mihrab Groceries",
        "category": "retail",
        "short_description": "A chain of neighbourhood grocery shops with over 45 stores.",
        "long_description": "Al Mihrab Groceries operates a network of community grocery shops across Qatar.",
        "branches": "Above 45 shops",
        "accent": "from-pug-green-600 to-pug-gold-500",
        "initials": "AM",
        "services": ["Grocery", "Beverages", "Household goods"],
    },
    {
        "slug": "maharib-fish",
        "name": "Maharib Fish",
        "category": "retail",
        "short_description": "Fresh fish supply to retail and wholesale customers.",
        "long_description": "Maharib Fish supplies fresh seafood to retailers, restaurants, and households.",
        "accent": "from-pug-green-500 to-pug-green-700",
        "initials": "MF",
        "services": ["Fresh fish", "Shellfish", "Wholesale supply"],
    },
    {
        "slug": "yellowtech-garage",
        "name": "YellowTech Garage",
        "category": "services",
        "short_description": "Light vehicle garage and service centre.",
        "long_description": "YellowTech Garage offers full-service light vehicle maintenance.",
        "accent": "from-pug-gold-500 to-pug-gold-700",
        "initials": "YG",
        "featured_image_url": "/images/home/services/service_03.jpg",
        "services": ["Vehicle maintenance", "Diagnostics", "Body work"],
    },
    {
        "slug": "express-diesel-turbo",
        "name": "Express Diesel Turbo",
        "category": "services",
        "short_description": "Specialist diesel and hydraulic garage.",
        "long_description": "Express Diesel Turbo is the group's heavy-duty specialist.",
        "accent": "from-pug-green-700 to-pug-green-800",
        "initials": "ED",
        "services": ["Diesel engines", "Turbochargers", "Hydraulic systems"],
    },
    {
        "slug": "auto-plux-car-service",
        "name": "Auto Plux Car Service",
        "category": "services",
        "short_description": "Quick-fix car garage for fast service jobs.",
        "long_description": "Auto Plux Car Service is a quick-fix garage focused on speed.",
        "accent": "from-pug-green-500 to-pug-gold-500",
        "initials": "AP",
        "services": ["Quick service", "Tyres", "Batteries", "AC service"],
    },
    {
        "slug": "greentech-real-estate",
        "name": "Greentech Real Estate Broker",
        "category": "services",
        "short_description": "Real estate brokerage and property advisory.",
        "long_description": "Greentech Real Estate Broker advises buyers, sellers, and tenants.",
        "accent": "from-pug-green-500 to-pug-green-700",
        "initials": "GR",
        "featured_image_url": "/images/home/services/service_04.jpg",
        "services": ["Property sales", "Leasing", "Investment advisory"],
    },
    {
        "slug": "core-engineering",
        "name": "Core Engineering and Construction",
        "category": "services",
        "short_description": "Construction, fit-outs, and engineering services.",
        "long_description": "Core Engineering and Construction delivers turnkey construction projects.",
        "accent": "from-pug-gold-600 to-pug-gold-800",
        "initials": "CE",
        "featured_image_url": "/images/home/services/service_05.jpg",
        "services": ["Construction", "Fit-outs", "Engineering services"],
    },
]


LEADERSHIP = [
    {
        "slug": "chairman",
        "name": "Mr. A. Al Hassan",
        "role": "Chairman & Founder",
        "short_message": "Our purpose is to serve communities with quality products and trusted service.",
        "full_message": "When we founded Paris United Group, we set out to build a company that families could rely on.",
        "accent": "from-pug-green-600 to-pug-gold-500",
        "initials": "AH",
        "photo_url": "/images/ourcompany/ceo_img.png",
        "signature": "Mr. A. Al Hassan",
        "role_label": "Chairman's message",
        "highlight_quote": (
            "We don't just build businesses — we build trust. Every store, every "
            "supplier, every customer interaction is part of the same promise."
        ),
        "message_paragraph_1": (
            "When we founded Paris United Group, we set out to build a company "
            "that families across the GCC could rely on for the things that "
            "matter every day — fresh food on the table, reliable services "
            "around the corner, and dignity at work for everyone we hire."
        ),
        "message_paragraph_2": (
            "Decades later, that purpose hasn't changed. It's the reason our "
            "hypermarkets, garages, and distribution arms still feel like they "
            "belong to the same family — because they do."
        ),
        "is_homepage_featured": True,
        "display_order": 1,
    },
    {
        "slug": "md",
        "name": "Mr. K. Rahman",
        "role": "Managing Director",
        "short_message": "Operational excellence and customer obsession are how we turn strategy into results.",
        "full_message": "Running a diversified group means making thoughtful decisions every single day.",
        "accent": "from-pug-green-700 to-pug-gold-500",
        "initials": "KR",
        "photo_url": "/images/ourcompany/member1.png",
        "signature": "Mr. K. Rahman",
        "role_label": "Managing director's message",
        "highlight_quote": (
            "Operational excellence is invisible when it's done right — that's "
            "exactly what our teams aim for, every shift, every day."
        ),
        "message_paragraph_1": (
            "Across distribution, retail, services, and engineering, we share "
            "one playbook: serve the customer first, give our teams the tools "
            "to win, and measure what matters. That clarity is how a "
            "diversified group still moves with focus."
        ),
        "message_paragraph_2": (
            "I'm proud of the way our people show up — at 6am in the warehouse, "
            "behind the till on a Friday afternoon, on a construction site in "
            "Doha's summer heat. The group's results are theirs."
        ),
        "is_homepage_featured": True,
        "display_order": 2,
    },
    {
        "slug": "ed-retail",
        "name": "Ms. S. Khan",
        "role": "Executive Director – Retail",
        "short_message": "Retail is detail. Every shelf, every till, every interaction is a chance to delight.",
        "full_message": "Across Paris Hyper Market, Paris Express, Al Mihrab, and Maharib Fish we serve hundreds of thousands every week.",
        "accent": "from-pug-gold-500 to-pug-gold-700",
        "initials": "SK",
        "photo_url": "/images/ourcompany/member2.png",
        "signature": "Ms. S. Khan",
        "display_order": 3,
    },
    {
        "slug": "ed-distribution",
        "name": "Mr. R. Iyer",
        "role": "Executive Director – Distribution",
        "short_message": "Reliable distribution is invisible when it works.",
        "full_message": "Our distribution businesses move FMCG, fresh produce, packaging, and building materials.",
        "accent": "from-pug-green-500 to-pug-green-700",
        "initials": "RI",
        "photo_url": "/images/ourcompany/member3.png",
        "signature": "Mr. R. Iyer",
        "display_order": 4,
    },
]


NEWS = [
    {
        "slug": "paris-united-group-opens-fifth-hypermarket",
        "title": "Paris United Group opens its fifth hypermarket",
        "summary": "A new Paris Hyper Market opens its doors in Lusail.",
        "body": "Paris United Group Holding today announced the opening of its fifth hypermarket in Lusail.",
        "category": "company",
        "author": "Group Communications",
        "cover": "from-pug-gold-500 to-pug-green-500",
        "cover_image_url": "/images/news/news_01.png",
        "published_at": datetime(2026, 5, 12, tzinfo=timezone.utc),
        "is_featured": True,
    },
    {
        "slug": "yellowtech-garage-launches-ev-service",
        "title": "YellowTech Garage launches EV maintenance",
        "summary": "Certified technicians, dedicated bays, OEM-approved tools.",
        "body": "YellowTech Garage has invested in dedicated EV service bays.",
        "category": "company",
        "author": "Group Communications",
        "cover": "from-pug-gold-500 to-pug-gold-700",
        "cover_image_url": "/images/news/news_02.png",
        "published_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
    },
    {
        "slug": "csr-back-to-school-2026",
        "title": "Back to School 2026 CSR drive distributes 5,000 kits",
        "summary": "Doha Fashion and Al Mihrab Groceries partnered with local schools.",
        "body": "Through a coordinated CSR initiative, Doha Fashion and Al Mihrab Groceries distributed 5,000 kits.",
        "category": "csr",
        "author": "Group CSR",
        "cover": "from-pug-green-500 to-pug-gold-500",
        "cover_image_url": "/images/news/news_03.png",
        "published_at": datetime(2026, 4, 15, tzinfo=timezone.utc),
    },
    {
        "slug": "maharib-fresh-cold-chain-upgrade",
        "title": "Maharib Fresh completes cold-chain upgrade",
        "summary": "New refrigerated trucks extend shelf life by up to 25%.",
        "body": "Maharib Fresh Trading has finished a multi-month cold-chain upgrade.",
        "category": "company",
        "author": "Group Communications",
        "cover": "from-pug-green-500 to-pug-green-700",
        "cover_image_url": "/images/news/news_04.png",
        "published_at": datetime(2026, 3, 22, tzinfo=timezone.utc),
    },
    {
        "slug": "annual-leadership-summit-2026",
        "title": "Annual leadership summit gathers all divisions",
        "summary": "Executives aligned on the 2026 group strategy.",
        "body": "Paris United Group Holding hosted its annual leadership summit.",
        "category": "event",
        "author": "Group Communications",
        "cover": "from-pug-green-600 to-pug-gold-500",
        "cover_image_url": "/images/news/news_05.png",
        "published_at": datetime(2026, 2, 18, tzinfo=timezone.utc),
        "is_featured": True,
    },
    {
        "slug": "core-engineering-wins-fitout-contract",
        "title": "Core Engineering wins major fit-out contract",
        "summary": "A multi-floor commercial fit-out in Doha.",
        "body": "Core Engineering and Construction has been awarded a multi-floor commercial fit-out project.",
        "category": "press",
        "author": "Group Communications",
        "cover": "from-pug-gold-600 to-pug-gold-800",
        "cover_image_url": "/images/news/news_01.png",
        "published_at": datetime(2026, 1, 30, tzinfo=timezone.utc),
    },
]


def _upsert_hero_slides(db: Session) -> int:
    db.query(HeroSlide).delete()
    for data in HERO_SLIDES:
        db.add(HeroSlide(**data))
    db.flush()
    return len(HERO_SLIDES)


HIGHLIGHTED_SLUGS = {
    "paris-hyper-market",
    "paris-food-international",
    "yellowtech-garage",
    "greentech-real-estate",
}


def _upsert_companies(db: Session) -> int:
    existing = {c.slug: c for c in db.execute(select(Company)).scalars()}
    for idx, data in enumerate(COMPANIES):
        services = data.pop("services")
        slug = data["slug"]
        # Mark the curated highlighted slugs (idempotent — admin can
        # toggle later from the UI without us reverting it on re-seed).
        data.setdefault("is_highlighted", slug in HIGHLIGHTED_SLUGS)
        data.setdefault("display_order", idx)
        company = existing.get(slug)
        if company is None:
            company = Company(**data)
            db.add(company)
        else:
            for k, v in data.items():
                setattr(company, k, v)
            company.services.clear()
        db.flush()
        for i, name in enumerate(services):
            db.add(CompanyService(company_id=company.id, name=name, display_order=i))
    db.flush()
    return len(COMPANIES)


def _upsert_leadership(db: Session) -> int:
    existing = {l.slug: l for l in db.execute(select(LeadershipMessage)).scalars()}
    for data in LEADERSHIP:
        slug = data["slug"]
        row = existing.get(slug)
        if row is None:
            db.add(LeadershipMessage(**data))
        else:
            for k, v in data.items():
                setattr(row, k, v)
    db.flush()
    return len(LEADERSHIP)


TRUSTED_BRANDS = [
    {"brand_name": "Paris Hyper Market", "logo_url": "/images/home/brands/brand_01.png"},
    {"brand_name": "Paris Express", "logo_url": "/images/home/brands/brand_02.png"},
    {"brand_name": "Al Mihrab Grocery", "logo_url": "/images/home/brands/brand_03.png"},
    {"brand_name": "Doha Fashion", "logo_url": "/images/home/brands/brand_04.png"},
    {"brand_name": "Greentech W.L.L", "logo_url": "/images/home/brands/brand_05.png"},
    {"brand_name": "Paris Packing", "logo_url": "/images/home/brands/brand_06.png"},
    {"brand_name": "YellowTech Garage", "logo_url": "/images/home/brands/brand_07.png"},
    {"brand_name": "Maharib Fish", "logo_url": "/images/home/brands/brand_08.png"},
    {"brand_name": "Paris Estates", "logo_url": "/images/home/brands/brand_09.png"},
    {"brand_name": "Paris Build", "logo_url": "/images/home/brands/brand_10.png"},
]


def _upsert_trusted_brands(db: Session) -> int:
    existing = {b.brand_name: b for b in db.execute(select(TrustedBrand)).scalars()}
    for order, data in enumerate(TRUSTED_BRANDS, start=1):
        payload = {**data, "display_order": order, "is_active": True}
        row = existing.get(data["brand_name"])
        if row is None:
            db.add(TrustedBrand(**payload))
        else:
            for k, v in payload.items():
                setattr(row, k, v)
    db.flush()
    return len(TRUSTED_BRANDS)


def _upsert_news(db: Session) -> int:
    existing = {n.slug: n for n in db.execute(select(NewsItem)).scalars()}
    for data in NEWS:
        slug = data["slug"]
        row = existing.get(slug)
        if row is None:
            db.add(NewsItem(**data))
        else:
            for k, v in data.items():
                setattr(row, k, v)
    db.flush()
    return len(NEWS)


BRAND_LOGOS_DEFAULT = "\n".join(
    f"/images/home/brands/brand_{i:02d}.png" for i in range(1, 11)
)

HOME_ABOUT_BODY_DEFAULT = (
    "Paris United Group Holding has grown from a single family business into "
    "one of Qatar's most diversified groups — operating across retail, "
    "distribution, fresh food, packaging, garages, real estate, and "
    "construction. We are guided every day by quality, trust, and the "
    "communities we serve."
)

HOME_FOUNDER_MESSAGE_DEFAULT = (
    "When we started Paris United Group, we set out to build something "
    "families could rely on. Decades later, every shelf, every shipment, and "
    "every project still reflects that promise."
)


SITE_SETTINGS_DEFAULTS = dict(
    site_name="Paris United Group Holding",
    tagline="A diversified group across retail, distribution, and services.",
    contact_phone="+974 0000 0000",
    contact_email="info@parisunitedgroup.example.com",
    contact_address="Doha, Qatar",
    whatsapp_number="+97400000000",
    social_linkedin="https://www.linkedin.com/",
    # Page banners
    about_banner_image_url="/images/ourcompany/ourvision.png",
    about_banner_video_url="/video/our-company/about_banner.mp4",
    careers_banner_image_url="/images/career/career_banner.png",
    careers_banner_mobile_url="/images/career/careerbanner_mob.png",
    contact_banner_image_url="/images/contact/contactusbanner.png",
    contact_banner_mobile_url="/images/contact/contactusbannermob.png",
    news_banner_image_url="/images/news/news_banner.png",
    news_banner_mobile_url="/images/news/newsbanner_mob.png",
    # Homepage About + Founder sections
    home_about_image_url="/images/home/about/home_about.jpg",
    home_about_title="Building everyday life across the GCC",
    home_about_body=HOME_ABOUT_BODY_DEFAULT,
    home_founder_image_url="/images/home/founder/founder.jpg",
    home_founder_name="Mr. A. Al Hassan",
    home_founder_role="Chairman & Founder",
    home_founder_message=HOME_FOUNDER_MESSAGE_DEFAULT,
    # Trusted-brands strip
    home_brand_logos=BRAND_LOGOS_DEFAULT,
    home_brand_strip_title="Trusted brands we work with",
    # Unified Leadership Messages section
    home_leadership_section_enabled=True,
    home_leadership_section_eyebrow="Leadership messages",
    home_leadership_section_title="Guided by vision, driven by excellence",
    home_leadership_section_subtitle=(
        "A message from the leadership of Paris United Group Holding."
    ),
    home_leadership_animation_enabled=True,
)


def _upsert_site_settings(db: Session) -> None:
    settings = db.get(SiteSetting, 1)
    if settings is None:
        settings = SiteSetting(id=1, **SITE_SETTINGS_DEFAULTS)
        db.add(settings)
        db.flush()
    else:
        # Only fill in fields that are still empty — never overwrite admin
        # edits when the seed script is re-run.
        for key, value in SITE_SETTINGS_DEFAULTS.items():
            current = getattr(settings, key, None)
            if current in (None, ""):
                setattr(settings, key, value)
        db.flush()


def seed(db: Session) -> None:
    slides = _upsert_hero_slides(db)
    companies = _upsert_companies(db)
    leadership = _upsert_leadership(db)
    brands = _upsert_trusted_brands(db)
    news = _upsert_news(db)
    _upsert_site_settings(db)
    db.commit()

    print("CMS seed complete.")
    print(f"  hero_slides         : {slides}")
    print(f"  companies           : {companies}")
    print(f"  leadership_messages : {leadership}")
    print(f"  trusted_brands      : {brands}")
    print(f"  news_items          : {news}")
    print(f"  site_settings       : 1 (id=1)")


def main(argv: Sequence[str] | None = None) -> int:
    db = SessionLocal()
    try:
        seed(db)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
