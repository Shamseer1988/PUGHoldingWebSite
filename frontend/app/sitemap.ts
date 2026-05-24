/**
 * Dynamic sitemap.xml — auto-generated from the live CMS payloads.
 *
 * Next.js takes a `MetadataRoute.Sitemap` array and turns it into a
 * valid `sitemap.xml` at `/sitemap.xml`. We:
 *   1. List every static public route (Home, About, Careers, etc.).
 *   2. Append a row per active company, published news article, open
 *      job, and published CMS page using the existing public API
 *      helpers.
 *
 * No admin UI is required — admins control what shows up by flipping
 * the same is_active / is_published / status fields they already use
 * for the public site itself. If the backend is unreachable at build
 * time we fall through to a minimal static set so the route never
 * blows up.
 */
import type { MetadataRoute } from "next";

import { env } from "@/lib/env";
import {
  getCompanies,
  getNews,
  getPages,
  getPublicJobs,
} from "@/lib/public-api";


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

  // Pull every dynamic list in parallel. Each helper already swallows
  // errors and returns `[]` on failure, so a flaky backend just trims
  // the sitemap instead of failing the build.
  const [companies, news, jobs, pages] = await Promise.all([
    getCompanies().catch(() => []),
    getNews().catch(() => []),
    getPublicJobs().catch(() => []),
    getPages().catch(() => []),
  ]);

  const entries: MetadataRoute.Sitemap = STATIC_ROUTES.map((route) => ({
    url: urlFor(route.path),
    lastModified: now,
    changeFrequency: route.changeFrequency,
    priority: route.priority,
  }));

  for (const company of companies) {
    entries.push({
      url: urlFor(`/companies/${company.slug}`),
      lastModified: company.updated_at
        ? new Date(company.updated_at)
        : now,
      changeFrequency: "monthly",
      priority: 0.7,
    });
  }

  for (const item of news) {
    entries.push({
      url: urlFor(`/news/${item.slug}`),
      lastModified: item.updated_at
        ? new Date(item.updated_at)
        : now,
      changeFrequency: "weekly",
      priority: 0.6,
    });
  }

  for (const job of jobs) {
    entries.push({
      url: urlFor(`/careers/${job.slug}`),
      lastModified: job.updated_at ? new Date(job.updated_at) : now,
      changeFrequency: "daily",
      priority: 0.7,
    });
  }

  for (const page of pages) {
    entries.push({
      url: urlFor(`/pages/${page.slug}`),
      lastModified: page.updated_at ? new Date(page.updated_at) : now,
      changeFrequency: "monthly",
      priority: 0.5,
    });
  }

  return entries;
}
