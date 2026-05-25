import "@/styles/globals.css";

import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { SeoBodyStart } from "@/components/site/seo-body-start";
import { SeoHead } from "@/components/site/seo-head";
import { ThemeProvider } from "@/components/theme-provider";
import { env } from "@/lib/env";
import { getSiteSettings } from "@/lib/public-api";
import { getPublicSeoHead, type PublicSeoHeadFeed } from "@/lib/seo-api";
import { buildThemeStyle } from "@/lib/theme";
import { cn } from "@/lib/utils";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});


/**
 * Build the root `<head>` metadata.
 *
 * Title, description, and Open Graph defaults come from the SEO
 * Configuration module (admin-controlled). Anything the admin hasn't
 * filled in falls back to the existing hard-coded copy so a freshly
 * deployed site still renders sensible defaults.
 *
 * Admin-pasted verification meta tags (Google Search Console, Bing,
 * Meta, Pinterest, etc.) ship via Next's `other` field — App Router
 * only honours real meta tags returned from `generateMetadata()`, so
 * we can't render them via a child component.
 */
export async function generateMetadata(): Promise<Metadata> {
  const feed = await getPublicSeoHead().catch(() => null);

  // Build the `other` map for verification + alternate-name meta tags.
  // Multiple tags with the same `name` are unusual in practice (one
  // per provider) so a flat record is sufficient for Phase 1.
  const otherTags: Record<string, string> = {};
  for (const meta of feed?.verification_metas ?? []) {
    const key = (meta.name ?? meta.property ?? "").trim();
    if (!key || !meta.content) continue;
    otherTags[key] = meta.content;
  }

  const siteName = feed?.site_name?.trim() || env.siteName;
  const defaultTitle =
    feed?.default_meta_title?.trim() || `${siteName} | Diversified Holding Group`;
  const description =
    feed?.default_meta_description?.trim() ||
    "Paris United Group Holding - a diversified business group across retail, wholesale distribution, FMCG, fashion, packaging, fresh food, building materials, garages, real estate, and construction.";

  return {
    metadataBase: new URL(env.siteUrl),
    title: {
      default: defaultTitle,
      template: `%s | ${siteName}`,
    },
    description,
    applicationName: siteName,
    authors: [{ name: siteName }],
    keywords: [
      "Paris United Group",
      "Holding Group",
      "Qatar",
      "Retail",
      "Distribution",
      "FMCG",
      "Construction",
    ],
    openGraph: {
      type: "website",
      siteName,
      images: feed?.default_og_image ? [feed.default_og_image] : ["/logo.png"],
    },
    twitter: feed?.enable_twitter_cards
      ? {
          card: "summary_large_image",
          images: feed?.default_twitter_image
            ? [feed.default_twitter_image]
            : undefined,
        }
      : undefined,
    other: Object.keys(otherTags).length ? otherTags : undefined,
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "hsl(40 30% 98%)" },
    { media: "(prefers-color-scheme: dark)", color: "hsl(145 28% 7%)" },
  ],
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Pull theme overrides server-side so the CSS variables ship in the
  // initial HTML — no flash of un-themed content on hard reload.
  const [settings, seoFeed] = await Promise.all([
    getSiteSettings().catch(() => null),
    getPublicSeoHead().catch(() => null),
  ]);
  const themeStyle = settings ? buildThemeStyle(settings) : undefined;
  const feed: PublicSeoHeadFeed = seoFeed ?? {
    site_name: null,
    default_meta_title: null,
    default_meta_description: null,
    canonical_base_url: null,
    default_language: null,
    enable_canonical: true,
    enable_open_graph: true,
    enable_twitter_cards: true,
    default_og_image: null,
    default_twitter_image: null,
    enable_sitemap: true,
    sitemap_include_static: true,
    sitemap_include_companies: true,
    sitemap_include_cms_pages: true,
    sitemap_include_news: true,
    sitemap_default_changefreq: null,
    sitemap_default_priority: null,
    verification_metas: [],
    integrations: [],
  };

  return (
    <html lang={feed.default_language ?? "en"} suppressHydrationWarning style={themeStyle}>
      <body className={cn("font-sans antialiased", inter.variable)}>
        {/* GTM noscript + Meta Pixel noscript — must be the FIRST body child. */}
        <SeoBodyStart feed={feed} />
        {/* GTM head loader + GA4 / Pixel / Clarity / LinkedIn / TikTok / X.
            Next's <Script> ports these into <head>. */}
        <SeoHead feed={feed} />
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
