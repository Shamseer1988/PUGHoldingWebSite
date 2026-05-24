/**
 * Smoke tests for the bento StatsStrip.
 *
 * The dummy STATS array is module-level static, so test (b) (hero
 * placement is data-driven) re-mocks the data import and re-imports
 * the component before rendering. Everything else uses the real data.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";


afterEach(() => {
  vi.resetModules();
  vi.restoreAllMocks();
  cleanup();
});


describe("StatsStrip (bento)", () => {
  test("renders all 5 stat labels", async () => {
    const { StatsStrip } = await import("@/components/site/stats-strip");
    render(<StatsStrip />);
    expect(screen.getByText("Group companies")).toBeInTheDocument();
    expect(screen.getByText("Retail branches")).toBeInTheDocument();
    expect(screen.getByText("Employees")).toBeInTheDocument();
    expect(screen.getByText("Business sectors")).toBeInTheDocument();
    expect(screen.getByText("Customers served daily")).toBeInTheDocument();
  });

  test("hero tile is picked by tile_variant, regardless of array order", async () => {
    // Re-mock the data module so the hero is no longer last in the
    // array — we want to prove ordering doesn't drive layout.
    vi.doMock("@/lib/dummy-data/site-content", async () => {
      const real = await vi.importActual<
        typeof import("@/lib/dummy-data/site-content")
      >("@/lib/dummy-data/site-content");
      const hero = real.STATS.find((s) => s.tile_variant === "hero")!;
      const rest = real.STATS.filter((s) => s.tile_variant !== "hero");
      // Hero first, supporting tiles after.
      return { ...real, STATS: [hero, ...rest] };
    });

    const { StatsStrip } = await import("@/components/site/stats-strip");
    const { container } = render(<StatsStrip />);

    // The hero tile is the only one with the dot-grid utility, so we
    // find it then check the label inside that subtree.
    const heroNode = container.querySelector(".pug-dotgrid");
    expect(heroNode).not.toBeNull();
    expect(heroNode!.textContent).toContain("Customers served daily");
  });

  test("a stat without tile_variant still renders as a default tile", async () => {
    vi.doMock("@/lib/dummy-data/site-content", async () => {
      const real = await vi.importActual<
        typeof import("@/lib/dummy-data/site-content")
      >("@/lib/dummy-data/site-content");
      const stripped = real.STATS.map(({ tile_variant: _drop, ...rest }) => ({
        ...rest,
      }));
      return { ...real, STATS: stripped };
    });

    const { StatsStrip } = await import("@/components/site/stats-strip");
    // Should not throw and should still render every label.
    render(<StatsStrip />);
    for (const label of [
      "Group companies",
      "Retail branches",
      "Employees",
      "Business sectors",
      "Customers served daily",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  test("no sparkline path when sparkline_points is undefined", async () => {
    // Strip sparkline data off every stat and re-import.
    vi.doMock("@/lib/dummy-data/site-content", async () => {
      const real = await vi.importActual<
        typeof import("@/lib/dummy-data/site-content")
      >("@/lib/dummy-data/site-content");
      const stripped = real.STATS.map(
        ({ sparkline_points: _drop, ...rest }) => ({ ...rest })
      );
      return { ...real, STATS: stripped };
    });

    const { StatsStrip } = await import("@/components/site/stats-strip");
    const { container } = render(<StatsStrip />);
    // Lucide icons render as <svg>, so we narrow to the sparkline's
    // signature viewBox (200x50) — the icons use 24x24.
    expect(container.querySelector("svg[viewBox='0 0 200 50']")).toBeNull();
  });

  test("no trend pill when both trend_percent and trend_label are absent", async () => {
    vi.doMock("@/lib/dummy-data/site-content", async () => {
      const real = await vi.importActual<
        typeof import("@/lib/dummy-data/site-content")
      >("@/lib/dummy-data/site-content");
      const stripped = real.STATS.map(
        ({ trend_percent: _p, trend_label: _l, ...rest }) => ({ ...rest })
      );
      return { ...real, STATS: stripped };
    });

    const { StatsStrip } = await import("@/components/site/stats-strip");
    render(<StatsStrip />);
    expect(screen.queryByText(/% YoY/)).toBeNull();
    expect(screen.queryByText(/in Q2/)).toBeNull();
  });

  test("reduced motion: final numbers visible on first render", async () => {
    // Framer-motion's useReducedMotion reads matchMedia ONCE when its
    // module is first loaded (singleton subscription). To convince it
    // that the user prefers reduced motion, we have to:
    //   1. install the matchMedia mock,
    //   2. reset module cache so framer-motion re-initialises against
    //      the new matchMedia,
    //   3. dynamically import the component (which pulls a fresh
    //      framer-motion).
    const reducedMql: MediaQueryList = {
      matches: true,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    };
    const fakeMatchMedia = (query: string): MediaQueryList =>
      query.includes("prefers-reduced-motion")
        ? reducedMql
        : { ...reducedMql, matches: false, media: query };

    const original = window.matchMedia;
    // Direct assignment — Object.defineProperty in test-setup.ts made
    // the property writable but not configurable, so vi.spyOn can't
    // install its descriptor reliably across vitest versions.
    (window as { matchMedia: typeof window.matchMedia }).matchMedia =
      fakeMatchMedia as typeof window.matchMedia;
    vi.resetModules();

    try {
      const { StatsStrip } = await import("@/components/site/stats-strip");
      const { container } = render(<StatsStrip />);
      // Each number nests as <strong><motion.span>…</motion.span></strong>
      // which makes both the parent and the child match a textContent
      // matcher (it's the same string). Cleaner to assert on the
      // flattened container text — under reduced motion the Counter
      // skips the 0 → target ramp and writes the final value into the
      // first render, so each formatted value must appear directly.
      const text = container.textContent ?? "";
      expect(text).toContain("100,000+");
      expect(text).toContain("2,500+");
      expect(text).toContain("56+");
      expect(text).toContain("14");
      expect(text).toContain("3");
      // No "0" zero-padding from a half-finished count-up.
      expect(text).not.toMatch(/\b0\b/);
    } finally {
      (window as { matchMedia: typeof window.matchMedia }).matchMedia =
        original;
    }
  });
});
