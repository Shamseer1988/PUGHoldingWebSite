/**
 * Mirror of the backend Pydantic schemas (app/schemas/cms.py).
 */

export type CompanyCategory = "distribution" | "retail" | "services";
export type NewsCategory = "company" | "event" | "press" | "csr";

export interface HeroSlide {
  id: number;
  eyebrow: string | null;
  title: string;
  description: string | null;
  cta_label: string | null;
  cta_href: string | null;
  secondary_cta_label: string | null;
  secondary_cta_href: string | null;
  background_image_url: string | null;
  background_video_url: string | null;
  gradient: string;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CompanyBrandLogo {
  id: number;
  image_url: string;
  name: string | null;
  link_url: string | null;
  display_order: number;
}

export interface CompanyBrandLogoInput {
  image_url: string;
  name?: string | null;
  link_url?: string | null;
  display_order?: number;
}

export interface CompanyService {
  id: number;
  name: string;
  display_order: number;
}

export interface Company {
  id: number;
  slug: string;
  name: string;
  category: CompanyCategory;
  short_description: string | null;
  long_description: string | null;
  /** Short premium description used only on the homepage Group Companies panel. */
  homepage_highlight_description: string | null;
  /** Newline-separated bullet points rendered as chips on the homepage panel. */
  homepage_highlight_points: string | null;
  /** Phase 18 follow-up — richer Group Companies homepage card + video. */
  homepage_group_highlight: string | null;
  homepage_group_stat_line: string | null;
  homepage_group_video_url: string | null;
  homepage_group_video_poster_url: string | null;
  branches: string | null;
  accent: string;
  initials: string;
  brand_logo_url: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  website: string | null;
  featured_image_url: string | null;
  cta_label: string | null;
  cta_url: string | null;
  is_highlighted: boolean;
  display_order: number;
  is_active: boolean;
  services: CompanyService[];
  brand_logos: CompanyBrandLogo[];
  created_at: string;
  updated_at: string;
}

export interface LeadershipMessage {
  id: number;
  slug: string;
  name: string;
  role: string;
  short_message: string | null;
  full_message: string | null;
  accent: string;
  initials: string;
  photo_url: string | null;
  signature: string | null;
  role_label: string | null;
  message_paragraph_1: string | null;
  message_paragraph_2: string | null;
  highlight_quote: string | null;
  signature_image_url: string | null;
  cta_label: string | null;
  cta_url: string | null;
  is_homepage_featured: boolean;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface NewsItem {
  id: number;
  slug: string;
  title: string;
  summary: string | null;
  body: string | null;
  category: NewsCategory;
  author: string | null;
  cover: string;
  cover_image_url: string | null;
  published_at: string;
  is_featured: boolean;
  is_published: boolean;
  created_at: string;
  updated_at: string;
}

export interface ContactMessage {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  department: string | null;
  subject: string | null;
  message: string;
  is_read: boolean;
  is_replied: boolean;
  is_archived: boolean;
  reply_body: string | null;
  replied_by_id: number | null;
  replied_at: string | null;
  created_at: string;
}

export interface NewsletterSubscriber {
  id: number;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface SiteSettings {
  id: number;
  site_name: string;
  tagline: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  contact_address: string | null;
  /**
   * Admin-pasted map embed shown on the public Contact page. May be
   * either a bare embed URL (Google Maps / OpenStreetMap) or a full
   * `<iframe>` snippet. The frontend sanitises the value at render
   * time and only honours iframes whose `src` resolves to a trusted
   * maps host.
   */
  contact_map_embed: string | null;
  whatsapp_number: string | null;
  social_linkedin: string | null;
  social_instagram: string | null;
  social_facebook: string | null;
  social_youtube: string | null;
  seo_default_title: string | null;
  seo_default_description: string | null;
  seo_keywords: string | null;

  // Featured-companies section
  featured_companies_enabled: boolean;
  featured_companies_eyebrow: string | null;
  featured_companies_title: string | null;
  featured_companies_subtitle: string | null;
  featured_companies_cta_label: string | null;
  featured_companies_cta_url: string | null;
  featured_companies_animation_enabled: boolean;

  // Page banners
  about_banner_image_url: string | null;
  about_banner_video_url: string | null;
  careers_banner_image_url: string | null;
  careers_banner_mobile_url: string | null;
  contact_banner_image_url: string | null;
  contact_banner_mobile_url: string | null;
  news_banner_image_url: string | null;
  news_banner_mobile_url: string | null;
  media_banner_image_url: string | null;
  media_banner_mobile_url: string | null;

  // Homepage About + Founder
  home_about_image_url: string | null;
  home_about_title: string | null;
  home_about_body: string | null;
  home_founder_image_url: string | null;
  home_founder_name: string | null;
  home_founder_role: string | null;
  home_founder_message: string | null;

  // Trusted-brands strip
  home_brand_logos: string | null;
  home_brand_strip_title: string | null;

  // Unified Leadership Messages section
  home_leadership_section_enabled: boolean;
  home_leadership_section_eyebrow: string | null;
  home_leadership_section_title: string | null;
  home_leadership_section_subtitle: string | null;
  home_leadership_animation_enabled: boolean;

  // Theme overrides (Phase 5 follow-up)
  theme_primary_hex: string | null;
  theme_accent_hex: string | null;
  theme_heading_font: string | null;
  theme_body_font: string | null;

  /**
   * When true the public site renders a maintenance page in place of
   * every public route. Admin (`/admin/*`) and HR (`/hr/*`) portals are
   * unaffected so the team can still log in to turn it back off.
   */
  maintenance_mode_enabled: boolean;
  /** Optional override copy shown on the maintenance page. */
  maintenance_message: string | null;
  /** Short "Back by" hint, e.g. "Tonight at 9 PM GMT". */
  maintenance_eta: string | null;
}

export interface UploadResponse {
  url: string;
  filename: string;
  size: number;
  mime_type: string;
}

export interface DashboardStat {
  key: string;
  label: string;
  value: number;
}

export interface MonthlyCount {
  month: string;
  count: number;
}

export interface DashboardSummary {
  stats: DashboardStat[];
  contact_messages_per_month: MonthlyCount[];
  news_per_month: MonthlyCount[];
  latest_contact_messages: ContactMessage[];
  latest_news: NewsItem[];
}

export interface AuditEntry {
  id: number;
  action: string;
  scope: string | null;
  actor_id: number | null;
  actor_email: string | null;
  target_type: string | null;
  target_id: string | null;
  ip_address: string | null;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

// Media gallery + pages (Phase 5 follow-up) -----------------------------

export type MediaKind = "image" | "video";

export interface MediaAsset {
  id: number;
  kind: MediaKind | string;
  filename: string;
  original_name: string | null;
  url: string;
  mime_type: string | null;
  file_size: number | null;
  file_hash: string;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  title: string | null;
  alt_text: string | null;
  tags: string | null;
  /**
   * When false the asset is hidden from the public /media gallery
   * (and per-company galleries). It stays available everywhere else
   * admins can pick it from — hero slides, CMS pages, leadership
   * photos — so this is "show in the public photo album" rather than
   * a soft-delete.
   */
  is_public: boolean;
  /**
   * Resized image variants generated by the backend at upload time.
   * Drives the public site's `<ResponsiveImage>` component so phones
   * download a 480-wide WebP instead of the 4MB original.
   *
   * `null` for assets uploaded before the optimization pipeline
   * existed (run `python -m app.scripts.backfill_image_variants` to
   * populate them) and for assets the optimizer couldn't decode
   * (SVG, videos, broken files).
   */
  variants: MediaVariants | null;
  uploaded_by_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface MediaVariants {
  webp: { thumb: string; medium: string; large: string };
  jpg: { thumb: string; medium: string; large: string };
}

export interface MediaUploadResult {
  asset: MediaAsset;
  deduped: boolean;
}


/**
 * A predefined public page whose hero + banner + named sections are
 * admin-editable. Mirrors the backend `SitePage` model.
 *
 * `sections` is a free-form dict keyed by section name. Each section
 * has at minimum a `body`; some also carry a `title` or `eyebrow`.
 * The shape is intentionally loose so adding new sections is a
 * frontend-only change.
 */
export type SitePageKey =
  | "about"
  | "companies"
  | "careers"
  | "contact"
  | "news"
  | "media";

export interface SitePageSection {
  eyebrow?: string | null;
  title?: string | null;
  body?: string | null;
}

export interface SitePage {
  id: number;
  page_key: SitePageKey;
  hero_eyebrow: string | null;
  hero_title: string | null;
  hero_description: string | null;
  banner_image_url: string | null;
  banner_mobile_url: string | null;
  banner_video_url: string | null;
  sections: Record<string, SitePageSection>;
  seo_title: string | null;
  seo_description: string | null;
  seo_keywords: string | null;
  updated_by_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface CMSPageListItem {
  id: number;
  slug: string;
  title: string;
  summary: string | null;
  is_published: boolean;
  display_order: number;
  published_at: string | null;
  updated_at: string;
}

export interface CMSPage {
  id: number;
  slug: string;
  title: string;
  eyebrow: string | null;
  summary: string | null;
  body: string | null;
  banner_image_url: string | null;
  banner_mobile_url: string | null;
  seo_title: string | null;
  seo_description: string | null;
  seo_keywords: string | null;
  is_published: boolean;
  display_order: number;
  published_at: string | null;
  updated_by_id: number | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Navigation menu (Phase 5 follow-up)
// ---------------------------------------------------------------------------

export type NavMegaKind = "companies";

export interface NavigationItemNode {
  id: number;
  parent_id: number | null;
  label: string;
  href: string;
  description: string | null;
  mega_kind: NavMegaKind | null;
  open_in_new_tab: boolean;
  display_order: number;
  is_active: boolean;
  children?: NavigationItemNode[];
}

export interface NavigationItemCreatePayload {
  label: string;
  href: string;
  description?: string | null;
  mega_kind?: NavMegaKind | null;
  open_in_new_tab?: boolean;
  display_order?: number;
  is_active?: boolean;
  parent_id?: number | null;
}

export type NavigationItemUpdatePayload = Partial<NavigationItemCreatePayload>;

// ---------------------------------------------------------------------------
// Users & Roles (Phase 5 follow-up)
// ---------------------------------------------------------------------------

export type Scope = "system" | "website" | "hr";

export interface RoleSummary {
  id: number;
  name: string;
  scope: Scope;
  description: string | null;
}

export interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  last_login_at: string | null;
  created_at: string;
  roles: RoleSummary[];
  scopes: Scope[];
}

export interface AdminUserCreatePayload {
  email: string;
  full_name: string;
  password: string;
  is_active: boolean;
  is_superuser: boolean;
  role_ids: number[];
}

export interface AdminUserUpdatePayload {
  full_name?: string;
  password?: string;
  is_active?: boolean;
  is_superuser?: boolean;
  role_ids?: number[];
}
