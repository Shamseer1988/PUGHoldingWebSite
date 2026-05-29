/**
 * Server-side locale resolver (Phase C-1).
 *
 * Reads the ``x-locale`` request header that ``middleware.ts``
 * stamps on every incoming request after running its URL-prefix +
 * cookie + Accept-Language negotiation. The middleware is the
 * single source of truth for "which locale is this request?" — the
 * layout just trusts what it set and falls back to ``DEFAULT_LOCALE``
 * if the header is missing (defensive; shouldn't happen at runtime).
 */
import { headers } from "next/headers";

import { DEFAULT_LOCALE, isLocale, type Locale } from "./config";

export function getLocale(): Locale {
  const value = headers().get("x-locale");
  return isLocale(value) ? value : DEFAULT_LOCALE;
}
