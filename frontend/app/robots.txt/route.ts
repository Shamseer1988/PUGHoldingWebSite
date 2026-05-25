/**
 * Public `/robots.txt` — admin-driven.
 *
 * Phase 1 of the SEO Configuration module moves robots.txt off the
 * old `app/robots.ts` (which only supported the structured
 * MetadataRoute format) and onto a free-form route handler so the
 * admin can paste arbitrary custom content under Admin → Settings →
 * SEO Configuration → Robots.txt.
 *
 * The body is rendered by the backend (`/api/v1/public/seo/robots`)
 * so we don't need to mirror robots logic in two languages. If the
 * backend is unreachable we serve a sensible default that still
 * blocks /admin /api /hr.
 */
import { env } from "@/lib/env";
import { getPublicRobotsTxt } from "@/lib/seo-api";

const FALLBACK_ROBOTS = `User-agent: *
Allow: /
Disallow: /admin
Disallow: /admin/
Disallow: /api
Disallow: /api/
Disallow: /hr
Disallow: /hr/
Disallow: /login
Disallow: /uploads/private/

Sitemap: __BASE__/sitemap.xml
`;

export const revalidate = 60;
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const adminBody = await getPublicRobotsTxt();
  const body =
    adminBody ??
    FALLBACK_ROBOTS.replace("__BASE__", env.siteUrl.replace(/\/$/, ""));
  return new Response(body, {
    status: 200,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "public, max-age=60, s-maxage=300",
    },
  });
}
