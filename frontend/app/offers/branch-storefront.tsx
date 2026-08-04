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
  Phone,
  Youtube,
} from "lucide-react";

import type {
  BranchPage,
  OfferIndexCampaign,
  OffersIndexCatalogue,
} from "@/lib/public-offers";
import { resolveAssetUrl } from "@/lib/public-api";
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

  const hasContact = Boolean(
    branch.address ||
      branch.phone ||
      branch.whatsapp ||
      branch.email ||
      branch.opening_hours,
  );

  return (
    <div className="min-h-screen bg-[#f7f5f0] dark:bg-[#0f1512]">
      {/* ---------------------------------------------------------------
          Header — branch identity. Kept deliberately simple: someone who
          just scanned a code in the store needs to confirm they're in
          the right place, not navigate a site.
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
              className="absolute inset-0 h-full w-full object-cover opacity-30"
            />
            <div
              className="absolute inset-0 bg-gradient-to-b from-[#17382f]/70 via-[#17382f]/80 to-[#17382f]"
              aria-hidden
            />
          </>
        )}

        <div className="relative mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
          <nav className="mb-6 flex items-center gap-1.5 text-xs text-white/60">
            <Link href="/offers" className="transition-colors hover:text-white">
              Offers
            </Link>
            <ChevronRight className="h-3 w-3" aria-hidden />
            <span className="text-white/90">{branch.name}</span>
          </nav>

          <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
            {logo && (
              // eslint-disable-next-line @next/next/no-img-element -- see above
              <img
                src={logo}
                alt=""
                className="h-16 w-16 shrink-0 rounded-2xl bg-white/95 object-contain p-2 shadow-lg sm:h-20 sm:w-20"
              />
            )}
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold uppercase tracking-wide sm:text-4xl">
                {branch.name}
              </h1>
              {branch.city && (
                <p className="mt-1.5 inline-flex items-center gap-1.5 text-sm text-[#d8c9a3]">
                  <MapPin className="h-3.5 w-3.5" aria-hidden />
                  {branch.city}
                </p>
              )}
            </div>
          </div>

          {branch.description && (
            <p className="mt-5 max-w-2xl text-sm leading-relaxed text-white/75 sm:text-base">
              {branch.description}
            </p>
          )}

          {branch.other_branches.length > 0 && (
            <div className="mt-7">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-white/45">
                Other branches
              </p>
              <div className="flex flex-wrap gap-2">
                {branch.other_branches.map((b) => (
                  <Link
                    key={b.slug}
                    href={`/offers/${b.slug}`}
                    className="rounded-full border border-white/20 bg-white/5 px-3 py-1.5 text-xs text-white/80 transition-colors hover:border-[#b89c5c] hover:bg-white/10 hover:text-white"
                  >
                    {b.name}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
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
      --------------------------------------------------------------- */}
      <footer className="border-t border-black/5 bg-[#17382f] text-white dark:border-white/10">
        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wider text-[#d8c9a3]">
                {branch.name}
              </h2>
              {branch.address && (
                <p className="mt-3 flex items-start gap-2 text-sm leading-relaxed text-white/70">
                  <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-[#b89c5c]" aria-hidden />
                  <span>{branch.address}</span>
                </p>
              )}
              {branch.maps_url && (
                <a
                  href={branch.maps_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-[#b89c5c]/40 px-3 py-1.5 text-xs text-[#d8c9a3] transition-colors hover:bg-[#b89c5c]/15"
                >
                  <MapPin className="h-3.5 w-3.5" aria-hidden />
                  Get directions
                </a>
              )}
            </div>

            {hasContact && (
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-wider text-[#d8c9a3]">
                  Contact
                </h2>
                <ul className="mt-3 space-y-2.5 text-sm text-white/70">
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
                        <Phone className="h-4 w-4 text-[#b89c5c]" aria-hidden />
                        WhatsApp {branch.whatsapp}
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
              </div>
            )}

            {socials.length > 0 && (
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-wider text-[#d8c9a3]">
                  Follow us
                </h2>
                <div className="mt-3 flex flex-wrap gap-2">
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
              </div>
            )}
          </div>

          <div className="mt-10 border-t border-white/10 pt-6 text-xs text-white/40">
            <p>
              © {new Date().getFullYear()} Paris United Group. All rights
              reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
