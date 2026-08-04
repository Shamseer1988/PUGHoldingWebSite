/**
 * Shared presentational pieces for the public offers surface.
 *
 * The landing and every branch storefront render the same campaign and
 * catalogue tiles. Keeping them here means a visual change lands on all
 * of them at once — previously the landing owned its own markup, so the
 * two could drift.
 *
 * Server components: no state, no effects, so they cost nothing on the
 * client bundle.
 */

import Link from "next/link";
import { BookOpen, Clock, Flame, Sparkles, Zap } from "lucide-react";

import type {
  OfferIndexCampaign,
  OffersIndexCatalogue,
} from "@/lib/public-offers";
import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";

/** A catalogue published within this window gets a "NEW" flash. */
const NEW_WINDOW_DAYS = 10;

export function SectionHeading({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-5 flex items-end justify-between gap-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-[#17382f] dark:text-white sm:text-xl">
          {title}
        </h2>
        {subtitle && (
          <p className="mt-0.5 text-sm text-black/50 dark:text-white/50">
            {subtitle}
          </p>
        )}
      </div>
      {/* Gold rule echoes the QR badge ring — ties the printed asset to
          the page it lands on. */}
      <span
        className="hidden h-px flex-1 bg-gradient-to-r from-[#b89c5c]/40 to-transparent sm:block"
        aria-hidden
      />
    </div>
  );
}

function isNew(createdAt: string | null): boolean {
  if (!createdAt) return false;
  const age = Date.now() - new Date(createdAt).getTime();
  return age >= 0 && age < NEW_WINDOW_DAYS * 24 * 60 * 60 * 1000;
}

export function Flag({
  tone,
  children,
}: {
  tone: "killer" | "flash" | "featured" | "expired" | "new" | "branch";
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
        tone === "killer" && "bg-rose-600 text-white",
        tone === "flash" && "bg-amber-500 text-[#17382f]",
        tone === "featured" && "bg-[#b89c5c] text-[#17382f]",
        tone === "new" && "bg-emerald-600 text-white",
        tone === "expired" && "bg-black/45 text-white backdrop-blur-sm",
        tone === "branch" &&
          "bg-white/90 text-[#17382f] dark:bg-white/15 dark:text-white",
      )}
    >
      {children}
    </span>
  );
}

export function CatalogueCard({
  catalogue,
}: {
  catalogue: OffersIndexCatalogue;
}) {
  const cover = resolveAssetUrl(catalogue.cover_image_url);
  return (
    <Link
      href={`/offers/catalogues/${catalogue.slug}`}
      className="group flex flex-col overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-black/5 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl dark:bg-white/[0.04] dark:ring-white/10"
    >
      <div className="relative aspect-[3/4] overflow-hidden bg-[#ece7dc] dark:bg-white/5">
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element -- CMS/R2 URL
          <img
            src={cover}
            alt={catalogue.title}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <BookOpen className="h-8 w-8 text-[#17382f]/20 dark:text-white/20" />
          </div>
        )}

        <div className="absolute left-2 top-2 flex flex-wrap gap-1">
          {isNew(catalogue.created_at) && <Flag tone="new">New</Flag>}
          {catalogue.is_featured && <Flag tone="featured">Featured</Flag>}
        </div>
        {catalogue.branch_name && (
          <div className="absolute bottom-2 left-2">
            <Flag tone="branch">{catalogue.branch_name}</Flag>
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col p-3">
        <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-[#17382f] dark:text-white">
          {catalogue.title}
        </h3>
        <p className="mt-auto pt-2 text-[11px] text-black/45 dark:text-white/45">
          {catalogue.page_count} page{catalogue.page_count === 1 ? "" : "s"}
        </p>
      </div>
    </Link>
  );
}

export function CampaignCard({
  campaign,
}: {
  campaign: OfferIndexCampaign;
}) {
  const cover = resolveAssetUrl(
    campaign.cover_image_url || campaign.banner_image_url,
  );
  return (
    <Link
      href={`/offers/${campaign.slug}`}
      className={cn(
        "group flex flex-col overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-black/5 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl dark:bg-white/[0.04] dark:ring-white/10",
        campaign.is_expired && "opacity-75",
      )}
    >
      <div className="relative aspect-[16/10] overflow-hidden bg-[#ece7dc] dark:bg-white/5">
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element -- CMS/R2 URL
          <img
            src={cover}
            alt={campaign.title}
            loading="lazy"
            className={cn(
              "h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]",
              campaign.is_expired && "grayscale",
            )}
          />
        ) : (
          <div
            className="flex h-full items-center justify-center"
            style={
              campaign.theme_color
                ? { backgroundColor: campaign.theme_color }
                : undefined
            }
          >
            <Sparkles className="h-8 w-8 text-white/40" />
          </div>
        )}

        <div className="absolute left-2.5 top-2.5 flex flex-wrap gap-1">
          {campaign.is_killer_offer && (
            <Flag tone="killer">
              <Flame className="h-2.5 w-2.5" aria-hidden />
              Killer
            </Flag>
          )}
          {campaign.is_flash_sale && (
            <Flag tone="flash">
              <Zap className="h-2.5 w-2.5" aria-hidden />
              Flash
            </Flag>
          )}
          {campaign.is_featured && <Flag tone="featured">Featured</Flag>}
        </div>
        {campaign.is_expired && (
          <div className="absolute right-2.5 top-2.5">
            <Flag tone="expired">Ended</Flag>
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col p-4">
        <h3 className="line-clamp-2 font-semibold leading-snug text-[#17382f] dark:text-white">
          {campaign.title}
        </h3>
        {campaign.description && (
          <p className="mt-1.5 line-clamp-2 text-sm text-black/55 dark:text-white/55">
            {campaign.description}
          </p>
        )}
        <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-3 text-[11px] text-black/45 dark:text-white/45">
          <span className="inline-flex items-center gap-1">
            <BookOpen className="h-3 w-3" aria-hidden />
            {campaign.catalogue_count} catalogue
            {campaign.catalogue_count === 1 ? "" : "s"}
          </span>
          {campaign.end_date && (
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" aria-hidden />
              {campaign.is_expired ? "Ended" : "Until"}{" "}
              {new Date(campaign.end_date).toLocaleDateString(undefined, {
                day: "numeric",
                month: "short",
              })}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
