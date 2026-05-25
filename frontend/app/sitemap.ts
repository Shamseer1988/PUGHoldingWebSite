/**
 * Dynamic sitemap.xml — admin-driven.
 *
 * Phase 1 of the SEO Configuration module makes this honour the
 * include_* + default_changefreq + default_priority toggles set
 * under Admin → Settings → SEO Configuration → Sitemap.
 *
 * The static-route table is kept here (rather than the backend)
 * because Next owns the routing — only the frontend knows which
 * static pages exist. Toggles selected by the admin gate which
 * dynamic groups join.
 *
 * Behaviour:
 *   - `enable_sitemap = false` → return an empty array (Next emits a
 *     well-formed but content-free sitemap.xml so the URL still
 *     resolves and crawlers see "no entries").
 *   - `sitemap_default_changefreq` / `_default_priority` override
 *     the per-entry defaults below when the admin has set them.
 *   - `sitemap_include_companies` / `_cms_pages` / `_news` skip the
 *     corresponding loops when off.
 *
 * If the backend is unreachable we fall back to "enable everything"
 * — a flaky API shouldn't accidentally strip the sitemap.
 */
import type { MetadataRoute } from "next";

import { env } from "@/lib/env";
import {
  getCompanies,
  getNews,
  getPages,
  getPublicJobs,
} from "@/lib/public-api";
import { getPublicSeoHead } from "@/lib/seo-api";


const STATIC_ROUTES: Array<{ path: string; priority: number; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"] }> = [
  { path: "/", priority: 1.0, changeFrequency: "weekly" },
  { path: "/about", priority: 0.8, changeFrequency: "monthly" },
  { path: "/companies", priority: 0.8, changeFrequency: "weekly" },
  { path: "/careers", priority: 0.9, changeFrequency: "daily" },
  { path: "/news", priority: 0.8, changeFrequency: "weekly" },
  { path: "/media", priority: 0.5, changeFrequency: "monthly" },
  { path: "/contact", priority: 0.6, changeFrequency: "yearly" },
];


function urlFor(path: string): string {
  const base = env.siteUrl.replace(/\/$/, "");
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}


export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const flags = await getPublicSeoHead().catch(() => null);

  if (flags && !flags.enable_sitemap) {
    return [];
  }

  // Defaults — admin overrides win when present.
  const overrideFreq = (flags?.sitemap_default_changefreq ?? null) as
    | MetadataRoute.Sitemap[number]["changeFrequency"]
    | null;
  const overridePriority = flags?.sitemap_default_priority ?? null;
  const includeStatic = flags?.sitemap_include_static ?? true;
  const includeCompanies = flags?.sitemap_include_companies ?? true;
  const includeNews = flags?.sitemap_include_news ?? true;
  const includeCmsPages = flags?.sitemap_include_cms_pages ?? true;

  const [companies, news, jobs, pages] = await Promise.all([
    includeCompanies ? getCompanies().catch(() => []) : [],
    includeNews ? getNews().catch(() => []) : [],
    getPublicJobs().catch(() => []),
    includeCmsPages ? getPages().catch(() => []) : [],
  ]);

  const entries: MetadataRoute.Sitemap = [];

  if (includeStatic) {
    for (const route of STATIC_ROUTES) {
      entries.push({
        url: urlFor(route.path),
        lastModified: now,
        changeFrequency: overrideFreq ?? route.changeFrequency,
        priority: overridePriority ?? route.priority,
      });
    }
  }

  for (const company of companies) {
    entries.push({
      url: urlFor(`/companies/${company.slug}`),
      lastModified: company.updated_at ? new Date(company.updated_at) : now,
      changeFrequency: overrideFreq ?? "monthly",
      priority: overridePriority ?? 0.7,
    });
  }

  for (const item of news) {
    entries.push({
      url: urlFor(`/news/${item.slug}`),
      lastModified: item.updated_at ? new Date(item.updated_at) : now,
      changeFrequency: overrideFreq ?? "weekly",
      priority: overridePriority ?? 0.6,
    });
  }

  for (const job of jobs) {
    entries.push({
      url: urlFor(`/careers/${job.slug}`),
      lastModified: job.updated_at ? new Date(job.updated_at) : now,
      changeFrequency: overrideFreq ?? "daily",
      priority: overridePriority ?? 0.7,
    });
  }

  for (const page of pages) {
    entries.push({
      url: urlFor(`/pages/${page.slug}`),
      lastModified: page.updated_at ? new Date(page.updated_at) : now,
      changeFrequency: overrideFreq ?? "monthly",
      priority: overridePriority ?? 0.5,
    });
  }

  return entries;
}
