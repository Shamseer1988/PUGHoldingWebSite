/**
 * ``shortUrlFor`` pins the branded short domain. Short links must render
 * from the dedicated short domain (``https://pug.qa`` by default), NOT
 * from whatever host the admin is signed into — and never with a double
 * slash when the configured base carries a trailing one.
 */
import { afterEach, describe, expect, test } from "vitest";

import {
  DEFAULT_SHORT_URL_BASE,
  shortUrlBase,
  shortUrlFor,
} from "@/lib/short-url";

const ENV_KEY = "NEXT_PUBLIC_SHORT_URL_BASE";

afterEach(() => {
  delete process.env[ENV_KEY];
});

describe("shortUrlFor", () => {
  test("defaults to the pug.qa short domain", () => {
    delete process.env[ENV_KEY];
    expect(DEFAULT_SHORT_URL_BASE).toBe("https://pug.qa");
    expect(shortUrlBase()).toBe("https://pug.qa");
    expect(shortUrlFor("summer-25")).toBe("https://pug.qa/go/summer-25");
  });

  test("is stable, not derived from the current browser origin", () => {
    // Regression: the old helper used ``window.location.origin``, so a
    // link made on parisunitedgroup.com came out branded with the wrong
    // host. The base is configuration now, so the result is stable.
    delete process.env[ENV_KEY];
    expect(shortUrlFor("abc123").startsWith("https://pug.qa/go/")).toBe(true);
  });

  test("honours the NEXT_PUBLIC_SHORT_URL_BASE override", () => {
    process.env[ENV_KEY] = "https://go.example.qa";
    expect(shortUrlBase()).toBe("https://go.example.qa");
    expect(shortUrlFor("xyz")).toBe("https://go.example.qa/go/xyz");
  });

  test("trims trailing slashes on the configured base", () => {
    process.env[ENV_KEY] = "https://pug.qa///";
    expect(shortUrlBase()).toBe("https://pug.qa");
    expect(shortUrlFor("eid")).toBe("https://pug.qa/go/eid");
  });
});
