import { AskPugAiButton } from "@/components/site/ask-pug-ai-button";
import { Footer } from "@/components/site/footer";
import { Navbar } from "@/components/site/navbar";
import { SkipToContent } from "@/components/site/skip-to-content";
import {
  getCompanies,
  getPublicNavigation,
  getSiteSettings,
} from "@/lib/public-api";

export const revalidate = 60;

/**
 * Public site layout.
 *
 * Wraps every public route in the navbar / footer / floating AI button.
 * Site settings populate the footer; the companies list feeds the
 * mega menu shown under "Group Companies"; the navigation tree drives
 * the navbar + mobile drawer.
 */
export default async function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [settings, companies, navItems] = await Promise.all([
    getSiteSettings(),
    getCompanies(),
    getPublicNavigation(),
  ]);

  return (
    <div className="relative flex min-h-screen flex-col">
      <SkipToContent />
      <Navbar companies={companies} items={navItems} />
      <main id="main-content" className="flex-1">
        {children}
      </main>
      <Footer settings={settings} />
      <AskPugAiButton />
    </div>
  );
}
