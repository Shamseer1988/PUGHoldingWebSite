/**
 * Public offers filtering.
 *
 * The branch rule is the one worth pinning: a campaign or catalogue
 * with no branch of its own runs group-wide, so selecting a branch
 * must still show it. Filtering strictly by branch would hide the main
 * weekly flyer the moment a shopper picks their store — which is
 * exactly the failure mode that made this page look empty.
 */
import { describe, expect, it } from "vitest";

import type {
  OfferIndexCampaign,
  OffersIndexCatalogue,
} from "@/lib/public-offers";

import {
  filterCampaigns,
  filterCatalogues,
  type CampaignFilterState,
} from "../offers-landing";

function mk(over: Partial<OfferIndexCampaign>): OfferIndexCampaign {
  return {
    slug: over.slug ?? "x",
    title: over.title ?? "Title",
    description: over.description ?? null,
    banner_image_url: over.banner_image_url ?? null,
    theme_color: over.theme_color ?? null,
    branch: over.branch ?? null,
    start_date: over.start_date ?? null,
    end_date: over.end_date ?? null,
    is_featured: over.is_featured ?? false,
    is_killer_offer: over.is_killer_offer ?? false,
    is_flash_sale: over.is_flash_sale ?? false,
    is_expired: over.is_expired ?? false,
    catalogue_count: over.catalogue_count ?? 1,
    cover_image_url: over.cover_image_url ?? null,
  };
}

function mkCat(
  over: Partial<OffersIndexCatalogue>,
): OffersIndexCatalogue {
  return {
    slug: over.slug ?? "c",
    title: over.title ?? "Flyer",
    description: over.description ?? null,
    cover_image_url: over.cover_image_url ?? null,
    page_count: over.page_count ?? 8,
    branch_name: over.branch_name ?? null,
    is_featured: over.is_featured ?? false,
    created_at: over.created_at ?? null,
  };
}

const empty: CampaignFilterState = {
  branchName: null,
  query: "",
  flags: [],
};

describe("filterCampaigns — branch", () => {
  it("returns everything when no branch is selected", () => {
    const a = mk({ slug: "a", branch: "Al Khor" });
    const b = mk({ slug: "b", branch: "Al Wakra" });
    expect(filterCampaigns([a, b], empty)).toEqual([a, b]);
  });

  it("keeps group-wide campaigns when a branch is selected", () => {
    // The load-bearing case: a campaign with no branch belongs to
    // every branch, so it must survive the filter.
    const groupWide = mk({ slug: "weekly", branch: null });
    const alKhor = mk({ slug: "khor", branch: "Al Khor" });
    const alWakra = mk({ slug: "wakra", branch: "Al Wakra" });
    expect(
      filterCampaigns([groupWide, alKhor, alWakra], {
        ...empty,
        branchName: "Al Khor",
      }),
    ).toEqual([groupWide, alKhor]);
  });

  it("matches branch case-insensitively and ignores stray whitespace", () => {
    const a = mk({ slug: "a", branch: "  al khor " });
    expect(
      filterCampaigns([a], { ...empty, branchName: "Al Khor" }),
    ).toEqual([a]);
  });
});

describe("filterCampaigns — promo flags", () => {
  const killer = mk({ slug: "k", is_killer_offer: true });
  const featured = mk({ slug: "f", is_featured: true });
  const flash = mk({ slug: "z", is_flash_sale: true });
  const plain = mk({ slug: "p" });
  const all = [killer, featured, flash, plain];

  it("no flags = no narrowing", () => {
    expect(filterCampaigns(all, empty)).toHaveLength(4);
  });

  it("a single flag returns only matching rows", () => {
    expect(filterCampaigns(all, { ...empty, flags: ["killer"] })).toEqual([
      killer,
    ]);
  });

  it("multiple promo flags OR together", () => {
    expect(
      filterCampaigns(all, { ...empty, flags: ["killer", "featured"] }),
    ).toEqual([killer, featured]);
  });

  it("a row with two flags matches when either is selected", () => {
    const both = mk({ slug: "both", is_killer_offer: true, is_featured: true });
    expect(
      filterCampaigns([both, plain], { ...empty, flags: ["featured"] }),
    ).toEqual([both]);
    expect(
      filterCampaigns([both, plain], { ...empty, flags: ["killer"] }),
    ).toEqual([both]);
  });
});

