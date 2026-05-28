/**
 * Locale middleware (Phase C-1).
 *
 * Single entry point for "what locale does this request render in?"
 * Runs before every public-page render and stamps an ``x-locale``
 * request header that ``lib/i18n/get-locale.ts`` reads.
 *
 * Resolution order:
 *
 *   1. URL prefix — ``/en/...`` or ``/ar/...``. If present, we
 *      rewrite the URL to strip the prefix (so existing routes
 *      under ``app/(public)`` keep matching without restructuring
 *      the directory tree) and remember the choice in a cookie.
 *   2. Cookie — ``pug_locale`` from a previous switcher click.
 *   3. ``Accept-Language`` header negotiation.
 *   4. ``DEFAULT_LOCALE`` (English).
 *
 * Admin / HR portals are intentionally excluded (``matcher`` below):
 * those consoles are English-only and the localised public chrome
 * shouldn't bleed into them.
 */
import { NextResponse, type NextRequest } from "next/server";

import {
  DEFAULT_LOCALE,
  LOCALES,
  isLocale,
  negotiateLocale,
  type Locale,
} from "@/lib/i18n/config";

const LOCALE_COOKIE = "pug_locale";
// 1 year — long enough that returning visitors don't pay the
// negotiation cost again, short enough that a user who clears their
// cookies isn't permanently stranded in a stale locale.
const LOCALE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

function localeFromPath(pathname: string): { locale: Locale; remainder: string } | null {
  // ``/en`` or ``/en/foo``; not ``/enquire``.
  const match = /^\/(\w{2})(?=\/|$)/.exec(pathname);
  if (!match) return null;
  const candidate = match[1];
  if (!isLocale(candidate)) return null;
  const remainder = pathname.slice(match[0].length) || "/";
  return { locale: candidate, remainder };
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Step 1: URL prefix wins outright.
  const fromPath = localeFromPath(pathname);
  if (fromPath) {
    const url = request.nextUrl.clone();
    url.pathname = fromPath.remainder;
    const response = NextResponse.rewrite(url, {
      request: {
        // The rewritten request the page handler sees carries the
        // ``x-locale`` header.
        headers: withLocaleHeader(request.headers, fromPath.locale),
      },
    });
    response.cookies.set(LOCALE_COOKIE, fromPath.locale, {
      maxAge: LOCALE_COOKIE_MAX_AGE,
      sameSite: "lax",
      path: "/",
    });
    return response;
  }

  // Step 2 + 3 + 4: cookie → Accept-Language → default.
  const cookieLocale = request.cookies.get(LOCALE_COOKIE)?.value;
  const locale: Locale = isLocale(cookieLocale)
    ? cookieLocale
    : negotiateLocale(request.headers.get("accept-language"));

  const response = NextResponse.next({
    request: {
      headers: withLocaleHeader(request.headers, locale),
    },
  });
  // Refresh the cookie even when it was already present so its TTL
  // rolls forward on activity. New visitors get one stamped here.
  response.cookies.set(LOCALE_COOKIE, locale, {
    maxAge: LOCALE_COOKIE_MAX_AGE,
    sameSite: "lax",
    path: "/",
  });
  return response;
}

function withLocaleHeader(original: Headers, locale: Locale): Headers {
  const next = new Headers(original);
  next.set("x-locale", locale);
  return next;
}

/**
 * Run on every request EXCEPT:
 *
 *   - ``/admin/*`` + ``/hr/*`` — operator consoles, English-only
 *   - ``/api/*`` — backend hand-off
 *   - ``/_next/*`` — build assets
 *   - filenames containing a dot (``robots.txt``, ``sitemap.xml``,
 *     image / favicon requests, etc.)
 *
 * The ``matcher`` runs at the edge so keeping it narrow saves
 * latency on static asset hits.
 */
export const config = {
  matcher: [
    "/((?!admin|hr|api|_next|.*\\..*).*)",
  ],
};

export { LOCALE_COOKIE, LOCALES };
