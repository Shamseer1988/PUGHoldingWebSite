import "@/styles/globals.css";

import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { ThemeProvider } from "@/components/theme-provider";
import { env } from "@/lib/env";
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
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1220" },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
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
