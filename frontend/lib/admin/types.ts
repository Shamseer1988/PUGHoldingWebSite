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
  signature: string | null;
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
