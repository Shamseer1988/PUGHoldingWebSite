/**
 * TypeScript surface for the SEO Configuration admin module (Phase 1).
 *
 * Mirrors `backend/app/schemas/seo.py`. The admin pages consume these
 * types; the public layout consumes a slimmer projection from
 * `lib/seo-api.ts`.
 */

export type VerificationProvider =
  | "google"
  | "bing"
  | "meta"
  | "pinterest"
  | "yandex"
  | "linkedin"
  | "tiktok"
  | "microsoft_ads"
  | "custom";

export type VerificationType =
  | "meta_tag"
  | "full_meta_tag"
  | "html_file"
  | "dns_txt";

export type VerificationStatus =
  | "pending"
  | "verified_manually"
  | "failed"
  | "dns_required";

export type TrackingProvider =
  | "google_tag_manager"
  | "google_analytics_ga4"
  | "meta_pixel"
  | "microsoft_clarity"
  | "linkedin_insight"
  | "tiktok_pixel"
  | "twitter_pixel"
  | "custom";

export type ScriptPlacement = "head" | "body_start" | "body_end";

export interface SeoSettings {
  id: number;
  site_name: string | null;
  default_meta_title: string | null;
  default_meta_description: string | null;
  default_meta_keywords: string | null;
  canonical_base_url: string | null;
  default_language: string | null;
  default_country: string | null;
  default_og_image: string | null;
  default_twitter_image: string | null;
  enable_sitemap: boolean;
  enable_robots: boolean;
  enable_open_graph: boolean;
  enable_twitter_cards: boolean;
  enable_json_ld: boolean;
  enable_canonical: boolean;
  enable_hreflang: boolean;
  enable_breadcrumb_schema: boolean;
  sitemap_default_changefreq: string | null;
  sitemap_default_priority: number | null;
  sitemap_include_static: boolean;
  sitemap_include_companies: boolean;
  sitemap_include_cms_pages: boolean;
  sitemap_include_news: boolean;
  robots_use_default: boolean;
  robots_custom_content: string | null;
  robots_extra_disallows: string | null;
  updated_by_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface SeoVerification {
  id: number;
  provider: VerificationProvider;
  verification_type: VerificationType;
  verification_name: string | null;
  verification_content: string | null;
  full_meta_tag: string | null;
  html_filename: string | null;
  html_file_content: string | null;
  dns_txt_value: string | null;
  status: VerificationStatus;
  is_active: boolean;
  notes: string | null;
  created_by_id: number | null;
  updated_by_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface TrackingIntegration {
  id: number;
  provider: TrackingProvider;
  tracking_id: string | null;
  secondary_id: string | null;
  data_layer_name: string;
  placement: ScriptPlacement;
  enable_noscript: boolean;
  consent_mode_enabled: boolean;
  debug_mode: boolean;
  is_active: boolean;
  notes: string | null;
  created_by_id: number | null;
  updated_by_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface SeoDashboard {
  canonical_base_url: string | null;
  sitemap_enabled: boolean;
  robots_enabled: boolean;
  gtm_active: boolean;
  gtm_id: string | null;
  ga4_active: boolean;
  ga4_id: string | null;
  meta_pixel_active: boolean;
  meta_pixel_id: string | null;
  clarity_active: boolean;
  clarity_id: string | null;
  google_verification_active: boolean;
  bing_verification_active: boolean;
  meta_verification_active: boolean;
  active_integrations: string[];
  active_verifications: string[];
  duplicate_tracking_warning: string | null;
  last_updated_at: string | null;
}
