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
  branches: string | null;
  accent: string;
  initials: string;
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
  uploaded_by_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface MediaUploadResult {
  asset: MediaAsset;
  deduped: boolean;
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
