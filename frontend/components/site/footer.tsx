import Link from "next/link";

import { Logo } from "@/components/site/logo";
import {
  CONTACT_DETAILS,
  FOOTER_COLUMNS,
  SOCIAL_LINKS,
} from "@/lib/site-config";

export function Footer() {
  return (
    <footer className="relative mt-24 border-t border-border/60 bg-background/60">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -top-32 -z-10 h-32 bg-gradient-to-b from-transparent to-background/0"
      />

      <div className="container mx-auto px-4 py-12 lg:py-16">
        <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-5">
          {/* Brand column */}
          <div className="lg:col-span-2">
            <Logo />
            <p className="mt-4 max-w-sm text-sm text-muted-foreground">
              A diversified holding group across retail, distribution, FMCG,
              fashion, packaging, fresh food, building materials, garages,
              real estate, and construction.
            </p>

            <ul className="mt-6 space-y-2 text-sm">
              {CONTACT_DETAILS.map((detail) => {
                const Icon = detail.icon;
                const Content = (
                  <span className="flex items-start gap-2 text-muted-foreground">
                    <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <span>
                      <span className="block font-medium text-foreground">
                        {detail.label}
                      </span>
                      <span className="block break-words">{detail.value}</span>
                    </span>
                  </span>
                );
                return (
                  <li key={detail.label}>
                    {detail.href ? (
                      <Link href={detail.href} className="hover:text-foreground">
                        {Content}
                      </Link>
                    ) : (
                      Content
                    )}
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Link columns */}
          {FOOTER_COLUMNS.map((column) => (
            <div key={column.title}>
              <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-foreground">
                {column.title}
              </h3>
              <ul className="mt-4 space-y-2 text-sm">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-start justify-between gap-4 border-t border-border/60 pt-6 sm:flex-row sm:items-center">
          <p className="text-xs text-muted-foreground">
            © {new Date().getFullYear()} Paris United Group Holding. All rights reserved.
          </p>

          <ul className="flex items-center gap-2">
            {SOCIAL_LINKS.map((social) => {
              const Icon = social.icon;
              return (
                <li key={social.label}>
                  <Link
                    href={social.href}
                    aria-label={social.label}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border/60 bg-background/40 text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                  >
                    <Icon className="h-4 w-4" />
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </footer>
  );
}