describe("filterCampaigns — ended", () => {
  const live = mk({ slug: "live", is_expired: false });
  const dead = mk({ slug: "dead", is_expired: true });

  it("hides ended campaigns by default", () => {
    expect(filterCampaigns([live, dead], empty)).toEqual([live]);
  });

  it("includes them once Ended is ticked", () => {
    expect(
      filterCampaigns([live, dead], { ...empty, flags: ["expired"] }),
    ).toEqual([live, dead]);
  });

  it("Ended is a state, not another OR term alongside promo flags", () => {
    // Killer + Ended means "killer offers, including finished ones" —
    // not "killer offers OR anything that ended".
    const endedKiller = mk({
      slug: "ek",
      is_killer_offer: true,
      is_expired: true,
    });
    const endedPlain = mk({ slug: "ep", is_expired: true });
    const liveKiller = mk({ slug: "lk", is_killer_offer: true });
    expect(
      filterCampaigns([endedKiller, endedPlain, liveKiller], {
        ...empty,
        flags: ["killer", "expired"],
      }),
    ).toEqual([endedKiller, liveKiller]);
  });
});

describe("filterCampaigns — free-text search", () => {
  const summer = mk({
    slug: "summer",
    title: "Summer Edit",
    description: "Hot deals on swimwear",
  });
  const eid = mk({
    slug: "eid",
    title: "Eid Mubarak",
    description: "Family promotions",
    branch: "Al Wakra",
  });

  it("matches title", () => {
    expect(filterCampaigns([summer, eid], { ...empty, query: "Summer" })).toEqual(
      [summer],
    );
  });

  it("matches description", () => {
    expect(
      filterCampaigns([summer, eid], { ...empty, query: "promotions" }),
    ).toEqual([eid]);
  });

  it("matches branch label", () => {
    expect(
      filterCampaigns([summer, eid], { ...empty, query: "Wakra" }),
    ).toEqual([eid]);
  });

  it("is case-insensitive and trims the query", () => {
    expect(filterCampaigns([summer, eid], { ...empty, query: "  SWIM " })).toEqual(
      [summer],
    );
  });
});

describe("filterCatalogues", () => {
  const groupWide = mkCat({ slug: "weekly", branch_name: null });
  const khor = mkCat({ slug: "khor", branch_name: "Al Khor" });
  const wakra = mkCat({ slug: "wakra", branch_name: "Al Wakra" });

  it("keeps group-wide flyers under a branch filter", () => {
    expect(
      filterCatalogues([groupWide, khor, wakra], {
        ...empty,
        branchName: "Al Khor",
      }),
    ).toEqual([groupWide, khor]);
  });

  it("narrows to featured when that flag is on", () => {
    const feat = mkCat({ slug: "f", is_featured: true });
    expect(
      filterCatalogues([feat, groupWide], { ...empty, flags: ["featured"] }),
    ).toEqual([feat]);
  });

  it("promo flags do not narrow catalogues", () => {
    // Killer/flash are campaign-level concepts; a catalogue has no
    // such field, so these must not silently empty the flyer grid.
    expect(
      filterCatalogues([groupWide, khor], {
        ...empty,
        flags: ["killer", "flash"],
      }),
    ).toEqual([groupWide, khor]);
  });

  it("searches title and description", () => {
    const ramadan = mkCat({ slug: "r", title: "Ramadan Flyer" });
    expect(
      filterCatalogues([ramadan, groupWide], { ...empty, query: "ramadan" }),
    ).toEqual([ramadan]);
  });
});
