/**
 * Server-side fetch helpers for the public website.
 *
 * Every helper:
 *   - calls the backend `/api/v1/public/*` endpoints
 *   - returns plain typed objects (no Response wrapping)
 *   - uses Next.js fetch revalidation (60 seconds by default)
 *   - returns a safe fallback if the backend is unreachable so the
 *     page still renders gracefully
 *
 * For client-side form submissions, use `lib/public-api-client.ts`.
 */

import type {
  Company,
  ContactMessage,
  HeroSlide,
  LeadershipMessage,
  NewsItem,
  NewsletterSubscriber,
  SiteSettings,
} from "@/lib/admin/types";
import { env } from "@/lib/env";

const REVALIDATE_SECONDS = 60;

interface FetchOptions {
  /** Override the default revalidate window. */
  revalidate?: number;
  /** Skip cache entirely (e.g. for previewing). */
  noStore?: boolean;
}

async function fetchPublic<T>(
  path: string,
  options: FetchOptions = {}
): Promise<T | null> {
  const url = `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  try {
    const response = await fetch(url, {
      next: options.noStore
        ? undefined
        : { revalidate: options.revalidate ?? REVALIDATE_SECONDS },
      cache: options.noStore ? "no-store" : undefined,
    });
    if (response.status === 404) {
      return null;
    }
    if (!response.ok) {
      console.error(
        `Public API ${url} returned ${response.status}: ${await response.text()}`
      );
      return null;
    }
    return (await response.json()) as T;
  } catch (error) {
    console.error(`Public API ${url} failed:`, error);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Read helpers
// ---------------------------------------------------------------------------

export async function getHeroSlides(): Promise<HeroSlide[]> {
  return (await fetchPublic<HeroSlide[]>("/public/hero-slides")) ?? [];
}

export interface CompaniesQuery {
  category?: "distribution" | "retail" | "services";
}

export async function getCompanies(query?: CompaniesQuery): Promise<Company[]> {
  const search = query?.category ? `?category=${query.category}` : "";
  return (await fetchPublic<Company[]>(`/public/companies${search}`)) ?? [];
}

export async function getCompanyBySlug(slug: string): Promise<Company | null> {
  return fetchPublic<Company>(`/public/companies/${encodeURIComponent(slug)}`);
}

export async function getLeadership(): Promise<LeadershipMessage[]> {
  return (await fetchPublic<LeadershipMessage[]>("/public/leadership")) ?? [];
}

export interface NewsQuery {
  featured?: boolean;
  limit?: number;
}

export async function getNews(query?: NewsQuery): Promise<NewsItem[]> {
  const params = new URLSearchParams();
  if (query?.featured !== undefined) params.set("featured", String(query.featured));
  if (query?.limit) params.set("limit", String(query.limit));
  const search = params.toString() ? `?${params}` : "";
  return (await fetchPublic<NewsItem[]>(`/public/news${search}`)) ?? [];
}

export async function getNewsBySlug(slug: string): Promise<NewsItem | null> {
  return fetchPublic<NewsItem>(`/public/news/${encodeURIComponent(slug)}`);
}

// CMS pages + media gallery (Phase 5 follow-up) ---------------------------

export interface PublicPage {
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
  created_at: string;
  updated_at: string;
}

export interface PublicMediaAsset {
  id: number;
  kind: "image" | "video" | string;
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
  created_at: string;
  updated_at: string;
}

export async function getPages(): Promise<PublicPage[]> {
  return (await fetchPublic<PublicPage[]>("/public/pages")) ?? [];
}

export async function getPageBySlug(slug: string): Promise<PublicPage | null> {
  return fetchPublic<PublicPage>(`/public/pages/${encodeURIComponent(slug)}`);
}

export interface HomepageLeadershipCard {
  slug: string;
  role_type: string;
  role_label: string | null;
  name: string;
  role: string;
  designation: string | null;
  initials: string;
  accent: string;
  photo_url: string | null;
  signature_image_url: string | null;
  signature: string | null;
  highlight_quote: string | null;
  message_paragraph_1: string | null;
  message_paragraph_2: string | null;
  cta_label: string | null;
  cta_url: string | null;
  display_order: number;
  is_active: boolean;
}

export interface HomepageLeadershipSection {
  enabled: boolean;
  eyebrow: string | null;
  title: string | null;
  subtitle: string | null;
  animation_enabled: boolean;
  messages: HomepageLeadershipCard[];
}

const FALLBACK_LEADERSHIP_SECTION: HomepageLeadershipSection = {
  enabled: true,
  eyebrow: "Leadership messages",
  title: "Guided by vision, driven by excellence",
  subtitle: "A message from the leadership of Paris United Group Holding.",
  animation_enabled: true,
  messages: [],
};

export async function getHomepageLeadership(): Promise<HomepageLeadershipSection> {
  return (
    (await fetchPublic<HomepageLeadershipSection>(
      "/public/homepage/leadership-messages"
    )) ?? FALLBACK_LEADERSHIP_SECTION
  );
}


// ---------------------------------------------------------------------------
// Trusted Brands showcase
// ---------------------------------------------------------------------------


export interface HomepageTrustedBrand {
  id: number;
  brand_name: string;
  logo_url: string | null;
  logo_url_alt: string | null;
  link_url: string | null;
  category: string | null;
  is_highlight: boolean;
  display_order: number;
  is_active: boolean;
}

export interface HomepageTrustedBrandsSection {
  enabled: boolean;
  eyebrow: string | null;
  title: string | null;
  subtitle: string | null;
  animation_enabled: boolean;
  layout_mode: "marquee" | "grid" | "carousel";
  brands: HomepageTrustedBrand[];
}

const FALLBACK_TRUSTED_BRANDS: HomepageTrustedBrandsSection = {
  enabled: true,
  eyebrow: "Trusted brands we work with",
  title: "Trusted by strong brands",
  subtitle: null,
  animation_enabled: true,
  layout_mode: "marquee",
  brands: [],
};

export async function getHomepageTrustedBrands(): Promise<HomepageTrustedBrandsSection> {
  return (
    (await fetchPublic<HomepageTrustedBrandsSection>(
      "/public/homepage/trusted-brands"
    )) ?? FALLBACK_TRUSTED_BRANDS
  );
}


export async function getMediaGallery(
  options: {
    kind?: "image" | "video";
    /**
     * Match a single tag token in the asset's comma-separated `tags`
     * field. Use a company slug (per-company gallery) or a category
     * like `stores` / `events` / `team` / `campaigns`.
     */
    tag?: string;
    limit?: number;
  } = {}
): Promise<PublicMediaAsset[]> {
  const params = new URLSearchParams();
  if (options.kind) params.set("kind", options.kind);
  if (options.tag) params.set("tag", options.tag);
  if (options.limit) params.set("limit", String(options.limit));
  const suffix = params.toString() ? `?${params}` : "";
  return (await fetchPublic<PublicMediaAsset[]>(`/public/media${suffix}`)) ?? [];
}

const FALLBACK_SETTINGS: SiteSettings = {
  id: 1,
  site_name: "Paris United Group Holding",
  tagline: null,
  contact_phone: null,
  contact_email: null,
  contact_address: null,
  contact_map_embed: null,
  whatsapp_number: null,
  social_linkedin: null,
  social_instagram: null,
  social_facebook: null,
  social_youtube: null,
  seo_default_title: null,
  seo_default_description: null,
  seo_keywords: null,
  featured_companies_enabled: true,
  featured_companies_eyebrow: null,
  featured_companies_title: null,
  featured_companies_subtitle: null,
  featured_companies_cta_label: null,
  featured_companies_cta_url: null,
  featured_companies_animation_enabled: true,
  about_banner_image_url: null,
  about_banner_video_url: null,
  careers_banner_image_url: null,
  careers_banner_mobile_url: null,
  contact_banner_image_url: null,
  contact_banner_mobile_url: null,
  news_banner_image_url: null,
  news_banner_mobile_url: null,
  home_about_image_url: null,
  home_about_title: null,
  home_about_body: null,
  home_founder_image_url: null,
  home_founder_name: null,
  home_founder_role: null,
  home_founder_message: null,
  home_brand_logos: null,
  home_brand_strip_title: null,
  home_leadership_section_enabled: true,
  home_leadership_section_eyebrow: null,
  home_leadership_section_title: null,
  home_leadership_section_subtitle: null,
  home_leadership_animation_enabled: true,
  theme_primary_hex: null,
  theme_accent_hex: null,
  theme_heading_font: null,
  theme_body_font: null,
};

export async function getSiteSettings(): Promise<SiteSettings> {
  return (
    (await fetchPublic<SiteSettings>("/public/site-settings")) ??
    FALLBACK_SETTINGS
  );
}

// Navigation menu (Phase 5 follow-up) -----------------------------------

import type { NavItem } from "@/lib/site-config";
import { NAV_ITEMS } from "@/lib/site-config";
import type { NavigationItemNode } from "@/lib/admin/types";

/** Convert the backend tree into the NavItem shape the navbar /
 *  mobile menu already render. Inactive items are pre-filtered server
 *  side; any node without children leaves `children` undefined to
 *  avoid rendering an empty dropdown caret. */
function toNavItems(rows: NavigationItemNode[]): NavItem[] {
  return rows.map((row) => {
    const children = (row.children ?? [])
      .filter((c) => c.is_active)
      .map((c) => ({
        label: c.label,
        href: c.href,
        description: c.description ?? undefined,
      }));
    const item: NavItem = {
      label: row.label,
      href: row.href,
    };
    if (children.length > 0) item.children = children;
    if (row.mega_kind === "companies") item.mega = "companies";
    return item;
  });
}

/** Public site navigation. Falls back to the compiled-in defaults when
 *  the admin hasn't populated any rows yet (or the backend is down) so
 *  the navbar always has something to render. */
export async function getPublicNavigation(): Promise<NavItem[]> {
  const rows = await fetchPublic<NavigationItemNode[]>("/public/navigation");
  if (!rows || rows.length === 0) return NAV_ITEMS;
  return toNavItems(rows);
}

// Job openings ------------------------------------------------------------

export type JobStatus = "open" | "on_hold" | "closed";
export type EmploymentType = "full_time" | "part_time" | "contract";

export interface PublicJob {
  id: number;
  slug: string;
  title: string;
  department: string;
  division: string | null;
  company: string;
  location: string;
  employment_type: EmploymentType;
  min_experience: number;
  max_experience: number;
  required_education: string | null;
  salary_min: number | null;
  salary_max: number | null;
  visa_requirement: string | null;
  nationality_preference: string | null;
  language_requirement: string | null;
  notice_period_preference: string | null;
  description: string | null;
  responsibilities: string | null;
  requirements: string | null;
  required_skills: string | null;
  preferred_skills: string | null;
  status: JobStatus;
  posted_at: string;
  closed_at: string | null;
  created_by_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface PublicJobsQuery {
  department?: string;
  company?: string;
  location?: string;
  employment_type?: EmploymentType;
  q?: string;
}

export async function getPublicJobs(
  query?: PublicJobsQuery
): Promise<PublicJob[]> {
  const params = new URLSearchParams();
  if (query?.department) params.set("department", query.department);
  if (query?.company) params.set("company", query.company);
  if (query?.location) params.set("location", query.location);
  if (query?.employment_type)
    params.set("employment_type", query.employment_type);
  if (query?.q) params.set("q", query.q);
  const search = params.toString() ? `?${params}` : "";
  return (await fetchPublic<PublicJob[]>(`/public/jobs${search}`)) ?? [];
}

export async function getPublicJobBySlug(slug: string): Promise<PublicJob | null> {
  return fetchPublic<PublicJob>(`/public/jobs/${encodeURIComponent(slug)}`);
}

export const EMPLOYMENT_TYPE_LABELS: Record<EmploymentType, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
};

/**
 * Split a comma-separated skills string into a clean trimmed list.
 * Empty entries are dropped. Returns [] for null/undefined input.
 */
export function splitSkills(value: string | null | undefined): string[] {
  if (!value) return [];
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Split a newline-separated text block into a clean trimmed list.
 * Used for `responsibilities` and `requirements` rendering.
 */
export function splitLines(value: string | null | undefined): string[] {
  if (!value) return [];
  return value
    .split(/\r?\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

// Featured-companies homepage section -----------------------------------

export interface FeaturedSectionPayload {
  enabled: boolean;
  eyebrow: string | null;
  title: string | null;
  subtitle: string | null;
  cta_label: string | null;
  cta_url: string | null;
  animation_enabled: boolean;
}

export interface FeaturedCompaniesSection {
  section: FeaturedSectionPayload;
  companies: Company[];
}

export async function getFeaturedCompaniesSection(): Promise<FeaturedCompaniesSection> {
  const fallback: FeaturedCompaniesSection = {
    section: {
      enabled: true,
      eyebrow: "Group companies",
      title: "A diversified portfolio, one trusted group.",
      subtitle:
        "Scroll to explore the businesses powering Paris United Group across retail, distribution, and services.",
      cta_label: "View all companies",
      cta_url: "/companies",
      animation_enabled: true,
    },
    companies: [],
  };
  return (
    (await fetchPublic<FeaturedCompaniesSection>(
      "/public/featured-companies-section"
    )) ?? fallback
  );
}

/**
 * Resolve an asset URL coming from the backend.
 *
 * Uploads under `/api/v1/uploads/...` are served by the FastAPI host,
 * not by Next.js — so we prefix with `env.apiBaseUrl`'s origin.
 * External URLs (http://, https://) and Next.js public assets
 * (anything else starting with `/`) pass through unchanged.
 *
 * LAN-access edge case: when `NEXT_PUBLIC_API_BASE_URL` was built
 * with a loopback host (localhost / 127.0.0.1) but the page itself
 * was loaded from a non-loopback host (e.g. another device on the
 * LAN hitting http://192.168.x.y:3000), the browser would otherwise
 * try to fetch the image from ITS OWN loopback and fail. In that
 * scenario we swap the API host for the current page's hostname,
 * preserving the backend's port — so the image is fetched from the
 * dev machine over the LAN instead.
 */
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "0.0.0.0"]);

export function resolveAssetUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith("/api/")) {
    try {
      const base = new URL(env.apiBaseUrl);
      if (
        typeof window !== "undefined" &&
        LOOPBACK_HOSTS.has(base.hostname) &&
        !LOOPBACK_HOSTS.has(window.location.hostname)
      ) {
        const port = base.port ? `:${base.port}` : "";
        return `${window.location.protocol}//${window.location.hostname}${port}${url}`;
      }
      return `${base.origin}${url}`;
    } catch {
      return url;
    }
  }
  return url;
}

// Convenience helpers used by detail pages for `generateStaticParams`.

export async function getAllCompanySlugs(): Promise<string[]> {
  const companies = await getCompanies();
  return companies.map((c) => c.slug);
}

export async function getAllNewsSlugs(): Promise<string[]> {
  const news = await getNews();
  return news.map((n) => n.slug);
}

// Re-export the types so consumer pages only import from one module.
export type {
  Company,
  ContactMessage,
  HeroSlide,
  LeadershipMessage,
  NewsItem,
  NewsletterSubscriber,
  SiteSettings,
};
