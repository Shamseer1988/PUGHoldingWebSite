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
 * Still keeps a minimal top bar so the customer can find their way
 * back to the rest of the site.
 */
export default function OffersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
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
            <span>Offers & Catalogues</span>
          </Link>
        </div>
      </header>
      <div className="flex-1">{children}</div>
    </div>
  );
}
