"""SEO service helpers.

Two responsibilities:

  1. **Sanitisation** — admin-pasted meta tags / full `<meta>` snippets
     must never carry executable HTML. The helpers here normalise
     incoming strings, extract just the (name, content) tuples, and
     reject anything that smells like script injection.

  2. **Snippet builders** — turn provider IDs into ready-to-render
     script / iframe strings, so the public layout can just concat
     instead of templating. Frontends use Next's `<Script>` for
     injection where possible; the snippet builders here are also
     used to render the iframes that go into the body-start slot,
     and to power the admin "preview" panels.

Nothing in this file talks to the DB — it's pure functions so it's
trivial to unit-test.
"""
from __future__ import annotations

import html
import re
from typing import Dict, Iterable, List, Optional, Tuple

from app.models.seo import (
    PLACEMENT_BODY_START,
    PLACEMENT_HEAD,
    PROVIDER_CLARITY,
    PROVIDER_GA4,
    PROVIDER_GTM,
    PROVIDER_LINKEDIN,
    PROVIDER_META_PIXEL,
    PROVIDER_TIKTOK,
    PROVIDER_X,
    SeoSetting,
    SeoVerification,
    TrackingIntegration,
    VERIFICATION_TYPE_FULL_META,
    VERIFICATION_TYPE_HTML_FILE,
    VERIFICATION_TYPE_META,
)
from app.schemas.seo import (
    CLARITY_ID_RE,
    GA4_ID_RE,
    GTM_ID_RE,
    LINKEDIN_ID_RE,
    META_PIXEL_ID_RE,
    PublicTrackingIntegration,
    PublicVerificationMeta,
    TIKTOK_ID_RE,
    X_ID_RE,
)


# ---------------------------------------------------------------------------
# Sanitisation
# ---------------------------------------------------------------------------

# Words that should never appear in an admin-pasted meta-tag attribute.
# We refuse the input outright rather than try to "clean" it — that's
# the safer default for security-sensitive surfaces.
_FORBIDDEN_SUBSTRINGS = ("<script", "javascript:", "onerror=", "onload=", "onclick=")

# Restrict the `name`/`property` attribute to the small set of known
# verification keys. This list is the union of what each major search
# engine / ads platform documents. New providers can be added in code
# review — admins can't sneak arbitrary names through the form.
ALLOWED_VERIFICATION_NAMES = frozenset(
    n.lower()
    for n in (
        "google-site-verification",
        "msvalidate.01",  # Bing
        "facebook-domain-verification",
        "p:domain_verify",  # Pinterest
        "yandex-verification",
        "norton-safeweb-site-verification",
        "alexaVerifyID",
        "tiktok-developers-site-verification",
        "linkedin-developers-site-verification",
        "microsoft-advertising-validation",
    )
)


class MetaSanitiseError(ValueError):
    """Raised when an admin-pasted meta tag fails sanitisation."""


