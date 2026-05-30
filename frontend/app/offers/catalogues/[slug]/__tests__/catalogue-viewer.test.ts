import { describe, expect, it } from "vitest";

import { getVisibleIndices } from "../catalogue-viewer";


// ---------------------------------------------------------------------------
// getVisibleIndices — single source of truth for "which page indices are
// actually rendered at ``pageIndex``". Highlights + status readout rely on
// this so thumbnail / outline navigation lands on the visible page set even
// when react-pageflip is in spread (showCover, landscape) mode.
// ---------------------------------------------------------------------------


describe("getVisibleIndices", () => {
  // ----- Empty catalogue ----------------------------------------------------

  it("returns an empty array when there are no pages", () => {
    expect(getVisibleIndices(0, 0, false)).toEqual([]);
    expect(getVisibleIndices(0, 0, true)).toEqual([]);
  });

  // ----- Portrait (mobile) — every spread is one page ----------------------

  it("portrait: returns just the single visible page", () => {
    expect(getVisibleIndices(0, 24, true)).toEqual([0]);
    expect(getVisibleIndices(11, 24, true)).toEqual([11]);
    expect(getVisibleIndices(23, 24, true)).toEqual([23]);
  });

  // ----- Landscape with showCover — even page count -------------------------

  it("landscape even total: cover is alone on the first spread", () => {
    // pageCount=24 → spreads [0] [1,2] [3,4] … [21,22] [23]
    expect(getVisibleIndices(0, 24, false)).toEqual([0]);
  });

  it("landscape even total: paired spreads return both pages", () => {
    expect(getVisibleIndices(1, 24, false)).toEqual([1, 2]);
    expect(getVisibleIndices(3, 24, false)).toEqual([3, 4]);
    expect(getVisibleIndices(21, 24, false)).toEqual([21, 22]);
  });

  it("landscape even total: back cover is alone on the last spread", () => {
    // Last index 23 with pageCount=24 (even) → back cover alone.
    expect(getVisibleIndices(23, 24, false)).toEqual([23]);
  });

  // ----- Landscape with showCover — odd page count --------------------------

  it("landscape odd total: cover alone, last index paired as right-side", () => {
    // pageCount=25 → [0] [1,2] [3,4] … [21,22] [23,24]
    expect(getVisibleIndices(0, 25, false)).toEqual([0]);
    expect(getVisibleIndices(23, 25, false)).toEqual([23, 24]);
  });

  // ----- Boundary cases -----------------------------------------------------

  it("clamps the upper bound when pageIndex+1 would overflow", () => {
    // Pathological state — if the library somehow lands on the very
    // last index but the layout is odd / paired, we should never
    // return an out-of-range index.
    expect(getVisibleIndices(2, 3, false)).toEqual([2]);
  });

  it("two-page total renders both as a paired spread", () => {
    // pageCount=2 with showCover lays out as [0] [1] in practice
    // because there isn't room for a pair after the cover, but the
    // helper falls back to "paired if pageIndex+1 < pageCount" so a
    // pageIndex of 1 with pageCount=2 still pairs sensibly. The
    // cover case stays alone.
    expect(getVisibleIndices(0, 2, false)).toEqual([0]);
    // Edge: pageIndex=1, pageCount=2 (even) → back-cover-alone.
    expect(getVisibleIndices(1, 2, false)).toEqual([1]);
  });
});
