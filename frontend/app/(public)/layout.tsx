import { AskPugAiButton } from "@/components/site/ask-pug-ai-button";
import { Footer } from "@/components/site/footer";
import { Navbar } from "@/components/site/navbar";
import { SkipToContent } from "@/components/site/skip-to-content";

/**
 * Public site layout (Phase 3 foundation).
 *
 * Wraps every public route ((/), /about, /companies, /news, /careers,
 * /contact, /media) in:
 *   - Skip-to-content link (a11y)
 *   - Sticky transparent navbar with desktop dropdown + mobile drawer
 *   - Footer with contact details + social links
 *   - Floating "Ask PUG AI" launcher (modal placeholder until Phase 17)
 */
export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen flex-col">
      <SkipToContent />
      <Navbar />
      <main id="main-content" className="flex-1">
        {children}
      </main>
      <Footer />
      <AskPugAiButton />
    </div>
  );
}
