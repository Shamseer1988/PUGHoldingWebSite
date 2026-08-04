/**
 * ``qrUrlFor`` pins the permanent scan URL to the configured short
 * domain. This is the value encoded into printed artwork, so the
 * important property is that it does NOT vary with the host the admin
 * is signed into — a code generated from staging must still print the
 * production URL.
 */
import { afterEach, describe, expect, test } from "vitest";

import { QR_PATH_PREFIX, qrUrlDisplay, qrUrlFor } from "@/lib/marketing/qr-url";

const ENV_KEY = "NEXT_PUBLIC_SHORT_URL_BASE";

afterEach(() => {
  delete process.env[ENV_KEY];
});

describe("qrUrlFor", () => {
  test("defaults to the pug.qa short domain", () => {
    delete process.env[ENV_KEY];
    expect(QR_PATH_PREFIX).toBe("/q");
    expect(qrUrlFor("al-atiyah")).toBe("https://pug.qa/q/al-atiyah");
  });

  test("is stable, not derived from the current browser origin", () => {
    delete process.env[ENV_KEY];
    expect(qrUrlFor("al-khor").startsWith("https://pug.qa/q/")).toBe(true);
  });

  test("honours the NEXT_PUBLIC_SHORT_URL_BASE override", () => {
    process.env[ENV_KEY] = "https://go.example.qa";
    expect(qrUrlFor("al-wakra")).toBe("https://go.example.qa/q/al-wakra");
  });

  test("trims trailing slashes so the URL never doubles up", () => {
    process.env[ENV_KEY] = "https://pug.qa///";
    expect(qrUrlFor("umm-salal")).toBe("https://pug.qa/q/umm-salal");
  });

  test("shares its base with the URL shortener", () => {
    // Both link types must brand identically — if these diverge, one
    // of the two features is printing the wrong domain.
    process.env[ENV_KEY] = "https://links.example.qa";
    expect(qrUrlFor("x").startsWith("https://links.example.qa/")).toBe(true);
  });
});

describe("qrUrlDisplay", () => {
  test("strips the scheme for compact table cells", () => {
    delete process.env[ENV_KEY];
    expect(qrUrlDisplay("al-atiyah")).toBe("pug.qa/q/al-atiyah");
  });

  test("strips http as well as https", () => {
    process.env[ENV_KEY] = "http://localhost:3000";
    expect(qrUrlDisplay("al-khor")).toBe("localhost:3000/q/al-khor");
  });
});