def sanitize_meta_tag(raw: str) -> Tuple[str, str, Optional[str]]:
    """Validate a pasted `<meta>` snippet and return ``(attr, name, content)``.

    Accepts either ``name="..."`` or ``property="..."`` style metas
    and returns ``attr`` set to ``"name"`` or ``"property"`` so the
    caller can rebuild the tag in clean HTML themselves rather than
    re-emitting the admin's exact paste.

    Raises :class:`MetaSanitiseError` if the input contains forbidden
    substrings, fails to parse, or names a key outside the allow-list.
    """
    if not raw:
        raise MetaSanitiseError("Empty meta tag")
    cleaned = raw.strip()
    lower = cleaned.lower()
    for bad in _FORBIDDEN_SUBSTRINGS:
        if bad in lower:
            raise MetaSanitiseError(
                f"Meta tag contains forbidden substring: {bad!r}"
            )
    match = re.search(
        r"<meta\b[^>]*?\b(name|property)\s*=\s*[\"']([^\"']+)[\"'][^>]*?\bcontent\s*=\s*[\"']([^\"']*)[\"']",
        cleaned,
        flags=re.IGNORECASE,
    )
    if not match:
        # Try the reverse attribute order — `content="..." name="..."`.
        match = re.search(
            r"<meta\b[^>]*?\bcontent\s*=\s*[\"']([^\"']*)[\"'][^>]*?\b(name|property)\s*=\s*[\"']([^\"']+)[\"']",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not match:
            raise MetaSanitiseError(
                "Couldn't find a name/property + content pair on the meta tag"
            )
        content, attr, name = match.group(1), match.group(2), match.group(3)
    else:
        attr, name, content = match.group(1), match.group(2), match.group(3)
    attr_lower = attr.lower()
    name_lower = name.strip().lower()
    if name_lower not in ALLOWED_VERIFICATION_NAMES:
        raise MetaSanitiseError(
            f"Unrecognised verification name {name!r}. Allowed: {sorted(ALLOWED_VERIFICATION_NAMES)}"
        )
    return attr_lower, name_lower, content


def render_meta_tag(attr: str, name: str, content: str) -> str:
    """Render a single sanitised meta tag with HTML-escaped values."""
    return (
        f'<meta {attr}="{html.escape(name, quote=True)}" '
        f'content="{html.escape(content, quote=True)}" />'
    )


# ---------------------------------------------------------------------------
# Verification list helpers
# ---------------------------------------------------------------------------


def public_verification_metas(
    verifications: Iterable[SeoVerification],
) -> List[PublicVerificationMeta]:
    """Build the list of meta tags the public layout should inject.

    Only honours ``is_active=True`` rows. ``meta_tag`` rows use the
    explicit (name, content) pair; ``full_meta_tag`` rows are run
    through :func:`sanitize_meta_tag` so we never emit admin-supplied
    HTML attributes. ``html_file`` and ``dns_txt`` rows are skipped
    here — they're surfaced separately (verification-file route + DNS
    reference text).
    """
    out: List[PublicVerificationMeta] = []
    for record in verifications:
        if not record.is_active:
            continue
        if record.verification_type == VERIFICATION_TYPE_META:
            name = (record.verification_name or "").strip().lower()
            content = (record.verification_content or "").strip()
            if not name or not content:
                continue
            if name not in ALLOWED_VERIFICATION_NAMES:
                # Filter silently — the admin form rejects unknown names
                # on save; this just keeps stale rows from rendering.
                continue
            out.append(PublicVerificationMeta(name=name, content=content))
        elif record.verification_type == VERIFICATION_TYPE_FULL_META and record.full_meta_tag:
            try:
                attr, name, content = sanitize_meta_tag(record.full_meta_tag)
            except MetaSanitiseError:
                continue
            payload = (
                PublicVerificationMeta(name=name, content=content)
                if attr == "name"
                else PublicVerificationMeta(property=name, content=content)
            )
            out.append(payload)
        # html_file + dns_txt: not rendered as meta tags.
    return out


def find_active_verification_file(
    verifications: Iterable[SeoVerification], filename: str
) -> Optional[SeoVerification]:
    """Look up an active `html_file` verification by exact filename."""
    needle = filename.strip()
    if not needle:
        return None
    for record in verifications:
        if (
            record.is_active
            and record.verification_type == VERIFICATION_TYPE_HTML_FILE
            and (record.html_filename or "").strip() == needle
        ):
            return record
    return None


# ---------------------------------------------------------------------------
# Tracking ID validation
# ---------------------------------------------------------------------------


def validate_tracking_id(provider: str, value: str) -> str:
    """Validate a tracking ID against its provider's expected shape.

    Raises ``ValueError`` with a human-readable message on mismatch.
    Returns the normalised (upper / lower-cased) ID on success.
    """
    if not value:
        raise ValueError("Tracking ID is required")
    v = value.strip()
    if provider == PROVIDER_GTM:
        if not GTM_ID_RE.match(v):
            raise ValueError("GTM Container ID must look like GTM-XXXXXXX")
        return v.upper()
    if provider == PROVIDER_GA4:
        if not GA4_ID_RE.match(v):
            raise ValueError("GA4 Measurement ID must look like G-XXXXXXXXXX")
        return v.upper()
    if provider == PROVIDER_META_PIXEL:
        if not META_PIXEL_ID_RE.match(v):
            raise ValueError("Meta Pixel ID must be numeric (8-20 digits)")
        return v
    if provider == PROVIDER_CLARITY:
        if not CLARITY_ID_RE.match(v):
            raise ValueError("Clarity Project ID must be alphanumeric (6-15 chars)")
        return v.lower()
    if provider == PROVIDER_LINKEDIN:
        if not LINKEDIN_ID_RE.match(v):
            raise ValueError("LinkedIn Partner ID must be numeric (4-12 digits)")
        return v
    if provider == PROVIDER_TIKTOK:
        if not TIKTOK_ID_RE.match(v):
            raise ValueError("TikTok Pixel ID must be uppercase alphanumeric (15-30 chars)")
        return v.upper()
    if provider == PROVIDER_X:
        if not X_ID_RE.match(v):
            raise ValueError("X Pixel ID must be alphanumeric (4-15 chars)")
        return v.lower()
    # custom — no validation, admin owns the format
    return v


# ---------------------------------------------------------------------------
# Public integration projection
# ---------------------------------------------------------------------------


def public_integrations(
    integrations: Iterable[TrackingIntegration],
) -> List[PublicTrackingIntegration]:
    """Project active integrations down to the minimal payload the public layout consumes."""
    out: List[PublicTrackingIntegration] = []
    for row in integrations:
        if not row.is_active or not (row.tracking_id or "").strip():
            continue
        out.append(
            PublicTrackingIntegration(
                provider=row.provider,
                tracking_id=row.tracking_id.strip(),
                data_layer_name=row.data_layer_name or "dataLayer",
                placement=row.placement or PLACEMENT_HEAD,
                enable_noscript=row.enable_noscript,
                consent_mode_enabled=row.consent_mode_enabled,
                debug_mode=row.debug_mode,
            )
        )
    return out


def duplicate_tracking_warning(
    integrations: Iterable[TrackingIntegration],
) -> Optional[str]:
    """Return the GTM-vs-direct-script warning if both are active.

    GTM is meant to be the tracking hub. If admins also flip on the
    GA4 / Meta Pixel direct scripts, both load and events fire twice
    — this string surfaces in the SEO dashboard so the admin can
    decide whether the duplication is intentional.
    """
    active_providers = {
        row.provider for row in integrations if row.is_active and (row.tracking_id or "").strip()
    }
    if PROVIDER_GTM not in active_providers:
        return None
    duplicates = active_providers.intersection({PROVIDER_GA4, PROVIDER_META_PIXEL})
    if not duplicates:
        return None
    names = sorted({"GA4" if p == PROVIDER_GA4 else "Meta Pixel" for p in duplicates})
    return (
        "Google Tag Manager is active. Avoid enabling duplicate "
        f"{' + '.join(names)} direct scripts unless intentionally required."
    )


# ---------------------------------------------------------------------------
# Robots.txt builder
# ---------------------------------------------------------------------------

DEFAULT_ROBOTS_DISALLOWS = (
    "/admin",
    "/admin/",
    "/api",
    "/api/",
    "/hr",
    "/hr/",
    "/login",
    "/uploads/private/",
)


def build_robots_txt(settings: Optional[SeoSetting]) -> str:
    """Produce the final robots.txt text content."""
    if settings and not settings.enable_robots:
        # Convention: still serve a body so the route never 404s,
        # but explicitly tell crawlers we're closed.
        return "User-agent: *\nDisallow: /\n"
    base = (settings.canonical_base_url.rstrip("/") if settings and settings.canonical_base_url else "")
    if settings and not settings.robots_use_default and settings.robots_custom_content:
        body = settings.robots_custom_content.rstrip("\n") + "\n"
        if base and "Sitemap:" not in body:
            body += f"\nSitemap: {base}/sitemap.xml\n"
        return body

    disallows = list(DEFAULT_ROBOTS_DISALLOWS)
    if settings and settings.robots_extra_disallows:
        for line in settings.robots_extra_disallows.splitlines():
            stripped = line.strip()
            if stripped and stripped not in disallows:
                disallows.append(stripped)

    lines = ["User-agent: *", "Allow: /"]
    for d in disallows:
        lines.append(f"Disallow: {d}")
    if base:
        lines.append("")
        lines.append(f"Sitemap: {base}/sitemap.xml")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Dashboard aggregation
# ---------------------------------------------------------------------------


def integration_by_provider(
    integrations: Iterable[TrackingIntegration],
) -> Dict[str, TrackingIntegration]:
    """Return a {provider_key: row} map."""
    return {row.provider: row for row in integrations}


def verification_active_for(
    verifications: Iterable[SeoVerification], provider: str
) -> bool:
    """Whether at least one active verification record exists for `provider`."""
    key = provider.strip().lower()
    return any(
        v.is_active and v.provider == key for v in verifications
    )
