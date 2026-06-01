/**
 * Branded short-link helpers (Marketing → Tools → URL Shortener).
 *
 * Short links are always rendered from the dedicated short domain —
 * ``https://pug.qa`` by default — regardless of which host the admin
 * happens to be signed into. This used to be derived from
 * ``window.location.origin``, which meant a link created while logged
 * into ``parisunitedgroup.com`` (or a staging host) got copied/printed
 * with the wrong domain. The short domain is configuration, not
 * "wherever this page is being served from".
 *
 * Override per-environment with ``NEXT_PUBLIC_SHORT_URL_BASE`` — e.g.
 * point it at ``http://localhost:3000`` in local dev so copied links
 * resolve against the dev server. Like every ``NEXT_PUBLIC_*`` value it
 * is baked into the browser bundle at build time.
 */

/** Short domain used when ``NEXT_PUBLIC_SHORT_URL_BASE`` is unset. */
export const DEFAULT_SHORT_URL_BASE = "https://pug.qa";

/**
 * Configured short-link origin with any trailing slash(es) trimmed, so
 * callers can join with ``/go/{slug}`` without doubling the separator.
 */
export function shortUrlBase(): string {
  const raw =
    process.env.NEXT_PUBLIC_SHORT_URL_BASE || DEFAULT_SHORT_URL_BASE;
  return raw.replace(/\/+$/, "");
}

/**
 * Full public short link for ``slug`` — e.g.
 * ``shortUrlFor("summer-25") === "https://pug.qa/go/summer-25"``.
 */
export function shortUrlFor(slug: string): string {
  return `${shortUrlBase()}/go/${slug}`;
}
