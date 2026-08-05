import Link from "next/link";
import { Tag } from "lucide-react";

/**
 * Slim group footer for the offers surface.
 *
 * Rendered by the pages that want it rather than by the layout: the
 * branch storefront supplies its own store-specific footer, and having
 * both produced two stacked footers on mobile.
 */
export function OffersFooter() {
  const year = new Date().getFullYear();
  return (
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
  );
}
