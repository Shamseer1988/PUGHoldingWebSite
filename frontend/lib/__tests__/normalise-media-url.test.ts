/**
 * ``normaliseMediaUrl`` defends against historic DB rows written
 * when the backend's ``R2_PUBLIC_BASE_URL`` was set without
 * ``https://``. Those rows look like
 * ``pug-media.example.com/cms/foo.jpg`` and the browser would
 * otherwise treat them as a path relative to the current page.
 *
 * The helper now auto-promotes any bare-hostname pattern to
 * ``https://…``. The tests pin the contract:
 *
 *  * absolute ``http://`` / ``https://`` URLs pass through unchanged
 *  * bare hostnames (with at least one dot + a path) get ``https://``
 *  * relative paths (``/api/uploads/…``, ``/admin``) are NOT promoted
 *  * empty / whitespace / null / Windows backslashes still behave
 */
import { describe, expect, test } from "vitest";

import { normaliseMediaUrl } from "@/lib/public-api";

describe("normaliseMediaUrl", () => {
  test("returns null for empty / whitespace / null input", () => {
    expect(normaliseMediaUrl(null)).toBeNull();
    expect(normaliseMediaUrl(undefined)).toBeNull();
    expect(normaliseMediaUrl("")).toBeNull();
    expect(normaliseMediaUrl("   ")).toBeNull();
  });

  test("passes through absolute http/https URLs unchanged", () => {
    expect(normaliseMediaUrl("https://cdn.example.com/a.jpg")).toBe(
      "https://cdn.example.com/a.jpg",
    );
    expect(normaliseMediaUrl("http://cdn.example.com/a.jpg")).toBe(
      "http://cdn.example.com/a.jpg",
    );
  });

  test("auto-promotes bare hostname/path to https://", () => {
    // The exact pattern that broke in production after R2_PUBLIC_BASE_URL
    // was set without the scheme.
    expect(
      normaliseMediaUrl("pug-media.parisunitedgroup.com/cms/foo.jpg"),
    ).toBe("https://pug-media.parisunitedgroup.com/cms/foo.jpg");
  });

  test("handles multi-segment subdomains without confusion", () => {
    expect(
      normaliseMediaUrl("media.staging.example.co.uk/cms/companies/logos/x.png"),
    ).toBe("https://media.staging.example.co.uk/cms/companies/logos/x.png");
  });

  test("normalises Windows backslashes before evaluating scheme", () => {
    expect(normaliseMediaUrl("cdn.example.com\\cms\\foo.jpg")).toBe(
      "https://cdn.example.com/cms/foo.jpg",
    );
  });

  test("does NOT promote relative-looking paths", () => {
    // Leading slash → relative to the site root, never a hostname.
    const apiPath = normaliseMediaUrl("/api/v1/uploads/cms/x.png");
    expect(apiPath?.startsWith("https://")).toBe(false);
    expect(apiPath).toContain("/api/v1/uploads/cms/x.png");
  });

  test("does NOT promote bare filenames or paths without dots", () => {
    // Single-word hostnames are too ambiguous (could be 'localhost' or a
    // missing-slash typo) — leave them to ``resolveAssetUrl``.
    expect(normaliseMediaUrl("just-a-filename.jpg")).not.toMatch(/^https/);
  });
});
