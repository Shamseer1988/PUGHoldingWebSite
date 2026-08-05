/**
 * Branch storefront — the page a shopper lands on from an in-store QR.
 *
 * Design intent: this is the last link in the QR fallback chain, so it
 * has to feel like *that branch's* page, not a generic group page with
 * a filter applied. Hence the branch name in the header, its own
 * contact block in the footer, and content ordered so the freshest
 * flyer is the first thing on screen.
 *
 * Mobile-first throughout — essentially every visitor arrives by
 * phone camera, so the layout is designed at 375px and allowed to grow,
 * not the reverse.
 */

import Link from "next/link";
import {
  BookOpen,
  ChevronRight,
  Clock,
  Facebook,
  Instagram,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
  Youtube,
} from "lucide-react";

import type {
  BranchPage,
  OfferIndexCampaign,
  OffersIndexCatalogue,
} from "@/lib/public-offers";
import { resolveAssetUrl } from "@/lib/public-api";
import { env } from "@/lib/env";
import { cn } from "@/lib/utils";

import { CampaignCard, CatalogueCard, SectionHeading } from "./offer-cards";

/** Socials we have a Lucide glyph for; the rest fall back to a chip. */
const SOCIALS = [
  { key: "instagram", label: "Instagram", Icon: Instagram },
  { key: "facebook", label: "Facebook", Icon: Facebook },
  { key: "youtube", label: "YouTube", Icon: Youtube },
  { key: "tiktok", label: "TikTok", Icon: null },
  { key: "snapchat", label: "Snapchat", Icon: null },
  { key: "x", label: "X", Icon: null },
] as const;

