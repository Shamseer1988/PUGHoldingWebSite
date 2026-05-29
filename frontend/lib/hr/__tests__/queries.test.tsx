/**
 * HR recruitment analytics hook (Phase C-3).
 *
 * Exercises the wiring around ``useRecruitmentAnalytics``:
 *
 *   - Hits the right URL with the ``window_days`` query param.
 *   - Surfaces the payload as ``data`` on success.
 *   - Different windows produce different query keys (so changing
 *     the picker bypasses the cache instead of returning the wrong
 *     snapshot).
 *   - Errors flow through as ``HrApiError`` with status.
 */
import { describe, expect, test, vi, afterEach, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { HrApiError } from "@/lib/hr/api";
import { hrQueryKeys, useRecruitmentAnalytics } from "@/lib/hr/queries";

const hrApiMock = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock("@/lib/hr/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/hr/api")>(
    "@/lib/hr/api"
  );
  return {
    ...actual,
    hrApi: hrApiMock,
  };
});

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

function makeTestClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

beforeEach(() => {
  hrApiMock.get.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("hrQueryKeys.recruitmentAnalytics", () => {
  test("different windows produce different cache keys", () => {
    const a = hrQueryKeys.recruitmentAnalytics(30);
    const b = hrQueryKeys.recruitmentAnalytics(90);
    expect(a).not.toEqual(b);
  });
});

describe("useRecruitmentAnalytics", () => {
  test("requests the right URL with the window_days param", async () => {
    hrApiMock.get.mockResolvedValueOnce({
      window_days: 30,
      daily_applications: [],
      funnel_conversion: [],
      source_breakdown: [],
      time_to_hire: {
        overall_avg_days: null,
        sample_size: 0,
        by_source: [],
      },
    });

    const { result } = renderHook(() => useRecruitmentAnalytics(30), {
      wrapper: makeWrapper(makeTestClient()),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(hrApiMock.get).toHaveBeenCalledWith(
      "/hr/analytics/recruitment?window_days=30"
    );
    expect(result.current.data?.window_days).toBe(30);
  });

  test("HrApiError surfaces as error with status", async () => {
    hrApiMock.get.mockRejectedValueOnce(new HrApiError("Forbidden", 403));
    const { result } = renderHook(() => useRecruitmentAnalytics(90), {
      wrapper: makeWrapper(makeTestClient()),
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.status).toBe(403);
    expect(result.current.error?.message).toBe("Forbidden");
  });

  test("enabled=false defers the fetch", () => {
    renderHook(
      () => useRecruitmentAnalytics(90, { enabled: false }),
      { wrapper: makeWrapper(makeTestClient()) }
    );
    expect(hrApiMock.get).not.toHaveBeenCalled();
  });
});
