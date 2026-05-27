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
  catalogue_count: number;
  cover_image_url: string | null;
}

export interface OffersIndex {
  featured: OfferIndexCampaign[];
  killer_offers: OfferIndexCampaign[];
  flash_sales: OfferIndexCampaign[];
  all_campaigns: OfferIndexCampaign[];
  branches: string[];
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

export async function getOffersIndex(query?: {
  branch?: string;
  q?: string;
}): Promise<OffersIndex> {
  const data = await fetchPublic<OffersIndex>("/offers", query);
  return (
    data ?? {
      featured: [],
      killer_offers: [],
      flash_sales: [],
      all_campaigns: [],
      branches: [],
    }
  );
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
