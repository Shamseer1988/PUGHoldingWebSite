import { describe, expect, it } from "vitest";

import type { OfferIndexCampaign } from "@/lib/public-offers";

import { filterCampaigns, type CampaignFilterState } from "../offers-landing";


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


const empty: CampaignFilterState = {
  branch: "",
  query: "",
  types: [],
  statuses: [],
};


describe("filterCampaigns — branch", () => {
  it("returns everything when branch is empty", () => {
    const a = mk({ slug: "a", branch: "Doha" });
    const b = mk({ slug: "b", branch: "Lusail" });
    expect(filterCampaigns([a, b], { ...empty })).toEqual([a, b]);
  });

  it("filters strictly by exact branch match", () => {
    const a = mk({ slug: "a", branch: "Doha" });
    const b = mk({ slug: "b", branch: "Lusail" });
    expect(filterCampaigns([a, b], { ...empty, branch: "Doha" })).toEqual([a]);
  });

  it("trims whitespace on the branch param", () => {
    const a = mk({ slug: "a", branch: "Doha" });
    expect(filterCampaigns([a], { ...empty, branch: "  Doha  " })).toEqual([a]);
  });
});


describe("filterCampaigns — offer type", () => {
  const killer = mk({ slug: "k", is_killer_offer: true });
  const featured = mk({ slug: "f", is_featured: true });
  const flash = mk({ slug: "z", is_flash_sale: true });
  const plain = mk({ slug: "p" });
  const all = [killer, featured, flash, plain];

  it("empty type list = no filter", () => {
    expect(filterCampaigns(all, { ...empty }).length).toBe(4);
  });

  it("single type returns only matching rows", () => {
    expect(filterCampaigns(all, { ...empty, types: ["killer"] })).toEqual([
      killer,
    ]);
  });

  it("multi-select is OR (killer OR featured returns both)", () => {
    expect(
      filterCampaigns(all, { ...empty, types: ["killer", "featured"] }),
    ).toEqual([killer, featured]);
  });

  it("a campaign with two flags matches when either is selected", () => {
    const both = mk({ slug: "both", is_killer_offer: true, is_featured: true });
    expect(
      filterCampaigns([both, plain], { ...empty, types: ["featured"] }),
    ).toEqual([both]);
    expect(
      filterCampaigns([both, plain], { ...empty, types: ["killer"] }),
    ).toEqual([both]);
  });
});


describe("filterCampaigns — status", () => {
  const live = mk({ slug: "live", is_expired: false });
  const dead = mk({ slug: "dead", is_expired: true });

  it("empty status list = no filter", () => {
    expect(filterCampaigns([live, dead], { ...empty })).toEqual([live, dead]);
  });

  it("running only excludes expired", () => {
    expect(
      filterCampaigns([live, dead], { ...empty, statuses: ["running"] }),
    ).toEqual([live]);
  });

  it("expired only excludes running", () => {
    expect(
      filterCampaigns([live, dead], { ...empty, statuses: ["expired"] }),
    ).toEqual([dead]);
  });

  it("both statuses selected = no filter (they cancel out)", () => {
    expect(
      filterCampaigns([live, dead], {
        ...empty,
        statuses: ["running", "expired"],
      }),
    ).toEqual([live, dead]);
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
    branch: "Lusail",
  });

  it("matches title", () => {
    expect(
      filterCampaigns([summer, eid], { ...empty, query: "Summer" }),
    ).toEqual([summer]);
  });

  it("matches description", () => {
    expect(
      filterCampaigns([summer, eid], { ...empty, query: "promotions" }),
    ).toEqual([eid]);
  });

  it("matches branch", () => {
    expect(
      filterCampaigns([summer, eid], { ...empty, query: "Lusail" }),
    ).toEqual([eid]);
  });

  it("is case-insensitive", () => {
    expect(filterCampaigns([summer, eid], { ...empty, query: "SWIM" })).toEqual(
      [summer],
    );
  });

  it("ignores surrounding whitespace", () => {
    expect(
      filterCampaigns([summer, eid], { ...empty, query: "  eid  " }),
    ).toEqual([eid]);
  });
});


describe("filterCampaigns — combined", () => {
  it("branch + type + status compose with AND across filter axes", () => {
    const a = mk({
      slug: "a",
      branch: "Doha",
      is_killer_offer: true,
      is_expired: false,
    });
    const b = mk({
      slug: "b",
      branch: "Doha",
      is_killer_offer: true,
      is_expired: true,
    });
    const c = mk({
      slug: "c",
      branch: "Lusail",
      is_killer_offer: true,
      is_expired: false,
    });
    const d = mk({
      slug: "d",
      branch: "Doha",
      is_featured: true,
      is_expired: false,
    });
    const result = filterCampaigns([a, b, c, d], {
      branch: "Doha",
      query: "",
      types: ["killer"],
      statuses: ["running"],
    });
    expect(result).toEqual([a]);
  });
});
