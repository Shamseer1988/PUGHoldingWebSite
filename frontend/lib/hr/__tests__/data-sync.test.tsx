/**
 * HR data-sync signal (recruitment overhaul, Phase 0).
 *
 * The signal is the propagation backbone for "no module shows outdated
 * status": a mutation calls ``bump()`` and every subscribed screen
 * refetches. These tests pin the contract the screens rely on:
 *
 *   - The initial mount does NOT fire (so it composes with a screen's
 *     own first fetch instead of doubling it).
 *   - ``bump()`` fires every subscriber, every time.
 *   - The latest ``refetch`` closure is used without re-subscribing.
 *   - ``useHrDataBump`` is a safe no-op outside the provider.
 */
import { describe, expect, test, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import * as React from "react";

import {
  HrDataSyncProvider,
  useHrDataBump,
  useHrDataSync,
} from "@/lib/hr/data-sync";

function Wrapper({ children }: { children: React.ReactNode }) {
  return <HrDataSyncProvider>{children}</HrDataSyncProvider>;
}

describe("HrDataSync", () => {
  test("does not fire the subscriber on initial mount", () => {
    const refetch = vi.fn();
    renderHook(() => useHrDataSync(refetch), { wrapper: Wrapper });
    expect(refetch).not.toHaveBeenCalled();
  });

  test("bump() triggers every subscriber, every time", () => {
    const refetchA = vi.fn();
    const refetchB = vi.fn();
    const { result } = renderHook(
      () => {
        const bump = useHrDataBump();
        useHrDataSync(refetchA);
        useHrDataSync(refetchB);
        return bump;
      },
      { wrapper: Wrapper }
    );

    act(() => result.current());
    expect(refetchA).toHaveBeenCalledTimes(1);
    expect(refetchB).toHaveBeenCalledTimes(1);

    act(() => result.current());
    expect(refetchA).toHaveBeenCalledTimes(2);
    expect(refetchB).toHaveBeenCalledTimes(2);
  });

  test("uses the latest refetch closure without re-subscribing", () => {
    const first = vi.fn();
    const second = vi.fn();
    const { result, rerender } = renderHook(
      ({ cb }: { cb: () => void }) => {
        const bump = useHrDataBump();
        useHrDataSync(cb);
        return bump;
      },
      { wrapper: Wrapper, initialProps: { cb: first } }
    );

    rerender({ cb: second });
    act(() => result.current());

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });

  test("useHrDataBump is a safe no-op outside the provider", () => {
    const { result } = renderHook(() => useHrDataBump());
    expect(() => result.current()).not.toThrow();
  });
});
