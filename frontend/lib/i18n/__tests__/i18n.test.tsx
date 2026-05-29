/**
 * i18n core (Phase C-1).
 *
 * Exercises the pieces a future caller could break without anyone
 * else noticing:
 *
 *   - ``negotiateLocale`` picks the highest-priority supported tag
 *     from an ``Accept-Language`` header and falls back cleanly.
 *   - ``isLocale`` is the type-narrowing guard the middleware +
 *     resolver lean on.
 *   - ``translate`` returns the key on miss (loud failure),
 *     supports ``{placeholder}`` substitution, and handles missing
 *     placeholders by leaving them in place.
 *   - ``useT`` is a thin hook over ``translate``; rendering with
 *     the LocaleProvider in the tree returns the right string.
 *   - The Arabic dictionary covers the same keys as English —
 *     a missing key would surface as a raw dotted path in the UI.
 */
import { describe, expect, test } from "vitest";
import { render } from "@testing-library/react";

import enMessages from "@/lib/i18n/messages/en.json";
import arMessages from "@/lib/i18n/messages/ar.json";
import {
  DEFAULT_LOCALE,
  LOCALES,
  isLocale,
  negotiateLocale,
} from "@/lib/i18n/config";
import {
  LocaleProvider,
  translate,
  useT,
} from "@/lib/i18n/locale-provider";

describe("isLocale", () => {
  test.each([
    ["en", true],
    ["ar", true],
    ["fr", false],
    ["EN", false],
    ["", false],
    [null, false],
    [undefined, false],
  ])("isLocale(%j) → %s", (input, expected) => {
    expect(isLocale(input as string | null | undefined)).toBe(expected);
  });
});

describe("negotiateLocale", () => {
  test("returns DEFAULT_LOCALE when header is null", () => {
    expect(negotiateLocale(null)).toBe(DEFAULT_LOCALE);
  });

  test("picks the highest-priority supported tag", () => {
    expect(
      negotiateLocale("fr-FR,fr;q=0.9,ar;q=0.8,en;q=0.7")
    ).toBe("ar");
  });

  test("strips region subtags before matching", () => {
    expect(negotiateLocale("en-US,en;q=0.9")).toBe("en");
  });

  test("falls back when no listed tag is supported", () => {
    expect(negotiateLocale("de-DE,fr;q=0.9")).toBe(DEFAULT_LOCALE);
  });
});

describe("translate", () => {
  test("looks up a nested key", () => {
    expect(translate(enMessages, "navbar.open_menu")).toBe("Open menu");
  });

  test("returns the key itself on miss — loud failure", () => {
    expect(translate(enMessages, "navbar.does_not_exist")).toBe(
      "navbar.does_not_exist"
    );
  });

  test("interpolates {placeholder} values", () => {
    expect(
      translate(enMessages, "hero.slide_indicator", { n: 3 })
    ).toBe("Go to slide 3");
  });

  test("leaves placeholders intact when a value is missing", () => {
    expect(
      translate(enMessages, "navbar.switch_language_to")
    ).toBe("Switch language to {target}");
  });
});

describe("ar dictionary parity", () => {
  test("covers every English key", () => {
    const missing: string[] = [];
    const walk = (en: unknown, ar: unknown, path: string[]) => {
      if (typeof en === "string") {
        if (typeof ar !== "string") missing.push(path.join("."));
        return;
      }
      if (en && typeof en === "object") {
        for (const key of Object.keys(en)) {
          const next = (ar as Record<string, unknown> | null)?.[key];
          walk((en as Record<string, unknown>)[key], next, [...path, key]);
        }
      }
    };
    walk(enMessages, arMessages, []);
    expect(missing).toEqual([]);
  });
});

describe("useT under LocaleProvider", () => {
  function ProbeArabic() {
    const t = useT();
    return <span data-testid="probe">{t("navbar.open_menu")}</span>;
  }

  test("returns the Arabic string when the provider is in ar mode", () => {
    const { getByTestId } = render(
      <LocaleProvider locale="ar" messages={arMessages}>
        <ProbeArabic />
      </LocaleProvider>
    );
    expect(getByTestId("probe").textContent).toBe(
      arMessages.navbar.open_menu
    );
  });

  test("LOCALES is exactly the two configured locales", () => {
    expect(LOCALES).toEqual(["en", "ar"]);
  });
});
