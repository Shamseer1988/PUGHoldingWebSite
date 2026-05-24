import "@/styles/globals.css";

import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { ThemeProvider } from "@/components/theme-provider";
import { env } from "@/lib/env";
import { getSiteSettings } from "@/lib/public-api";
import { buildThemeStyle } from "@/lib/theme";
import { cn } from "@/lib/utils";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(env.siteUrl),
  title: {
    default: `${env.siteName} | Diversified Holding Group`,
    template: `%s | ${env.siteName}`,
  },
  description:
    "Paris United Group Holding - a diversified business group across retail, wholesale distribution, FMCG, fashion, packaging, fresh food, building materials, garages, real estate, and construction.",
  applicationName: env.siteName,
  authors: [{ name: env.siteName }],
  keywords: [
    "Paris United Group",
    "Holding Group",
    "Qatar",
    "Retail",
    "Distribution",
    "FMCG",
    "Construction",
  ],
  // Favicons are auto-wired from `app/icon.png` and `app/apple-icon.png`.
  // Open Graph default image uses the full logo.
  openGraph: {
    type: "website",
    siteName: env.siteName,
    images: ["/logo.png"],
  },
};

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
  const settings = await getSiteSettings().catch(() => null);
  const themeStyle = settings ? buildThemeStyle(settings) : undefined;

  return (
    <html lang="en" suppressHydrationWarning style={themeStyle}>
      <body className={cn("font-sans antialiased", inter.variable)}>
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
