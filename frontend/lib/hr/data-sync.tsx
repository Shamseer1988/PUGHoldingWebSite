"use client";

/**
 * HR data-sync signal (recruitment overhaul, Phase 0).
 *
 * The HR console mostly fetches into local React state rather than the
 * TanStack Query cache, so there is no single cache to invalidate when a
 * status changes. This module provides a tiny pub/sub "something changed"
 * pulse instead:
 *
 *   - A mutation (candidate status change, offer transition, …) calls
 *     ``bump()`` after it succeeds.
 *   - The realtime WebSocket calls ``bump()`` when another operator's
 *     change arrives.
 *   - Every screen that shows recruitment status subscribes with
 *     ``useHrDataSync(refetch)`` — one line — and refetches on each pulse.
 *
 * It is intentionally coarse (one global counter, not per-entity keys): an
 * HR console has low query cardinality, so a refetch-everything pulse is
 * cheap and removes any chance of one screen lagging another. It composes
 * with the existing manual fetches; screens keep their own initial/filter
 * effects and just gain a refetch-on-change.
 */

import * as React from "react";

type HrDataSyncValue = {
  /** Monotonic counter; changes on every {@link HrDataSyncValue.bump}. */
  signal: number;
  /** Signal that HR data changed so every subscribed screen refetches. */
  bump: () => void;
};

const HrDataSyncContext = React.createContext<HrDataSyncValue | null>(null);

export function HrDataSyncProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [signal, setSignal] = React.useState(0);
  const bump = React.useCallback(() => setSignal((n) => n + 1), []);
  const value = React.useMemo(() => ({ signal, bump }), [signal, bump]);
  return (
    <HrDataSyncContext.Provider value={value}>
      {children}
    </HrDataSyncContext.Provider>
  );
}

/**
 * Returns ``bump()`` — call it after a successful mutation so every other
 * HR screen refetches. Safe no-op when rendered outside the provider (e.g.
 * an isolated component test), so call sites never need a guard.
 */
export function useHrDataBump(): () => void {
  const ctx = React.useContext(HrDataSyncContext);
  return ctx?.bump ?? noop;
}

/**
 * Re-run ``refetch`` whenever the global HR data signal changes. The
 * initial mount is skipped so this composes with a screen's own first
 * fetch instead of doubling it. ``refetch`` is read through a ref, so an
 * unstable callback identity does not re-subscribe.
 */
export function useHrDataSync(refetch: () => void): void {
  const ctx = React.useContext(HrDataSyncContext);
  const signal = ctx?.signal ?? 0;
  const latest = React.useRef(refetch);
  latest.current = refetch;
  const mounted = React.useRef(false);
  React.useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    latest.current();
  }, [signal]);
}

function noop(): void {
  /* outside provider — nothing to signal */
}
