/**
 * Permanent scan-URL helpers for branch QR codes (Marketing → QR Codes).
 *
 * A QR code's URL is printed on signage and flyers, so it is rendered
 * from the configured short domain (``https://pug.qa`` by default) —
 * never from ``window.location.origin``. An admin signed into a
 * staging host must still be shown, and hand out, the production URL;
 * the alternative is artwork that resolves to staging forever.
 *
 * This shares ``NEXT_PUBLIC_SHORT_URL_BASE`` with the URL shortener
 * (see ``lib/short-url.ts``) so both link types brand identically. The
 * backend mirrors it as the ``SHORT_URL_BASE`` setting — the two must
 * agree, or the artwork the backend renders won't match the URL this
 * helper displays next to it.
 */
import { shortUrlBase } from "@/lib/short-url";

/** Path prefix the backend's QR resolver is mounted at. */
export const QR_PATH_PREFIX = "/q";

/**
 * Full permanent scan URL for ``slug`` — e.g.
 * ``qrUrlFor("al-atiyah") === "https://pug.qa/q/al-atiyah"``.
 *
 * This is exactly what gets encoded into the QR image, which is why it
 * must never be derived from the current page's origin.
 */
export function qrUrlFor(slug: string): string {
  return `${shortUrlBase()}${QR_PATH_PREFIX}/${slug}`;
}

/**
 * Display form with the scheme stripped — ``pug.qa/q/al-atiyah``.
 *
 * Used in table cells where the ``https://`` is noise. Purely
 * cosmetic: copy actions always use the full {@link qrUrlFor} value,
 * because a URL pasted without a scheme isn't clickable everywhere.
 */
export function qrUrlDisplay(slug: string): string {
  return qrUrlFor(slug).replace(/^https?:\/\//, "");
}
