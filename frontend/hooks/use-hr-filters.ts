"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

/**
 * Shared HR filter taxonomy (acceptance criterion 9).
 *
 * Candidates, Offers, Onboarding and Reports all filter by the same six
 * dimensions. Keeping the shape — and the query-string encoding — in one
 * place means a deep link minted on one page ("Open in Candidates",
 * "Open in Offers", a clickable dashboard KPI) lands on another with the
 * exact same filters pre-applied.
 *
 * The state lives in the URL (via ``router.replace``) so every filtered
 * view is shareable and survives a refresh. Pure ``parseHrFilters`` /
 * ``hrFiltersToSearchParams`` helpers are exported so the encoding is
 * unit-testable without a router.
 */

export interface HrFilters {
  /** Application or offer status (snake_case key from the taxonomy). */
  status: string;
  /** Job slug. */
  job: string;
  department: string;
  company: string;
  /** Candidate / application source (public_form, manual_upload, …). */
  source: string;
  /** Inclusive date-range bounds, ISO ``YYYY-MM-DD``. */
  dateFrom: string;
  dateTo: string;
}

export const EMPTY_HR_FILTERS: HrFilters = {
  status: "",
  job: "",
  department: "",
  company: "",
  source: "",
  dateFrom: "",
  dateTo: "",
};

/** Map each filter field to its query-string key. The snake_case keys
 *  match the HR list APIs so deep links need no translation layer. */
const QUERY_KEYS: Record<keyof HrFilters, string> = {
  status: "status",
  job: "job",
  department: "department",
  company: "company",
  source: "source",
  dateFrom: "date_from",
  dateTo: "date_to",
};

type ParamsLike = Pick<URLSearchParams, "get">;

/** Parse a URLSearchParams (or Next's ReadonlyURLSearchParams) into the
 *  filter bundle, defaulting every absent key to an empty string. */
export function parseHrFilters(params: ParamsLike | null | undefined): HrFilters {
  if (!params) return { ...EMPTY_HR_FILTERS };
  const out = { ...EMPTY_HR_FILTERS };
  for (const field of Object.keys(QUERY_KEYS) as Array<keyof HrFilters>) {
    out[field] = params.get(QUERY_KEYS[field]) ?? "";
  }
  return out;
}

/** Serialise filters to URLSearchParams, omitting empty values so the
 *  URL stays clean. Stable key order keeps the encoding deterministic
 *  (handy for cache keys and round-trip assertions). */
export function hrFiltersToSearchParams(
  filters: Partial<HrFilters>,
): URLSearchParams {
  const params = new URLSearchParams();
  for (const field of Object.keys(QUERY_KEYS) as Array<keyof HrFilters>) {
    const value = filters[field];
    if (value) params.set(QUERY_KEYS[field], value);
  }
  return params;
}

/** Serialise filters to a query string (no leading ``?``). */
export function hrFiltersToQueryString(filters: Partial<HrFilters>): string {
  return hrFiltersToSearchParams(filters).toString();
}

/** Build a deep link to ``pathname`` carrying the given filters
 *  (optionally overriding a few). Used by the "Open in Candidates /
 *  Offers" report links and clickable dashboard KPIs. */
export function buildHrFilterHref(
  pathname: string,
  filters: Partial<HrFilters>,
  overrides?: Partial<HrFilters>,
): string {
  const qs = hrFiltersToQueryString({ ...filters, ...overrides });
  return qs ? `${pathname}?${qs}` : pathname;
}

/** True when no filter is set. */
export function hasActiveHrFilters(filters: HrFilters): boolean {
  return Object.values(filters).some((v) => v !== "");
}

export interface UseHrFiltersResult {
  filters: HrFilters;
  /** Set a single field and sync the URL. */
  setFilter: <K extends keyof HrFilters>(key: K, value: HrFilters[K]) => void;
  /** Merge several fields at once and sync the URL. */
  setFilters: (next: Partial<HrFilters>) => void;
  /** Clear every filter. */
  reset: () => void;
  /** Current filters encoded as a query string (no leading ``?``). */
  queryString: string;
  /** True when at least one filter is active. */
  hasActive: boolean;
}

/**
 * URL-synced HR filter state. Reads the current filters from the query
 * string and writes changes back via ``router.replace`` (no history
 * spam, no scroll jump).
 */
export function useHrFilters(): UseHrFiltersResult {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const filters = React.useMemo(
    () => parseHrFilters(searchParams),
    [searchParams],
  );

  const commit = React.useCallback(
    (next: HrFilters) => {
      const qs = hrFiltersToQueryString(next);
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname],
  );

  const setFilter = React.useCallback(
    <K extends keyof HrFilters>(key: K, value: HrFilters[K]) => {
      commit({ ...filters, [key]: value });
    },
    [commit, filters],
  );

  const setFilters = React.useCallback(
    (next: Partial<HrFilters>) => {
      commit({ ...filters, ...next });
    },
    [commit, filters],
  );

  const reset = React.useCallback(() => {
    commit({ ...EMPTY_HR_FILTERS });
  }, [commit]);

  return {
    filters,
    setFilter,
    setFilters,
    reset,
    queryString: hrFiltersToQueryString(filters),
    hasActive: hasActiveHrFilters(filters),
  };
}
