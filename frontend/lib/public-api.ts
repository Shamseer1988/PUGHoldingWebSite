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

const FALLBACK_SETTINGS: SiteSettings = {
  id: 1,
  site_name: "Paris United Group Holding",
  tagline: null,
  contact_phone: null,
  contact_email: null,
  contact_address: null,
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
};

export async function getSiteSettings(): Promise<SiteSettings> {
  return (
    (await fetchPublic<SiteSettings>("/public/site-settings")) ??
    FALLBACK_SETTINGS
  );
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
 */
export function resolveAssetUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith("/api/")) {
    try {
      const base = new URL(env.apiBaseUrl);
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
