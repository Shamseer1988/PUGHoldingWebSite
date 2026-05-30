import Link from "next/link";
import { ArrowLeft, Tag } from "lucide-react";


/**
 * Layout for the public Offers / Catalogue surface.
 *
 * Intentionally lives OUTSIDE the ``(public)`` route group so it
 * doesn't inherit the site navbar / footer / floating AI button —
 * the viewer needs a full-bleed, immersive feel so the catalogue
 * pages occupy the whole viewport.
 *
 * Keeps a minimal top bar so the customer can find their way back to
 * the rest of the site, and a slim brand-matched footer below.
 * Both apply to ``/offers``, ``/offers/[slug]`` (campaign detail) and
 * ``/offers/catalogues/[slug]`` (page-flip viewer) automatically.
 */
export default function OffersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const year = new Date().getFullYear();
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="sticky top-0 z-30 border-b border-border/60 bg-background/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm font-semibold text-foreground/80 transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to site</span>
          </Link>
          <Link
            href="/offers"
            className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground hover:text-foreground"
          >
            <Tag className="h-3 w-3" />
            <span>Offers &amp; Catalogues</span>
          </Link>
        </div>
      </header>

      <div className="flex-1">{children}</div>

      {/* Slim brand-matched footer. Deliberately lighter than the
          site-wide one — the offers surface stays focused on the
          catalogues; a verbose footer would compete for attention. */}
      <footer className="border-t border-border/60 bg-pug-green-900 text-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="space-y-0.5">
            <p className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-pug-gold-300">
              <Tag className="h-3 w-3" />
              Paris United Group · Offers
            </p>
            <p className="text-xs text-white/70">
              &copy; {year} Paris United Group Holding. All rights reserved.
            </p>
          </div>
          <nav className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-white/80">
            <Link
              href="/"
              className="transition-colors hover:text-pug-gold-300"
            >
              Main site
            </Link>
            <Link
              href="/about"
              className="transition-colors hover:text-pug-gold-300"
            >
              About PUG
            </Link>
            <Link
              href="/contact"
              className="transition-colors hover:text-pug-gold-300"
            >
              Contact
            </Link>
            <Link
              href="/privacy-policy"
              className="transition-colors hover:text-pug-gold-300"
            >
              Privacy
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
