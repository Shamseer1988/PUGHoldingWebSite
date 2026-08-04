/**
 * Server-side fetch helpers for the public Offers & Catalogue surface.
 *
 * Mirrors the pattern in ``lib/public-api.ts`` — every helper calls
 * the backend ``/api/v1/offers/*`` endpoints, returns plain typed
 * objects, and falls back to a safe value (empty list / null) so the
 * pages still render gracefully if the backend is unreachable.
 *
 * Browser-side calls (view beacon, download trigger) live in
 * ``lib/public-offers-client.ts``.
 */

import type {
  Catalogue,
  CatalogueDetail,
} from "@/lib/admin/marketing-types";
import { env } from "@/lib/env";


// ---------------------------------------------------------------------------
// Public payload shapes (mirror app/schemas/marketing.py)
// ---------------------------------------------------------------------------

export interface OfferIndexCampaign {
  slug: string;
  title: string;
  description: string | null;
  banner_image_url: string | null;
  theme_color: string | null;
  branch: string | null;
  start_date: string | null;
  end_date: string | null;
  is_featured: boolean;
  is_killer_offer: boolean;
  is_flash_sale: boolean;
  /** True when ``end_date`` is in the past. UI renders an
   *  ``EXPIRED`` badge + muted cover; the row stays in
   *  ``all_campaigns`` but is excluded from the highlighted
   *  carousels. */
  is_expired: boolean;
  catalogue_count: number;
  cover_image_url: string | null;
}

export interface BranchSummary {
  slug: string;
  name: string;
  city: string | null;
}

export interface BranchSocialLinks {
  facebook: string | null;
  instagram: string | null;
  tiktok: string | null;
  youtube: string | null;
  snapchat: string | null;
  x: string | null;
}

/** Payload for a branch storefront — ``/offers/{branch-slug}``. */
export interface BranchPage {
  slug: string;
  name: string;
  city: string | null;
  description: string | null;
  logo_url: string | null;
  hero_image_url: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
  whatsapp: string | null;
  opening_hours: string | null;
  maps_url: string | null;
  social: BranchSocialLinks;
  campaigns: OfferIndexCampaign[];
  catalogues: OffersIndexCatalogue[];
  other_branches: BranchSummary[];
}

export interface OffersIndexCatalogue {
  slug: string;
  title: string;
  description: string | null;
  cover_image_url: string | null;
  page_count: number;
  /** Branch label for the tile chip. ``null`` = all branches. */
  branch_name: string | null;
  is_featured: boolean;
  created_at: string | null;
}

export interface OffersIndex {
  featured: OfferIndexCampaign[];
  killer_offers: OfferIndexCampaign[];
  flash_sales: OfferIndexCampaign[];
  all_campaigns: OfferIndexCampaign[];
  all_catalogues: OffersIndexCatalogue[];
  branches: BranchSummary[];
}

export interface CampaignPublicDetail {
  slug: string;
  title: string;
  description: string | null;
  banner_image_url: string | null;
  theme_color: string | null;
  branch: string | null;
  start_date: string | null;
  end_date: string | null;
  /** See ``OfferIndexCampaign.is_expired`` — same semantics. The
   *  detail page surfaces this as a prominent banner notice. */
  is_expired: boolean;
  meta_title: string | null;
  meta_description: string | null;
  catalogues: Catalogue[];
}


// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function fetchPublic<T>(
  path: string,
  query?: Record<string, string | undefined>
): Promise<T | null> {
  const base = `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  let url = base;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v) params.set(k, v);
    }
    const qs = params.toString();
    if (qs) url = `${base}?${qs}`;
  }
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (response.status === 404) return null;
    if (!response.ok) {
      console.error(`[public-offers] ${url} -> ${response.status}`);
      return null;
    }
    return (await response.json()) as T;
  } catch (err) {
    console.error(`[public-offers] ${url} failed:`, err);
    return null;
  }
}

export interface OffersQuery {
  branch?: string;
  q?: string;
  killer?: boolean;
  featured?: boolean;
  flash?: boolean;
  include_expired?: boolean;
}

/**
 * Landing payload, with a flag distinguishing "no offers right now"
 * from "we couldn't reach the API".
 *
 * Those two states used to be indistinguishable: a failed fetch fell
 * back to an empty index and the page rendered a cheerful "no offers"
 * — so an outage looked like an editorial decision. ``unavailable``
 * lets the page say something honest instead.
 */
export type OffersIndexResult = OffersIndex & { unavailable?: boolean };

const EMPTY_INDEX: OffersIndex = {
  featured: [],
  killer_offers: [],
  flash_sales: [],
  all_campaigns: [],
  all_catalogues: [],
  branches: [],
};

export async function getOffersIndex(
  query?: OffersQuery
): Promise<OffersIndexResult> {
  const params: Record<string, string> = {};
  if (query?.branch) params.branch = query.branch;
  if (query?.q) params.q = query.q;
  // Only send the flags that are on — the API defaults them to false,
  // and an all-false query string is noise in the CDN cache key.
  if (query?.killer) params.killer = "true";
  if (query?.featured) params.featured = "true";
  if (query?.flash) params.flash = "true";
  if (query?.include_expired === false) params.include_expired = "false";

  const data = await fetchPublic<OffersIndex>("/offers", params);
  if (data === null) return { ...EMPTY_INDEX, unavailable: true };
  return data;
}

/** One branch storefront. ``null`` when the branch isn't published. */
export async function getBranchPage(
  slug: string
): Promise<BranchPage | null> {
  return fetchPublic<BranchPage>(
    `/offers/branch/${encodeURIComponent(slug)}`
  );
}

/** Branch picker options, for pages that don't need the full index. */
export async function getBranches(): Promise<BranchSummary[]> {
  return (await fetchPublic<BranchSummary[]>("/offers/branches")) ?? [];
}

export async function getCampaignBySlug(
  slug: string
): Promise<CampaignPublicDetail | null> {
  return fetchPublic<CampaignPublicDetail>(`/offers/${encodeURIComponent(slug)}`);
}

export async function getCatalogueBySlug(
  slug: string
): Promise<CatalogueDetail | null> {
  return fetchPublic<CatalogueDetail>(
    `/offers/catalogues/${encodeURIComponent(slug)}`
  );
}
