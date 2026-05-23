import { AskPugAiButton } from "@/components/site/ask-pug-ai-button";
import { Footer } from "@/components/site/footer";
import { Navbar } from "@/components/site/navbar";
import { SkipToContent } from "@/components/site/skip-to-content";
import { getSiteSettings } from "@/lib/public-api";

export const revalidate = 60;

/**
 * Public site layout.
 *
 * Wraps every public route in the navbar / footer / floating AI button.
 * Site settings (contact details, social links, tagline) are fetched
 * server-side and passed down to the footer.
 */
export default async function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const settings = await getSiteSettings();

  return (
    <div className="relative flex min-h-screen flex-col">
      <SkipToContent />
      <Navbar />
      <main id="main-content" className="flex-1">
        {children}
      </main>
      <Footer settings={settings} />
      <AskPugAiButton />
    </div>
  );
}
