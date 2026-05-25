/**
 * Sanitiser for the Site Settings `contact_map_embed` field.
 *
 * Admins paste one of:
 *   1. A bare embed URL — e.g. `https://www.google.com/maps/embed?pb=...`
 *   2. A full `<iframe ...></iframe>` snippet copied from Google Maps
 *      → Share → Embed a map.
 *   3. Nothing (null / empty / whitespace).
 *
 * Goals:
 *   - Always render with OUR own `<iframe>` markup (no admin-supplied
 *     HTML attributes), so a malicious paste can't ship arbitrary
 *     scripts, `srcdoc`, `onload`, etc.
 *   - Only honour iframes whose final `src` lives on one of the
 *     allow-listed map hosts. Anything else returns `null` and the
 *     calling component shows a friendly empty state.
 *
 * The allow-list is intentionally narrow because the field is meant
 * for an address map, not arbitrary embeds.
 */

const ALLOWED_HOSTS = new Set([
  "www.google.com",
  "google.com",
  "maps.google.com",
  "www.openstreetmap.org",
  "openstreetmap.org",
  "www.bing.com",
  "bing.com",
]);

/**
 * Result of inspecting the raw admin input.
 *
 * `safeSrc` is the URL we'd use on the iframe. `error` is a short
 * human-readable reason when the input was non-empty but unusable —
 * the admin preview surfaces it; the public page just hides the
 * map.
 */
export interface ContactMapEmbed {
  safeSrc: string | null;
  error: string | null;
}

function extractIframeSrc(raw: string): string | null {
  // Lightweight extraction so we don't pull in a DOM parser server-
  // side. `src="..."` / `src='...'` — anything else fails closed.
  const match = raw.match(/<iframe\b[^>]*\bsrc\s*=\s*(?:"([^"]+)"|'([^']+)')/i);
  if (!match) return null;
  return (match[1] ?? match[2] ?? "").trim() || null;
}

export function parseContactMapEmbed(
  raw: string | null | undefined
): ContactMapEmbed {
  if (!raw) return { safeSrc: null, error: null };
  const trimmed = raw.trim();
  if (!trimmed) return { safeSrc: null, error: null };

  let candidate: string;
  if (trimmed.toLowerCase().startsWith("<iframe")) {
    const src = extractIframeSrc(trimmed);
    if (!src) {
      return {
        safeSrc: null,
        error:
          "Couldn't find a src=\"...\" on that iframe. Copy the full snippet from Google Maps.",
      };
    }
    candidate = src;
  } else if (/^https?:\/\//i.test(trimmed)) {
    candidate = trimmed;
  } else {
    return {
      safeSrc: null,
      error:
        "Paste either a full <iframe> snippet or a https:// embed URL.",
    };
  }

  let url: URL;
  try {
    url = new URL(candidate);
  } catch {
    return { safeSrc: null, error: "That doesn't look like a valid URL." };
  }

  if (url.protocol !== "https:") {
    return { safeSrc: null, error: "Embed URL must use https://." };
  }

  const host = url.hostname.toLowerCase();
  if (!ALLOWED_HOSTS.has(host)) {
    return {
      safeSrc: null,
      error: `Only Google Maps, OpenStreetMap, and Bing Maps are allowed (got ${host}).`,
    };
  }

  return { safeSrc: url.toString(), error: null };
}
