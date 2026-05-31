import { describe, expect, test, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

import {
  EMPTY_HR_FILTERS,
  buildHrFilterHref,
  hasActiveHrFilters,
  hrFiltersToQueryString,
  parseHrFilters,
  useHrFilters,
} from "@/hooks/use-hr-filters";

const replace = vi.fn();
let currentParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/hr/candidates",
  useSearchParams: () => currentParams,
}));

beforeEach(() => {
  replace.mockClear();
  currentParams = new URLSearchParams();
});

// Canonical encoding order: status, job, department, company, source,
// date_from, date_to.
const FULL_QS =
  "status=selected&job=eng&department=Tech&company=PUG&source=public_form&date_from=2026-01-01&date_to=2026-02-01";

describe("HR filter encoding", () => {
  test("round-trips a full filter set through the query string", () => {
    const parsed = parseHrFilters(new URLSearchParams(FULL_QS));
    expect(parsed).toEqual({
      status: "selected",
      job: "eng",
      department: "Tech",
      company: "PUG",
      source: "public_form",
      dateFrom: "2026-01-01",
      dateTo: "2026-02-01",
    });
    // Re-serialising yields the exact same query string.
    expect(hrFiltersToQueryString(parsed)).toBe(FULL_QS);
  });

  test("omits empty values when serialising", () => {
    expect(hrFiltersToQueryString({ status: "selected" })).toBe(
      "status=selected",
    );
    expect(hrFiltersToQueryString(EMPTY_HR_FILTERS)).toBe("");
  });

  test("defaults to empty filters for null params and ignores unknown keys", () => {
    expect(parseHrFilters(null)).toEqual(EMPTY_HR_FILTERS);
    const parsed = parseHrFilters(new URLSearchParams("foo=bar&status=joined"));
    expect(parsed.status).toBe("joined");
    expect(parsed.job).toBe("");
  });

  test("hasActiveHrFilters reflects whether anything is set", () => {
    expect(hasActiveHrFilters(EMPTY_HR_FILTERS)).toBe(false);
    expect(hasActiveHrFilters({ ...EMPTY_HR_FILTERS, company: "PUG" })).toBe(
      true,
    );
  });

  test("buildHrFilterHref carries filters and applies overrides", () => {
    const filters = { ...EMPTY_HR_FILTERS, department: "Tech" };
    expect(buildHrFilterHref("/hr/offers", filters)).toBe(
      "/hr/offers?department=Tech",
    );
    expect(
      buildHrFilterHref("/hr/candidates", filters, { status: "selected" }),
    ).toBe("/hr/candidates?status=selected&department=Tech");
    expect(buildHrFilterHref("/hr/onboarding", EMPTY_HR_FILTERS)).toBe(
      "/hr/onboarding",
    );
  });
});

describe("useHrFilters", () => {
  test("reads the current filters from the URL", () => {
    currentParams = new URLSearchParams("status=shortlisted&department=Ops");
    const { result } = renderHook(() => useHrFilters());
    expect(result.current.filters.status).toBe("shortlisted");
    expect(result.current.filters.department).toBe("Ops");
    expect(result.current.hasActive).toBe(true);
    expect(result.current.queryString).toBe("status=shortlisted&department=Ops");
  });

  test("setFilter writes the merged filters back to the URL", () => {
    currentParams = new URLSearchParams("department=Ops");
    const { result } = renderHook(() => useHrFilters());
    act(() => result.current.setFilter("status", "selected"));
    expect(replace).toHaveBeenCalledWith(
      "/hr/candidates?status=selected&department=Ops",
      { scroll: false },
    );
  });

  test("setFilters merges several fields and reset clears everything", () => {
    currentParams = new URLSearchParams("status=joined");
    const { result } = renderHook(() => useHrFilters());

    act(() => result.current.setFilters({ job: "eng", source: "public_form" }));
    expect(replace).toHaveBeenLastCalledWith(
      "/hr/candidates?status=joined&job=eng&source=public_form",
      { scroll: false },
    );

    act(() => result.current.reset());
    expect(replace).toHaveBeenLastCalledWith("/hr/candidates", {
      scroll: false,
    });
  });
});
