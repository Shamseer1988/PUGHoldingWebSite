/**
 * Server-side message loader (Phase C-1).
 *
 * Resolves a locale → its flat translation dictionary at request
 * time. Used by the public-site layout to seed the LocaleProvider
 * with the dictionary baked into the initial HTML — clients don't
 * pay a round trip to fetch translations.
 *
 * The dictionaries are imported statically so they ship in the
 * server bundle. Two locales × a handful of keys each is well under
 * a kilobyte; lazy-loading them would be premature.
 */
import enMessages from "./messages/en.json";
import arMessages from "./messages/ar.json";
import type { Locale } from "./config";

export type Messages = typeof enMessages;

const MESSAGES_BY_LOCALE: Record<Locale, Messages> = {
  en: enMessages,
  ar: arMessages,
};

export function getMessages(locale: Locale): Messages {
  return MESSAGES_BY_LOCALE[locale];
}
