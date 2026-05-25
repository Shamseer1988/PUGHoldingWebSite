/**
 * Smoke tests for the uniform-row StatsStrip.
 *
 * The component renders five equal glass cards; the brief's earlier
 * "hero / accent / sectors" bento was replaced with a single elegant
 * row that matches the brand. We still keep the data-mocking tests
 * that prove the StatItem extension fields don't break rendering.
 */
import { afterEach, describe, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";


afterEach(() => {
  // `vi.doMock` registrations are sticky across tests — they queue for
  // the next import even after `resetModules`. We have to explicitly
  // unmock the data module so the next test starts from the real STATS.
  vi.doUnmock("@/lib/dummy-data/site-content");
  vi.resetModules();
  vi.restoreAllMocks();
  cleanup();
});


describe("StatsStrip", () => {
  test("renders all 5 stat labels", async () => {
    const { StatsStrip } = await import("@/components/site/stats-strip");
    render(<StatsStrip />);
    expect(screen.getByText("Group companies")).toBeInTheDocument();
    expect(screen.getByText("Retail branches")).toBeInTheDocument();
    expect(screen.getByText("Employees")).toBeInTheDocument();
    expect(screen.getByText("Business sectors")).toBeInTheDocument();
    expect(screen.getByText("Customers served daily")).toBeInTheDocument();
  });

  test("renders one card per STAT entry, each with role='listitem'", async () => {
    const { StatsStrip } = await import("@/components/site/stats-strip");
    const { getAllByRole } = render(<StatsStrip />);
    // 5 cards, no separate `hero` outside the list.
    expect(getAllByRole("listitem")).toHaveLength(5);
  });

  test("a stat with tile_variant omitted still renders without crashing", async () => {
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

  test("trend pill text shows for stats that declare a percentage or label", async () => {
    const { StatsStrip } = await import("@/components/site/stats-strip");
    const { container } = render(<StatsStrip />);
    // The pill renders `<icon>{text}`, which splits the text node from
    // the leading SVG — getByText with a string fails because the
    // span's textContent starts with the icon's "" alt. Use a substring
    // match on the flattened text instead.
    const text = container.textContent ?? "";
    expect(text).toContain("+4 in Q2");
    expect(text).toContain("+12% YoY");
  });

  test("each card carries an aria-label with the final value + label", async () => {
    const { StatsStrip } = await import("@/components/site/stats-strip");
    render(<StatsStrip />);
    // Built from `${value.toLocaleString()}${suffix ?? ""} ${label.toLowerCase()}`
    expect(
      screen.getByLabelText("14 group companies")
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("100,000+ customers served daily")
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("2,500+ employees")
    ).toBeInTheDocument();
  });

  test("reduced motion: final numbers visible on first render", async () => {
    // Mock matchMedia BEFORE the dynamic import so our local
    // usePrefersReducedMotion hook picks up reduced-motion at first paint.
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
    (window as { matchMedia: typeof window.matchMedia }).matchMedia =
      fakeMatchMedia as typeof window.matchMedia;
    vi.resetModules();

    try {
      const { StatsStrip } = await import("@/components/site/stats-strip");
      const { container } = render(<StatsStrip />);
      // Counter renders the formatted final value into the first
      // paint when reduced motion is active — no 0 → target ramp.
      const text = container.textContent ?? "";
      expect(text).toContain("100,000+");
      expect(text).toContain("2,500+");
      expect(text).toContain("56+");
      expect(text).toContain("14");
      expect(text).toContain("3");
      // And no half-finished "0" sitting where a final number should be.
      expect(text).not.toMatch(/\b0\b/);
    } finally {
      (window as { matchMedia: typeof window.matchMedia }).matchMedia = original;
    }
  });
});
