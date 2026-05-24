/**
 * Public robots.txt — paired with the dynamic sitemap.
 *
 * Allows everything under the public surface but excludes the admin /
 * HR portals (which require auth anyway, but blocking them at the
 * robots layer keeps them out of search-engine indexes entirely).
 */
import type { MetadataRoute } from "next";

import { env } from "@/lib/env";


export default function robots(): MetadataRoute.Robots {
  const base = env.siteUrl.replace(/\/$/, "");
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/"],
        disallow: ["/admin", "/admin/*", "/hr", "/hr/*", "/api"],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
    host: base,
  };
}
