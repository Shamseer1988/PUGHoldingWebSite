"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowUp,
  ArrowUpRight,
  Compass,
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
import { parseContactMapEmbed } from "@/lib/contact-map";
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
            {/* `Logo` already renders its own <Link href="/"> so we do
                NOT wrap it in another anchor — that would produce
                nested <a> tags and trigger a hydration error. */}
            <Logo />

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

          {/* Find-us card — fills the empty space under the nav columns
              on lg+ and stacks below everything else on smaller widths. */}
          <FindUsCard settings={settings} />
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


/**
 * Footer "Find us" card — fills the empty space below the nav columns.
 *
 * - If `settings.contact_map_embed` is set, embeds the trusted iframe
 *   (same parser used on the Contact page) so the actual map preview
 *   appears here. The address card sits beside it on lg+.
 * - If no embed is configured, falls back to a compact address card
 *   only — still cute, still useful, still links to Maps.
 * - The whole card returns null if there's no address AND no embed,
 *   so empty CMS state doesn't leave a stray block.
 */
function FindUsCard({ settings }: { settings: SiteSettings }) {
  const address = settings.contact_address?.trim() || null;
  const mapEmbed = parseContactMapEmbed(settings.contact_map_embed);

  if (!address && !mapEmbed.safeSrc) {
    return null;
  }

  // Google Maps deep-link from the plain-text address — works even
  // without an iframe embed configured.
  const mapsHref = address
    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`
    : null;

  return (
    <div className="md:col-span-2 lg:col-span-7 lg:col-start-6">
      <div className="relative overflow-hidden rounded-2xl border border-pug-gold-500/20 bg-background/40 p-5 shadow-[0_18px_45px_-25px_rgba(15,53,32,0.35)] backdrop-blur-md dark:bg-pug-green-950/40">
        {/* Ambient brand glow */}
        <span
          aria-hidden
          className="pointer-events-none absolute -right-12 -top-12 h-40 w-40 rounded-full bg-pug-gold-500/15 blur-3xl"
        />
        <span
          aria-hidden
          className="pointer-events-none absolute -bottom-16 -left-10 h-40 w-40 rounded-full bg-pug-green-500/15 blur-3xl"
        />

        <div className="relative grid gap-5 sm:grid-cols-[1fr_auto] sm:items-center lg:grid-cols-[1.05fr_1fr]">
          {/* Left — address + CTA */}
          <div className="space-y-3">
            <p className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-pug-gold-700 dark:text-pug-gold-300">
              <Compass className="h-3.5 w-3.5" />
              Find us
            </p>
            <p className="text-sm font-medium leading-relaxed text-foreground">
              {address ?? "Doha, Qatar"}
            </p>
            {mapsHref && (
              <Link
                href={mapsHref}
                target="_blank"
                rel="noopener noreferrer"
                className="group/maps inline-flex items-center gap-1.5 rounded-full border border-pug-gold-500/30 bg-pug-gold-500/5 px-3 py-1.5 text-xs font-semibold text-pug-gold-700 transition-all hover:-translate-y-0.5 hover:border-pug-gold-500/60 hover:bg-pug-gold-500/10 hover:shadow-[0_8px_22px_-14px_rgba(207,166,70,0.5)] dark:text-pug-gold-200"
              >
                <MapPin className="h-3.5 w-3.5" />
                Open in Maps
                <ArrowUpRight className="h-3 w-3 transition-transform group-hover/maps:translate-x-0.5 group-hover/maps:-translate-y-0.5" />
              </Link>
            )}
          </div>

          {/* Right — embedded map (if configured) or decorative tile */}
          <div className="relative h-40 overflow-hidden rounded-xl border border-pug-gold-500/15 bg-pug-green-950/5 ring-1 ring-inset ring-white/5 sm:h-32 lg:h-40">
            {mapEmbed.safeSrc ? (
              <iframe
                src={mapEmbed.safeSrc}
                title={`Map showing ${settings.site_name}`}
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
                allowFullScreen={false}
                className="h-full w-full border-0 grayscale-[15%] transition-[filter] duration-300 hover:grayscale-0"
              />
            ) : (
              <DecorativeMapTile />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


/**
 * Stand-in for the right-hand map preview when no embed is configured.
 * Pure CSS so it stays lightweight and on-brand: a radial grid
 * suggesting a map, a centered pulsing pin, and a soft brand wash.
 */
function DecorativeMapTile() {
  return (
    <div className="relative h-full w-full bg-gradient-to-br from-pug-green-800/15 via-pug-green-700/10 to-pug-gold-500/15">
      {/* Faux map grid */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-[0.18] [background-image:linear-gradient(rgba(15,53,32,0.5)_1px,transparent_1px),linear-gradient(90deg,rgba(15,53,32,0.5)_1px,transparent_1px)] [background-size:24px_24px] dark:[background-image:linear-gradient(rgba(207,166,70,0.4)_1px,transparent_1px),linear-gradient(90deg,rgba(207,166,70,0.4)_1px,transparent_1px)]"
      />
      {/* Faux "roads" — two intersecting bands */}
      <span
        aria-hidden
        className="absolute left-1/4 top-0 bottom-0 w-px bg-gradient-to-b from-transparent via-pug-gold-500/40 to-transparent"
      />
      <span
        aria-hidden
        className="absolute right-1/3 top-0 bottom-0 w-px bg-gradient-to-b from-transparent via-pug-green-500/40 to-transparent"
      />
      <span
        aria-hidden
        className="absolute left-0 right-0 top-1/2 h-px bg-gradient-to-r from-transparent via-pug-gold-500/40 to-transparent"
      />
      {/* Centered pin with ping */}
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="relative flex h-12 w-12 items-center justify-center">
          <span
            aria-hidden
            className="absolute inline-flex h-full w-full animate-ping rounded-full bg-pug-gold-500/40"
            style={{ animationDuration: "2.4s" }}
          />
          <span className="relative inline-flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-pug-gold-400 to-pug-gold-600 text-pug-green-900 shadow-[0_6px_18px_-6px_rgba(207,166,70,0.7)]">
            <MapPin className="h-5 w-5" />
          </span>
        </span>
      </div>
    </div>
  );
}
