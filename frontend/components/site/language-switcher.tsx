"use client";

/**
 * Language switcher (Phase C-1).
 *
 * Single button that toggles between the two configured locales.
 * Sets the ``pug_locale`` cookie directly and reloads the page so
 * the middleware re-renders the document in the new locale + the
 * ``<html dir>`` attribute flips. Using ``router.refresh()`` instead
 * wouldn't reset the document direction — the ``dir`` attribute is
 * baked into the initial HTML, not part of the route render.
 */
import * as React from "react";
import { Languages } from "lucide-react";

import {
  LOCALE_LABEL,
  LOCALES,
  type Locale,
} from "@/lib/i18n/config";
import { useLocale, useT } from "@/lib/i18n/locale-provider";
import { cn } from "@/lib/utils";

interface LanguageSwitcherProps {
  className?: string;
}

export function LanguageSwitcher({ className }: LanguageSwitcherProps) {
  const locale = useLocale();
  const t = useT();
  const other = LOCALES.find((l) => l !== locale) ?? locale;

  const handleSwitch = React.useCallback(
    (next: Locale) => {
      // Cookie max-age 1 year, matches the middleware default.
      document.cookie = `pug_locale=${next}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
      // Hard reload so the document re-renders under the new locale
      // and the ``<html dir>`` attribute flips. The cookie set above
      // is read by the middleware on this next request.
      window.location.reload();
    },
    []
  );

  return (
    <button
      type="button"
      onClick={() => handleSwitch(other)}
      aria-label={t("navbar.switch_language_to", { target: LOCALE_LABEL[other] })}
      title={LOCALE_LABEL[other]}
      className={cn(
        "inline-flex h-10 items-center gap-1.5 rounded-full border border-border/40 bg-background/80 px-3 text-xs font-semibold uppercase tracking-[0.18em] text-foreground/80 transition-colors hover:border-border hover:text-foreground",
        className
      )}
    >
      <Languages className="h-3.5 w-3.5" aria-hidden />
      <span>{other.toUpperCase()}</span>
    </button>
  );
}
