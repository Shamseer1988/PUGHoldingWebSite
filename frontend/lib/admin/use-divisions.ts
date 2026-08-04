"use client";

/**
 * Shared branch (division) list for admin forms.
 *
 * Campaigns, catalogues and the QR console all need the same "which
 * branch?" dropdown. Fetching it in one hook keeps the option list
 * identical across all three — if the campaign form and the catalogue
 * form disagreed about what a branch is, targeting would silently
 * diverge between a campaign and the flyer inside it.
 *
 * The QR-codes endpoint is the source of truth for branches, so this
 * reads from there rather than scraping distinct labels off existing
 * campaigns (the old free-text approach, which could only ever offer
 * branches that already had a campaign).
 */

import * as React from "react";

import { adminApi, AdminApiError } from "@/lib/admin/api";

export interface DivisionOption {
  id: number;
  slug: string;
  name: string;
  city: string | null;
  is_active: boolean;
}

interface DivisionListResponse {
  items: DivisionOption[];
  total: number;
}

/**
 * Sentinel the API accepts to mean "clear this back to all branches".
 *
 * A PATCH body can't distinguish "field omitted" from "field set to
 * null" — both serialise to the same thing — so the backend reads 0
 * as an explicit clear. Exported so form code never hardcodes it.
 */
export const ALL_BRANCHES = 0;

export function useDivisions() {
  const [divisions, setDivisions] = React.useState<DivisionOption[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await adminApi.get<DivisionListResponse>(
          "/admin/marketing/divisions?include_inactive=false&limit=200",
        );
        if (!cancelled) setDivisions(data.items);
      } catch (err) {
        // Non-fatal: the form still works, the dropdown just falls
        // back to "All branches" only. A campaign editor shouldn't
        // become unusable because the branch list failed to load.
        if (!cancelled) setError((err as AdminApiError).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { divisions, loading, error };
}

/** Label for a branch id — used in read-only list cells. */
export function branchLabel(
  divisions: DivisionOption[],
  divisionId: number | null | undefined,
  legacyBranch?: string | null,
): string {
  if (divisionId) {
    const hit = divisions.find((d) => d.id === divisionId);
    if (hit) return hit.name;
  }
  // Pre-migration rows carry only the free-text label. Showing it
  // (rather than "All branches") keeps the admin list honest about
  // what the row actually targets.
  if (legacyBranch) return legacyBranch;
  return "All branches";
}
