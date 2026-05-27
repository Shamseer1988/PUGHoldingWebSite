"use client";

import * as React from "react";


const STORAGE_KEY = "pug:sidebar:collapsed";


/**
 * Persists "is the desktop sidebar collapsed?" in localStorage so the
 * state survives navigation and page reloads. SSR-safe: the initial
 * value is always ``false`` and we hydrate from localStorage in a
 * useEffect so the first render matches the server.
 *
 * Mobile drawer behaviour is unaffected — this hook is purely for the
 * lg+ "icons only vs icons + labels" toggle, not the open/closed
 * state of the off-canvas drawer.
 */
export function useSidebarCollapsed() {
  const [collapsed, setCollapsedRaw] = React.useState(false);
  const [hydrated, setHydrated] = React.useState(false);

  // Hydrate from localStorage after mount so the SSR + first-paint
  // render is deterministic.
  React.useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === "1") setCollapsedRaw(true);
    } catch {
      // Private mode, quota exceeded, etc. — fall through with the default.
    }
    setHydrated(true);
  }, []);

  const persist = React.useCallback((next: boolean) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    } catch {
      // Same defensive ignore.
    }
  }, []);

  const setCollapsed = React.useCallback(
    (next: boolean) => {
      setCollapsedRaw(next);
      persist(next);
    },
    [persist]
  );

  const toggle = React.useCallback(() => {
    setCollapsedRaw((prev) => {
      const next = !prev;
      persist(next);
      return next;
    });
  }, [persist]);

  return { collapsed, setCollapsed, toggle, hydrated };
}
