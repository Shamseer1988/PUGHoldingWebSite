"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowUp,
  Facebook,
  Instagram,
  Linkedin,
  Mail,
  MapPin,
  Phone,
  Sparkles,
  Youtube,
  type LucideIcon,
} from "lucide-react";

import { Logo } from "@/components/site/logo";
import type { SiteSettings } from "@/lib/admin/types";
import { FOOTER_COLUMNS, FOOTER_LEGAL_LINKS } from "@/lib/site-config";
import { cn } from "@/lib/utils";

interface FooterProps {
  settings: SiteSettings;
}

interface ContactRow {
  label: string;
  value: string;
  href?: string;
  icon: LucideIcon;
}

interface SocialRow {
  label: string;
  href: string;
  icon: LucideIcon;
}

export function Footer({ settings }: FooterProps) {
  const rootRef = React.useRef<HTMLElement | null>(null);
  const brandRef = React.useRef<HTMLDivElement | null>(null);
  const navRef = React.useRef<HTMLDivElement | null>(null);
  const bottomRef = React.useRef<HTMLDivElement | null>(null);

  const contactRows: ContactRow[] = [];
  if (settings.contact_address) {
    contactRows.push({
      label: "Address",
      value: settings.contact_address,
      icon: MapPin,
    });
  }
  if (settings.contact_phone) {
    contactRows.push({
      label: "Phone",
      value: settings.contact_phone,
      href: `tel:${settings.contact_phone.replace(/\s/g, "")}`,
      icon: Phone,
    });
  }
  if (settings.contact_email) {
    contactRows.push({
      label: "Email",
      value: settings.contact_email,
      href: `mailto:${settings.contact_email}`,
      icon: Mail,
    });
  }

  const socialRows: SocialRow[] = [];
  if (settings.social_linkedin) {
    socialRows.push({
      label: "LinkedIn",
      href: settings.social_linkedin,
      icon: Linkedin,
    });
  }
  if (settings.social_instagram) {
    socialRows.push({
      label: "Instagram",
      href: settings.social_instagram,
      icon: Instagram,
    });
  }
  if (settings.social_facebook) {
    socialRows.push({
      label: "Facebook",
      href: settings.social_facebook,
      icon: Facebook,
    });
  }
  if (settings.social_youtube) {
    socialRows.push({
      label: "YouTube",
      href: settings.social_youtube,
      icon: Youtube,
    });
  }

  // GSAP one-shot reveal — mirrors the pattern used by the Leadership
  // Messages + Trusted Brands sections so the whole site has a
  // consistent scroll-in feel. Runs only once when the footer crosses
  // into view; respects prefers-reduced-motion.
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let cancelled = false;
    let cleanup: (() => void) | undefined;

    (async () => {
      const { gsap } = await import("gsap");
      const { ScrollTrigger } = await import("gsap/ScrollTrigger");
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);

      const root = rootRef.current;
      const brand = brandRef.current;
      const nav = navRef.current;
      const bottom = bottomRef.current;
      if (!root) return;

      const ctx = gsap.context(() => {
        if (brand) gsap.set(brand, { y: 28, opacity: 0 });
        const columns = nav?.querySelectorAll<HTMLElement>(
          "[data-footer-column]"
        );
        if (columns?.length) gsap.set(columns, { y: 24, opacity: 0 });
        if (bottom) gsap.set(bottom, { y: 16, opacity: 0 });

        const tl = gsap.timeline({
          scrollTrigger: {
            trigger: root,
            start: "top 90%",
            once: true,
          },
          defaults: { ease: "power3.out" },
        });

        if (brand) tl.to(brand, { y: 0, opacity: 1, duration: 0.7 }, 0);
        if (columns?.length) {
          tl.to(
            columns,
            { y: 0, opacity: 1, duration: 0.6, stagger: 0.08 },
            0.15
          );
        }
        if (bottom) tl.to(bottom, { y: 0, opacity: 1, duration: 0.5 }, 0.45);
      }, root);

      cleanup = () => ctx.revert();
    })();

    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, []);

  const scrollToTop = () => {
    if (typeof window === "undefined") return;
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const year = new Date().getFullYear();

  return (
    <footer
      ref={rootRef}
      className={cn(
        "relative mt-24 overflow-hidden border-t",
        // Theme-aware container surface. Glass over a soft warm tint
        // in light mode; deeper green-black in dark mode.
        "border-pug-gold-500/20 bg-background/70 backdrop-blur-xl",
        "dark:border-pug-gold-500/15 dark:bg-pug-green-950/60"
      )}
    >
      {/* Top animated gold accent line — shimmer travels across the
          width on a slow infinite loop. Pure CSS so it doesn't fight
          the GSAP reveal. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px overflow-hidden"
      >
        <span className="absolute inset-y-0 left-0 w-full bg-gradient-to-r from-transparent via-pug-gold-500/60 to-transparent" />
        <span className="footer-shimmer absolute inset-y-0 -left-1/3 w-1/3 bg-gradient-to-r from-transparent via-pug-gold-300 to-transparent dark:via-pug-gold-200" />
      </div>

      {/* Ambient gold glow in the top-right corner — adds depth in
          both themes without competing with content. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-32 -top-32 -z-10 h-80 w-80 rounded-full bg-pug-gold-500/10 blur-3xl dark:bg-pug-gold-500/15"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -left-32 bottom-0 -z-10 h-72 w-72 rounded-full bg-pug-green-500/10 blur-3xl dark:bg-pug-green-500/15"
      />

      <div className="container relative mx-auto px-4 pb-8 pt-14 lg:pb-10 lg:pt-20">
        <div className="grid gap-12 md:grid-cols-2 lg:grid-cols-12">
          {/* Brand column — logo, tagline, contact, social */}
          <div ref={brandRef} className="lg:col-span-5">
            <Link
              href="/"
              className="inline-flex items-center gap-3 transition-opacity hover:opacity-80"
              aria-label={`${settings.site_name} — home`}
            >
              <Logo />
            </Link>

            <p className="mt-5 max-w-md text-sm leading-relaxed text-muted-foreground">
              {settings.tagline ??
                "A diversified holding group across retail, distribution, FMCG, fashion, packaging, fresh food, building materials, garages, real estate, and construction."}
            </p>

            {contactRows.length > 0 && (
              <ul className="mt-7 space-y-3 text-sm">
                {contactRows.map((detail) => {
                  const Icon = detail.icon;
                  const Content = (
                    <span className="group/contact flex items-start gap-3">
                      <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-pug-gold-500/20 bg-pug-gold-500/5 text-pug-gold-700 transition-all duration-200 group-hover/contact:border-pug-gold-500/50 group-hover/contact:bg-pug-gold-500/10 group-hover/contact:text-pug-gold-600 dark:border-pug-gold-500/20 dark:bg-pug-gold-500/10 dark:text-pug-gold-300 dark:group-hover/contact:border-pug-gold-500/40 dark:group-hover/contact:text-pug-gold-200">
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-foreground/80">
                          {detail.label}
                        </span>
                        <span className="mt-0.5 block break-words text-sm text-muted-foreground transition-colors group-hover/contact:text-foreground">
                          {detail.value}
                        </span>
                      </span>
                    </span>
                  );
                  return (
                    <li key={detail.label}>
                      {detail.href ? (
                        <Link href={detail.href} className="block">
                          {Content}
                        </Link>
                      ) : (
                        Content
                      )}
                    </li>
                  );
                })}
              </ul>
            )}

            {socialRows.length > 0 && (
              <div className="mt-7">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-foreground/70">
                  Follow us
                </p>
                <ul className="mt-3 flex flex-wrap items-center gap-2">
                  {socialRows.map((social) => {
                    const Icon = social.icon;
                    return (
                      <li key={social.label}>
                        <Link
                          href={social.href}
                          aria-label={social.label}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="group/social relative inline-flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl border border-pug-gold-500/20 bg-background/40 text-muted-foreground transition-all duration-300 hover:-translate-y-0.5 hover:border-pug-gold-500/60 hover:text-pug-gold-700 hover:shadow-[0_8px_24px_-12px_rgba(207,166,70,0.4)] dark:bg-pug-green-900/40 dark:hover:text-pug-gold-300"
                        >
                          {/* Animated gold sheen on hover */}
                          <span
                            aria-hidden
                            className="absolute inset-0 -translate-x-full skew-x-[-20deg] bg-gradient-to-r from-transparent via-pug-gold-500/30 to-transparent transition-transform duration-500 group-hover/social:translate-x-full"
                          />
                          <Icon className="relative h-4 w-4" />
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>

          {/* Nav columns */}
          <div
            ref={navRef}
            className="grid grid-cols-2 gap-10 sm:grid-cols-3 lg:col-span-7 lg:grid-cols-3"
          >
            {FOOTER_COLUMNS.map((column) => (
              <div key={column.title} data-footer-column>
                <h3 className="relative inline-flex items-center text-xs font-bold uppercase tracking-[0.22em] text-foreground">
                  {column.title}
                  <span
                    aria-hidden
                    className="ml-3 h-px w-6 bg-gradient-to-r from-pug-gold-500/70 to-transparent"
                  />
                </h3>
                <ul className="mt-5 space-y-3 text-sm">
                  {column.links.map((link) => (
                    <li key={link.href}>
                      <Link
                        href={link.href}
                        className="group/link relative inline-flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-foreground"
                      >
                        <span
                          aria-hidden
                          className="absolute left-0 top-1/2 h-1 w-1 -translate-y-1/2 -translate-x-2 rounded-full bg-pug-gold-500 opacity-0 transition-all duration-300 group-hover/link:-translate-x-3 group-hover/link:opacity-100"
                        />
                        <span className="relative">
                          {link.label}
                          <span
                            aria-hidden
                            className="absolute -bottom-0.5 left-0 h-px w-0 bg-gradient-to-r from-pug-gold-500 to-pug-gold-300 transition-all duration-300 group-hover/link:w-full"
                          />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Back-to-top — its own centered row above the bottom bar
            so it doesn't collide with any floating CTA buttons that
            live fixed in the bottom-right corner of the viewport. */}
        <div ref={bottomRef} className="mt-14">
          <div className="relative">
            <span
              aria-hidden
              className="absolute inset-x-0 top-1/2 -z-10 h-px -translate-y-1/2 bg-gradient-to-r from-transparent via-pug-gold-500/20 to-transparent"
            />
            <div className="flex justify-center">
              <button
                type="button"
                onClick={scrollToTop}
                className="group/top inline-flex items-center gap-2 rounded-full border border-pug-gold-500/30 bg-background/80 px-4 py-1.5 text-xs font-medium text-foreground/80 backdrop-blur-md transition-all duration-200 hover:-translate-y-0.5 hover:border-pug-gold-500/60 hover:text-foreground hover:shadow-[0_6px_18px_-10px_rgba(207,166,70,0.45)] dark:bg-pug-green-950/80"
              >
                <ArrowUp className="h-3.5 w-3.5 transition-transform duration-200 group-hover/top:-translate-y-0.5" />
                <span>Back to top</span>
              </button>
            </div>
          </div>

          {/* Bottom bar: copyright + legal links, all left-aligned.
              We deliberately keep the right side of this row clear
              because the fixed floating CTAs (Ask PUG AI, etc.) live
              over that region. On mobile the legal links wrap to a
              second line below the copyright. */}
          <div className="mt-8 flex flex-col items-start gap-x-5 gap-y-3 border-t border-pug-gold-500/10 pt-6 sm:flex-row sm:flex-wrap sm:items-center">
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Sparkles className="h-3 w-3 text-pug-gold-500" aria-hidden />
              <span>
                © {year} {settings.site_name}. All rights reserved.
              </span>
            </p>

            <span
              aria-hidden
              className="hidden h-3 w-px bg-border sm:block"
            />

            <ul className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
              {FOOTER_LEGAL_LINKS.map((link, i) => (
                <React.Fragment key={link.href}>
                  {i > 0 && (
                    <li
                      aria-hidden
                      className="hidden h-3 w-px bg-border sm:block"
                    />
                  )}
                  <li>
                    <Link
                      href={link.href}
                      className="group/legal relative text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link.label}
                      <span
                        aria-hidden
                        className="absolute -bottom-0.5 left-0 h-px w-0 bg-gradient-to-r from-pug-gold-500 to-pug-gold-300 transition-all duration-300 group-hover/legal:w-full"
                      />
                    </Link>
                  </li>
                </React.Fragment>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </footer>
  );
}
