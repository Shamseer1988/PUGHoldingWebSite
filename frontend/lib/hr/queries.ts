/**
 * TanStack Query hooks for the HR console (Phase C-3).
 *
 * Mirrors the admin queries surface from Phase B-4 — same retry
 * semantics, same cache invalidation discipline — scoped to the HR
 * data plane. The first consumer is the recruitment analytics page;
 * additional hooks land here as HR pages migrate off the manual
 * ``useEffect`` + ``setState`` pattern.
 */
import {
  useQuery,
  type UseQueryResult,
} from "@tanstack/react-query";

import { hrApi, HrApiError } from "@/lib/hr/api";
import type { RecruitmentAnalytics } from "@/lib/hr/types";

export const hrQueryKeys = {
  all: ["hr"] as const,
  recruitmentAnalytics: (windowDays: number) =>
    [...hrQueryKeys.all, "analytics", "recruitment", windowDays] as const,
};

export interface UseRecruitmentAnalyticsOptions {
  enabled?: boolean;
}

export function useRecruitmentAnalytics(
  windowDays: number,
  options: UseRecruitmentAnalyticsOptions = {}
): UseQueryResult<RecruitmentAnalytics, HrApiError> {
  return useQuery<RecruitmentAnalytics, HrApiError>({
    queryKey: hrQueryKeys.recruitmentAnalytics(windowDays),
    queryFn: () =>
      hrApi.get<RecruitmentAnalytics>(
        `/hr/analytics/recruitment?window_days=${windowDays}`
      ),
    enabled: options.enabled ?? true,
  });
}
