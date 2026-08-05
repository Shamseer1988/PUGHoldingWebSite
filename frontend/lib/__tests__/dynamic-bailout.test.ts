/**
 * Next's static-rendering bail-out must pass through our fetch
 * helpers untouched.
 *
 * The risk being guarded is not cosmetic: if a helper catches
 * ``DynamicServerError`` and returns its empty fallback, Next can
 * prerender the page with no data instead of marking it dynamic. The
 * visible symptom is a build log full of "fetch failed" traces for a
 * build that succeeded.
 */
import { describe, expect, it } from "vitest";

import {
  isDynamicServerError,
  rethrowIfDynamicServerError,
} from "@/lib/dynamic-bailout";

/** Shape Next throws during prerender of a `no-store` fetch. */
function dynamicServerError(): Error & { digest: string } {
  const err = new Error(
    "Dynamic server usage: no-store fetch https://example.com/api /offers",
  ) as Error & { digest: string };
  err.digest = "DYNAMIC_SERVER_USAGE";
  return err;
}

describe("isDynamicServerError", () => {
  it("recognises Next's bail-out signal by its digest", () => {
    expect(isDynamicServerError(dynamicServerError())).toBe(true);
  });

  it("does not mistake a real fetch failure for it", () => {
    expect(isDynamicServerError(new TypeError("fetch failed"))).toBe(false);
  });

  it("ignores an unrelated digest", () => {
    const err = new Error("boom") as Error & { digest: string };
    err.digest = "NEXT_NOT_FOUND";
    expect(isDynamicServerError(err)).toBe(false);
  });

  it("is safe on null, undefined and primitives", () => {
    expect(isDynamicServerError(null)).toBe(false);
    expect(isDynamicServerError(undefined)).toBe(false);
    expect(isDynamicServerError("DYNAMIC_SERVER_USAGE")).toBe(false);
    expect(isDynamicServerError(42)).toBe(false);
  });
});

describe("rethrowIfDynamicServerError", () => {
  it("re-throws the bail-out so Next can mark the route dynamic", () => {
    const err = dynamicServerError();
    expect(() => rethrowIfDynamicServerError(err)).toThrow(err);
  });

  it("returns quietly for a genuine error, letting the caller handle it", () => {
    expect(() =>
      rethrowIfDynamicServerError(new Error("ECONNREFUSED")),
    ).not.toThrow();
  });
});