export function BranchStorefront({ branch }: { branch: BranchPage }) {
  const hero = resolveAssetUrl(branch.hero_image_url);
  const logo = resolveAssetUrl(branch.logo_url);

  const live = branch.campaigns.filter((c) => !c.is_expired);
  const past = branch.campaigns.filter((c) => c.is_expired);
  const socials = SOCIALS.map((s) => ({
    ...s,
    href: branch.social[s.key],
  })).filter((s): s is typeof s & { href: string } => Boolean(s.href));

  // Served by the offers API so the artwork is branded and cached at
  // the CDN rather than generated per-render in the browser. Built from
  // the PUBLIC api base because the browser loads this <img> directly —
  // an internal origin would be unreachable from the phone.
  const locationQrUrl = `${env.apiBaseUrl}/offers/branch/${branch.slug}/location-qr.png`;

  return (
    <div className="min-h-screen bg-[#f7f5f0] dark:bg-[#0f1512]">
      {/* ---------------------------------------------------------------
          Header — branch identity.
          Compact on mobile by design: someone who just scanned a code
          in the store needs to confirm they're in the right place and
          then see the flyer. The banner is the draw, so the overlay is
          a bottom-up gradient only — the top of the artwork stays
          readable instead of being flattened by a full-bleed scrim.
      --------------------------------------------------------------- */}
      <header className="relative overflow-hidden bg-[#17382f] text-white">
        {hero && (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element -- CMS
                URL that may live on R2; next/image would need every
                possible remote host allow-listed. */}
            <img
              src={hero}
              alt=""
              className="absolute inset-0 h-full w-full object-cover opacity-70 sm:opacity-45"
            />
            <div
              className="absolute inset-0 bg-gradient-to-t from-[#17382f] via-[#17382f]/75 to-[#17382f]/20"
              aria-hidden
            />
          </>
        )}

        <div className="relative mx-auto max-w-6xl px-4 pb-5 pt-3 sm:px-6 sm:pb-10 sm:pt-6">
          <nav className="mb-3 flex items-center gap-1.5 text-[11px] text-white/60 sm:mb-6 sm:text-xs">
            <Link href="/offers" className="transition-colors hover:text-white">
              Offers
            </Link>
            <ChevronRight className="h-3 w-3" aria-hidden />
            <span className="text-white/90">{branch.name}</span>
          </nav>

          <div className="flex items-center gap-3 sm:gap-4">
            {logo && (
              // eslint-disable-next-line @next/next/no-img-element -- see above
              <img
                src={logo}
                alt=""
                className="h-11 w-11 shrink-0 rounded-xl bg-white/95 object-contain p-1.5 shadow-lg sm:h-20 sm:w-20 sm:rounded-2xl sm:p-2"
              />
            )}
            <div className="min-w-0">
              <h1 className="text-xl font-semibold uppercase leading-tight tracking-wide sm:text-4xl">
                {branch.name}
              </h1>
              {branch.city && (
                <p className="mt-0.5 inline-flex items-center gap-1 text-xs text-[#d8c9a3] sm:mt-1.5 sm:gap-1.5 sm:text-sm">
                  <MapPin className="h-3 w-3 sm:h-3.5 sm:w-3.5" aria-hidden />
                  {branch.city}
                </p>
              )}
            </div>
          </div>

          {branch.description && (
            <p className="mt-3 line-clamp-2 max-w-2xl text-xs leading-relaxed text-white/75 sm:mt-5 sm:line-clamp-none sm:text-base">
              {branch.description}
            </p>
          )}

          {branch.other_branches.length > 0 && (
            <div className="mt-4 sm:mt-7">
              <div className="flex flex-wrap gap-1.5 sm:gap-2">
                {branch.other_branches.map((b) => (
                  <Link
                    key={b.slug}
                    href={`/offers/${b.slug}`}
                    className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1 text-[11px] text-white/85 backdrop-blur-sm transition-colors hover:border-[#b89c5c] hover:text-white sm:px-3 sm:py-1.5 sm:text-xs"
                  >
                    {b.name}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-7 sm:px-6 sm:py-14">
        {branch.catalogues.length === 0 && live.length === 0 && (
          <div className="rounded-3xl border border-dashed border-black/10 bg-white/60 px-6 py-16 text-center dark:border-white/10 dark:bg-white/[0.03]">
            <BookOpen className="mx-auto h-8 w-8 text-[#17382f]/30 dark:text-white/25" />
            <h2 className="mt-4 text-lg font-semibold text-[#17382f] dark:text-white">
              No offers running right now
            </h2>
            <p className="mx-auto mt-2 max-w-sm text-sm text-black/55 dark:text-white/55">
              New flyers for {branch.name} land here as soon as they&apos;re
              published. Check back soon.
            </p>
            <Link
              href="/offers"
              className="mt-6 inline-flex items-center gap-1.5 rounded-full bg-[#17382f] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#1f4a3d]"
            >
              Browse all offers
              <ChevronRight className="h-4 w-4" aria-hidden />
            </Link>
          </div>
        )}

        {branch.catalogues.length > 0 && (
          <section className="mb-14">
            <SectionHeading
              title="Latest catalogues"
              subtitle={`Flyers available at ${branch.name}`}
            />
            <div className="grid grid-cols-2 gap-4 sm:gap-5 lg:grid-cols-4">
              {branch.catalogues.map((c: OffersIndexCatalogue) => (
                <CatalogueCard key={c.slug} catalogue={c} />
              ))}
            </div>
          </section>
        )}

        {live.length > 0 && (
          <section className="mb-14">
            <SectionHeading
              title="Campaigns"
              subtitle="Running now at this branch"
            />
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {live.map((c: OfferIndexCampaign) => (
                <CampaignCard key={c.slug} campaign={c} />
              ))}
            </div>
          </section>
        )}

        {past.length > 0 && (
          <section>
            <SectionHeading title="Past campaigns" subtitle="Recently ended" />
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {past.map((c: OfferIndexCampaign) => (
                <CampaignCard key={c.slug} campaign={c} />
              ))}
            </div>
          </section>
        )}
      </main>

      {/* ---------------------------------------------------------------
          Footer — this branch's own contact block, not the group's.
          One column on mobile, flattened to a single list: the previous
          three-heading grid pushed the useful details below the fold on
          a phone, which is where nearly every visitor is.
      --------------------------------------------------------------- */}
      <footer className="bg-[#17382f] text-white">
        <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-[#d8c9a3]">
                {branch.name}
              </h2>

              <ul className="mt-3 space-y-2 text-sm text-white/75">
                {branch.address && (
                  <li className="flex items-start gap-2">
                    <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-[#b89c5c]" aria-hidden />
                    <span>{branch.address}</span>
                  </li>
                )}
                {branch.phone && (
                  <li>
                    <a
                      href={`tel:${branch.phone.replace(/\s+/g, "")}`}
                      className="inline-flex items-center gap-2 transition-colors hover:text-white"
                    >
                      <Phone className="h-4 w-4 text-[#b89c5c]" aria-hidden />
                      {branch.phone}
                    </a>
                  </li>
                )}
                {branch.whatsapp && (
                  <li>
                    <a
                      // wa.me needs a bare international number.
                      href={`https://wa.me/${branch.whatsapp.replace(/[^\d]/g, "")}`}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-2 transition-colors hover:text-white"
                    >
                      <MessageCircle className="h-4 w-4 text-[#b89c5c]" aria-hidden />
                      WhatsApp
                    </a>
                  </li>
                )}
                {branch.email && (
                  <li>
                    <a
                      href={`mailto:${branch.email}`}
                      className="inline-flex items-center gap-2 break-all transition-colors hover:text-white"
                    >
                      <Mail className="h-4 w-4 shrink-0 text-[#b89c5c]" aria-hidden />
                      {branch.email}
                    </a>
                  </li>
                )}
                {branch.opening_hours && (
                  <li className="flex items-start gap-2">
                    <Clock className="mt-0.5 h-4 w-4 shrink-0 text-[#b89c5c]" aria-hidden />
                    <span className="whitespace-pre-line">
                      {branch.opening_hours}
                    </span>
                  </li>
                )}
              </ul>

              {socials.length > 0 && (
                <div className="mt-5 flex flex-wrap gap-2">
                  {socials.map(({ key, label, Icon, href }) => (
                    <a
                      key={key}
                      href={href}
                      target="_blank"
                      rel="noreferrer noopener"
                      aria-label={label}
                      title={label}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-2 text-xs text-white/75 transition-colors",
                        "hover:border-[#b89c5c] hover:bg-[#b89c5c]/15 hover:text-white",
                      )}
                    >
                      {Icon ? <Icon className="h-4 w-4" aria-hidden /> : null}
                      {/* Brands without a Lucide glyph still get a
                          readable label rather than an empty circle. */}
                      {!Icon && label}
                    </a>
                  ))}
                </div>
              )}
            </div>

            {/* Location block: tap-through button plus a scannable code.
                The QR makes the page work as a shareable artifact — a
                screenshot or a printed poster still opens directions,
                which a plain link can't do. */}
            {branch.maps_url && (
              <div className="flex items-center gap-4 sm:flex-col sm:items-end sm:gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element --
                    server-rendered PNG from the offers API; next/image
                    would proxy a already-optimised 512px asset. */}
                <img
                  src={locationQrUrl}
                  alt={`QR code with directions to ${branch.name}`}
                  loading="lazy"
                  width={104}
                  height={104}
                  className="h-26 w-26 shrink-0 rounded-xl bg-white p-1.5 shadow-lg"
                  style={{ height: "6.5rem", width: "6.5rem" }}
                />
                <div className="sm:text-right">
                  <a
                    href={branch.maps_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1.5 rounded-full border border-[#b89c5c]/50 px-3.5 py-2 text-xs font-medium text-[#d8c9a3] transition-colors hover:bg-[#b89c5c]/15"
                  >
                    <MapPin className="h-3.5 w-3.5" aria-hidden />
                    Get directions
                  </a>
                  <p className="mt-1.5 text-[11px] text-white/40">
                    Scan for directions
                  </p>
                </div>
              </div>
            )}
          </div>

          <p className="mt-8 border-t border-white/10 pt-5 text-[11px] text-white/40">
            © {new Date().getFullYear()} Paris United Group
          </p>
        </div>
      </footer>
    </div>
  );
}
