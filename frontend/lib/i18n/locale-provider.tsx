"use client";

/**
 * Client-side locale context (Phase C-1).
 *
 * Seeded from the server layout with the active locale + its
 * dictionary. Components read translations via ``useT()`` — a thin
 * lookup over the dictionary that supports ``{placeholder}``
 * interpolation but nothing else (no plural rules, no ICU). That's
 * enough for the initial bilingual surface; ``next-intl`` is the
 * graduation path if we need more.
 */
import * as React from "react";

import type { Locale } from "./config";
import type { Messages } from "./get-messages";

interface LocaleContextValue {
  locale: Locale;
  messages: Messages;
}

const LocaleContext = React.createContext<LocaleContextValue | null>(null);

interface LocaleProviderProps {
  locale: Locale;
  messages: Messages;
  children: React.ReactNode;
}

export function LocaleProvider({
  locale,
  messages,
  children,
}: LocaleProviderProps) {
  // ``useMemo`` is the cheap-context pattern: components that read
  // ``locale`` from this context don't re-render when an unrelated
  // re-render bubbles through.
  const value = React.useMemo(
    () => ({ locale, messages }),
    [locale, messages]
  );
  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale(): Locale {
  const ctx = React.useContext(LocaleContext);
  if (!ctx) {
    throw new Error("useLocale must be used inside a <LocaleProvider>");
  }
  return ctx.locale;
}

/**
 * Translation hook keyed by ``namespace.key`` dotted path.
 *
 * ``t("navbar.open_menu")`` → "Open menu" (English) / "فتح القائمة" (Arabic).
 *
 * The optional ``values`` argument substitutes ``{name}`` placeholders
 * with the provided values, in the order they appear in the string.
 * Missing placeholders are left intact so the bug is visible.
 */
export function useT(): (key: string, values?: Record<string, string | number>) => string {
  const ctx = React.useContext(LocaleContext);
  if (!ctx) {
    throw new Error("useT must be used inside a <LocaleProvider>");
  }
  const { messages } = ctx;

  return React.useCallback(
    (key, values) => translate(messages, key, values),
    [messages]
  );
}

/**
 * Pure lookup used by both the hook and the tests. Returns the key
 * itself when nothing matches so a missing translation surfaces
 * loudly in the UI (".navbar.open_menu") rather than silently
 * rendering empty.
 */
export function translate(
  messages: Messages,
  key: string,
  values?: Record<string, string | number>
): string {
  const segments = key.split(".");
  let current: unknown = messages;
  for (const segment of segments) {
    if (current && typeof current === "object" && segment in current) {
      current = (current as Record<string, unknown>)[segment];
    } else {
      return key;
    }
  }
  if (typeof current !== "string") return key;
  if (!values) return current;
  return current.replace(/\{(\w+)\}/g, (match, name: string) => {
    const replacement = values[name];
    return replacement === undefined ? match : String(replacement);
  });
}
