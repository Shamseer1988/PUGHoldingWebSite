/**
 * i18n configuration (Phase C-1).
 *
 * Hand-rolled to keep the dependency surface tight (CLAUDE.md rule).
 * If we outgrow this — ICU plural rules, server-component-only
 * helpers, lazy message splitting — we re-evaluate ``next-intl``;
 * for the initial bilingual launch (English + Arabic) two flat
 * JSON dictionaries + a context provider are enough.
 *
 * What lives where:
 *
 *   - ``messages/<locale>.json``  the dictionary (UI strings only;
 *     CMS content is single-language until the backend grows a
 *     ``locale`` column).
 *   - ``get-messages.ts``         server-side loader that picks the
 *     right JSON file for the active locale.
 *   - ``get-locale.ts``           server-side resolver that reads
 *     the ``x-locale`` header set by ``middleware.ts``.
 *   - ``locale-provider.tsx``     client provider + ``useLocale``
 *     + ``useT`` hook.
 *   - ``../../middleware.ts``     URL-prefix + cookie + Accept-
 *     Language detection; sets ``x-locale`` for the page render.
 */

export const LOCALES = ["en", "ar"] as const;

export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

/**
 * Maps each locale to its writing direction. Drives both the
 * ``<html dir>`` attribute and Tailwind's built-in ``rtl:`` /
 * ``ltr:`` variants.
 */
export const LOCALE_DIRECTION: Record<Locale, "ltr" | "rtl"> = {
  en: "ltr",
  ar: "rtl",
};

/**
 * Human-readable label per locale — used by the language switcher.
 * Kept here (not in the message dictionaries) so the label of the
 * *other* language renders in its own script regardless of which
 * locale the user is currently viewing.
 */
export const LOCALE_LABEL: Record<Locale, string> = {
  en: "English",
  ar: "العربية",
};

export function isLocale(value: string | null | undefined): value is Locale {
  return value != null && (LOCALES as readonly string[]).includes(value);
}

/**
 * Negotiate a locale from an ``Accept-Language`` header. Used by
 * the middleware when no cookie + no URL prefix is present.
 * Returns ``DEFAULT_LOCALE`` if no listed locale matches.
 */
export function negotiateLocale(acceptLanguage: string | null): Locale {
  if (!acceptLanguage) return DEFAULT_LOCALE;
  // ``en-US,en;q=0.9,ar;q=0.8`` → ["en-US", "en", "ar"]
  const tags = acceptLanguage
    .split(",")
    .map((part) => part.split(";")[0]?.trim().toLowerCase())
    .filter((s): s is string => Boolean(s));
  for (const tag of tags) {
    const primary = tag.split("-")[0];
    if (isLocale(primary)) return primary;
  }
  return DEFAULT_LOCALE;
}
