import { AskPugAiButton } from "@/components/site/ask-pug-ai-button";
import { Footer } from "@/components/site/footer";
import { MaintenancePage } from "@/components/site/maintenance-page";
import { Navbar } from "@/components/site/navbar";
import { ScrollProgressBar } from "@/components/site/scroll-progress";
import { SkipToContent } from "@/components/site/skip-to-content";
import { getLocale } from "@/lib/i18n/get-locale";
import { getMessages } from "@/lib/i18n/get-messages";
import { LocaleProvider } from "@/lib/i18n/locale-provider";
import {
  getCompanies,
  getPublicNavigation,
  getSiteSettings,
} from "@/lib/public-api";

export const dynamic = "force-dynamic";

/**
 * Public site layout.
 *
 * Wraps every public route in the navbar / footer / floating AI button.
 * Site settings populate the footer; the companies list feeds the
 * mega menu shown under "Group Companies"; the navigation tree drives
 * the navbar + mobile drawer.
 *
 * When ``site_settings.maintenance_mode_enabled`` is on, every public
 * route renders the maintenance page instead — admin (`/admin/*`) and
 * HR (`/hr/*`) portals are unaffected because they live in their own
 * route groups outside this layout.
 */
export default async function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const settings = await getSiteSettings();

  if (settings.maintenance_mode_enabled) {
    return <MaintenancePage settings={settings} />;
  }

  const [companies, navItems] = await Promise.all([
    getCompanies(),
    getPublicNavigation(),
  ]);

  // Phase C-1: read the locale stamped by ``middleware.ts`` and seed
  // the LocaleProvider with its dictionary. Components inside read
  // strings via ``useT()``; ``<html dir>`` is set in the root layout.
  const locale = getLocale();
  const messages = getMessages(locale);

  return (
    <LocaleProvider locale={locale} messages={messages}>
      <div className="relative flex min-h-screen flex-col">
        <SkipToContent />
        <ScrollProgressBar />
        <Navbar companies={companies} items={navItems} />
        <main id="main-content" className="flex-1">
          {children}
        </main>
        <Footer settings={settings} />
        <AskPugAiButton />
      </div>
    </LocaleProvider>
  );
}
