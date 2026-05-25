/**
 * Public SEO API helpers.
 *
 * Used by:
 *   - the root layout to render verification meta tags + tracking
 *     script tags in `<head>`,
 *   - `app/sitemap.ts` to read the sitemap toggles,
 *   - `app/robots.ts` to fetch the rendered robots.txt body.
 *
 * The endpoints these wrap are all cacheable at the edge — the data
 * changes only when an admin edits SEO settings, which is rare.
 */
import { env } from "@/lib/env";

export interface PublicVerificationMeta {
  /** Set when the meta tag uses ``name="..."``. */
  name?: string | null;
  /** Set when the meta tag uses ``property="..."``. */
  property?: string | null;
  content: string;
}

export type PublicTrackingProvider =
  | "google_tag_manager"
  | "google_analytics_ga4"
  | "meta_pixel"
  | "microsoft_clarity"
  | "linkedin_insight"
  | "tiktok_pixel"
  | "twitter_pixel"
  | "custom";

export interface PublicTrackingIntegration {
  provider: PublicTrackingProvider;
  tracking_id: string;
  data_layer_name: string;
  placement: "head" | "body_start" | "body_end";
  enable_noscript: boolean;
  consent_mode_enabled: boolean;
  debug_mode: boolean;
}

export interface PublicSeoHeadFeed {
  site_name: string | null;
  default_meta_title: string | null;
  default_meta_description: string | null;
  canonical_base_url: string | null;
  default_language: string | null;
  enable_canonical: boolean;
  enable_open_graph: boolean;
  enable_twitter_cards: boolean;
  default_og_image: string | null;
  default_twitter_image: string | null;
  enable_sitemap: boolean;
  sitemap_include_static: boolean;
  sitemap_include_companies: boolean;
  sitemap_include_cms_pages: boolean;
  sitemap_include_news: boolean;
  sitemap_default_changefreq: string | null;
  sitemap_default_priority: number | null;
  verification_metas: PublicVerificationMeta[];
  integrations: PublicTrackingIntegration[];
}

const EMPTY_FEED: PublicSeoHeadFeed = {
  site_name: null,
  default_meta_title: null,
  default_meta_description: null,
  canonical_base_url: null,
  default_language: null,
  enable_canonical: true,
  enable_open_graph: true,
  enable_twitter_cards: true,
  default_og_image: null,
  default_twitter_image: null,
  enable_sitemap: true,
  sitemap_include_static: true,
  sitemap_include_companies: true,
  sitemap_include_cms_pages: true,
  sitemap_include_news: true,
  sitemap_default_changefreq: null,
  sitemap_default_priority: null,
  verification_metas: [],
  integrations: [],
};

/** Re-validate the SEO head feed at most once per minute. */
const SEO_HEAD_REVALIDATE_SECONDS = 60;

export async function getPublicSeoHead(): Promise<PublicSeoHeadFeed> {
  try {
    const res = await fetch(`${env.apiBaseUrl}/public/seo/head`, {
      next: { revalidate: SEO_HEAD_REVALIDATE_SECONDS },
    });
    if (!res.ok) return EMPTY_FEED;
    return (await res.json()) as PublicSeoHeadFeed;
  } catch (err) {
    console.error("getPublicSeoHead failed:", err);
    return EMPTY_FEED;
  }
}

/** Fetch the rendered robots.txt body. Returns null on failure. */
export async function getPublicRobotsTxt(): Promise<string | null> {
  try {
    const res = await fetch(`${env.apiBaseUrl}/public/seo/robots`, {
      next: { revalidate: SEO_HEAD_REVALIDATE_SECONDS },
    });
    if (!res.ok) return null;
    return await res.text();
  } catch (err) {
    console.error("getPublicRobotsTxt failed:", err);
    return null;
  }
}

/**
 * Picks the active GTM integration ID (if any) — convenience helper
 * used by `<SeoBodyStart>` to render the GTM noscript iframe early in
 * the body without re-fetching.
 */
export function pickGtmId(feed: PublicSeoHeadFeed): string | null {
  const row = feed.integrations.find(
    (i) => i.provider === "google_tag_manager" && i.tracking_id
  );
  return row?.tracking_id ?? null;
}
