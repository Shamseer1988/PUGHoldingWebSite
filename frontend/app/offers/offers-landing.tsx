"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  BookOpen,
  Flame,
  MapPin,
  Search,
  Sparkles,
  Tag,
  Zap,
} from "lucide-react";

import type {
  OfferIndexCampaign,
  OffersIndex,
  OffersIndexCatalogue,
} from "@/lib/public-offers";
import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";


interface Props {
  index: OffersIndex;
  initialBranch?: string;
  initialQuery?: string;
}


export function OffersLanding({ index, initialBranch, initialQuery }: Props) {
  const router = useRouter();
  const params = useSearchParams();
  const [searchInput, setSearchInput] = React.useState(initialQuery ?? "");
  const currentBranch = initialBranch ?? "";

  function applyFilters(nextBranch: string | null, nextQuery: string | null) {
    const sp = new URLSearchParams(params?.toString() ?? "");
    if (nextBranch) sp.set("branch", nextBranch);
    else sp.delete("branch");
    if (nextQuery) sp.set("q", nextQuery);
    else sp.delete("q");
    const qs = sp.toString();
    router.push(qs ? `/offers?${qs}` : "/offers");
  }

  function onSubmitSearch(e: React.FormEvent) {
    e.preventDefault();
    applyFilters(currentBranch || null, searchInput.trim() || null);
  }

  function onPickBranch(branch: string | null) {
    applyFilters(branch, searchInput.trim() || null);
  }

  return (
    <main className="min-h-screen bg-background">
      {/* ----- Compact banner ----- */}
      <section className="border-b border-border/60 bg-card/40">
        <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6 sm:py-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                Paris United Group · Offers
              </p>
              <h1 className="mt-0.5 text-xl font-semibold leading-tight sm:text-2xl">
                Catalogues, killer offers & flash sales.
              </h1>
            </div>

            <form
              onSubmit={onSubmitSearch}
              className="flex w-full items-center gap-1 rounded-full border border-border/70 bg-background p-1 sm:w-80"
              role="search"
            >
              <Search className="ml-2 h-4 w-4 shrink-0 text-muted-foreground" />
              <input
                type="search"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search catalogues…"
                className="min-w-0 flex-1 bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground"
                aria-label="Search offers"
              />
              <button
                type="submit"
                className="rounded-full bg-pug-gold-400 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-pug-green-800 transition-colors hover:bg-pug-gold-300"
              >
                Search
              </button>
            </form>
          </div>

          {/* Branch facet — inline below the row */}
          {index.branches.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              <BranchChip
                label="All branches"
                active={!currentBranch}
                onClick={() => onPickBranch(null)}
              />
              {index.branches.map((b) => (
                <BranchChip
                  key={b}
                  label={b}
                  active={currentBranch === b}
                  onClick={() => onPickBranch(b)}
                />
              ))}
            </div>
          )}
        </div>
      </section>

      {/* ----- Killer offers carousel ----- */}
      {index.killer_offers.length > 0 && (
        <SectionBlock
          eyebrow="Killer offers"
          icon={Flame}
          title="Don't sleep on these."
          subtitle="Hand-picked deals from our retail partners — limited time, limited stock."
        >
          <Carousel campaigns={index.killer_offers} accent="killer" />
        </SectionBlock>
      )}

      {/* ----- Flash sales strip ----- */}
      {index.flash_sales.length > 0 && (
        <SectionBlock
          eyebrow="Flash sales"
          icon={Zap}
          title="Live right now."
          subtitle="Short-window prices on essentials — ends when the timer hits zero."
          accent="flash"
        >
          <Carousel campaigns={index.flash_sales} accent="flash" />
        </SectionBlock>
      )}

      {/* ----- Featured grid ----- */}
      {index.featured.length > 0 && (
        <SectionBlock
          eyebrow="Featured catalogues"
          icon={Sparkles}
          title="Worth a flip."
        >
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {index.featured.map((c) => (
              <CampaignCard key={c.slug} campaign={c} large />
            ))}
          </div>
        </SectionBlock>
      )}

      {/* ----- All campaigns ----- */}
      {index.all_campaigns.length > 0 && (
        <SectionBlock
          eyebrow="All offers"
          icon={Tag}
          title="Every active campaign."
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {index.all_campaigns.map((c) => (
              <CampaignCard key={c.slug} campaign={c} />
            ))}
          </div>
        </SectionBlock>
      )}

      {/* ----- Catalogues (every active+ready catalogue) ----- */}
      {index.all_catalogues.length > 0 && (
        <SectionBlock
          eyebrow="Catalogues"
          icon={BookOpen}
          title="Browse the full library."
          subtitle="Every active flyer — tap to open the page-flip viewer."
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {index.all_catalogues.map((c) => (
              <CatalogueCard key={c.slug} catalogue={c} />
            ))}
          </div>
        </SectionBlock>
      )}

      {/* ----- Global empty state ----- */}
      {index.all_campaigns.length === 0 &&
        index.all_catalogues.length === 0 && (
          <SectionBlock
            eyebrow="Nothing yet"
            icon={Tag}
            title="No active offers."
          >
            <div className="rounded-2xl border border-dashed border-border/60 bg-background p-12 text-center text-sm text-muted-foreground">
              {currentBranch || searchInput ? (
                <>
                  No offers match your{" "}
                  {[currentBranch && "branch", searchInput && "search"]
                    .filter(Boolean)
                    .join(" + ")}{" "}
                  filter. Try clearing it to see everything.
                </>
              ) : (
                <>
                  Check back soon — new flyers go up every week. If
                  you&apos;re an admin, upload a catalogue and toggle
                  the parent campaign to <strong>Active</strong> to see
                  it here.
                </>
              )}
            </div>
          </SectionBlock>
        )}
    </main>
  );
}


// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function BranchChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        active
          ? "border-pug-gold-400 bg-pug-gold-400 text-pug-green-800"
          : "border-border/70 bg-background text-foreground/80 hover:border-pug-gold-400/60 hover:text-foreground"
      )}
    >
      <MapPin className="h-3 w-3" />
      {label}
    </button>
  );
}


function SectionBlock({
  eyebrow,
  icon: Icon,
  title,
  subtitle,
  children,
  accent,
}: {
  eyebrow: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  accent?: "killer" | "flash";
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
      <header className="mb-6 flex flex-col gap-1.5">
        <span
          className={cn(
            "inline-flex w-fit items-center gap-1.5 rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em]",
            accent === "killer" &&
              "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300",
            accent === "flash" &&
              "border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-300",
            !accent &&
              "border-pug-gold-500/40 bg-pug-gold-500/10 text-pug-gold-700 dark:text-pug-gold-300"
          )}
        >
          <Icon className="h-3 w-3" />
          {eyebrow}
        </span>
        <h2 className="text-2xl font-semibold sm:text-3xl">{title}</h2>
        {subtitle && (
          <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">
            {subtitle}
          </p>
        )}
      </header>
      {children}
    </section>
  );
}


function Carousel({
  campaigns,
  accent,
}: {
  campaigns: OfferIndexCampaign[];
  accent?: "killer" | "flash";
}) {
  return (
    <div className="-mx-4 overflow-x-auto px-4 sm:-mx-6 sm:px-6">
      <div className="flex snap-x snap-mandatory gap-4 pb-2">
        {campaigns.map((c) => (
          <div
            key={c.slug}
            className="min-w-[260px] max-w-[260px] shrink-0 snap-start sm:min-w-[300px] sm:max-w-[300px]"
          >
            <CampaignCard campaign={c} accent={accent} />
          </div>
        ))}
      </div>
    </div>
  );
}


function CampaignCard({
  campaign,
  accent,
  large,
}: {
  campaign: OfferIndexCampaign;
  accent?: "killer" | "flash";
  large?: boolean;
}) {
  const cover = campaign.cover_image_url ?? campaign.banner_image_url;
  // The cover usually has a 2:3 aspect (vertical catalogue page),
  // but if the campaign only has a wide banner image (16:9) we
  // render that one instead. Either way we use ``object-cover`` so
  // the card always fills its slot.
  return (
    <Link
      href={`/offers/${campaign.slug}`}
      className="group block overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm transition-all hover:shadow-lg"
      style={
        campaign.theme_color
          ? {
              boxShadow: `0 1px 0 ${campaign.theme_color}22 inset`,
            }
          : undefined
      }
    >
      <div
        className={cn(
          "relative overflow-hidden bg-muted",
          large ? "aspect-[4/3]" : "aspect-[3/4]"
        )}
        style={{
          background: campaign.theme_color
            ? `${campaign.theme_color}10`
            : undefined,
        }}
      >
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={resolveAssetUrl(cover) ?? ""}
            alt={campaign.title}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <Tag className="h-8 w-8 opacity-40" />
          </div>
        )}
        {/* Flag chips overlay */}
        <div className="absolute left-3 top-3 flex flex-wrap gap-1">
          {campaign.is_killer_offer && (
            <span className="inline-flex items-center gap-1 rounded-full bg-rose-600/95 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white">
              <Flame className="h-2.5 w-2.5" />
              Killer
            </span>
          )}
          {campaign.is_flash_sale && (
            <span className="inline-flex items-center gap-1 rounded-full bg-sky-600/95 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white">
              <Zap className="h-2.5 w-2.5" />
              Flash
            </span>
          )}
          {campaign.is_featured && (
            <span className="inline-flex items-center gap-1 rounded-full bg-pug-gold-500/95 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-pug-green-800">
              <Sparkles className="h-2.5 w-2.5" />
              Featured
            </span>
          )}
        </div>
      </div>
      <div className="space-y-1 p-4">
        {campaign.branch && (
          <p className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            <MapPin className="h-3 w-3" />
            {campaign.branch}
          </p>
        )}
        <h3 className="line-clamp-2 text-base font-semibold leading-snug">
          {campaign.title}
        </h3>
        {campaign.description && (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {campaign.description}
          </p>
        )}
        <p className="pt-1 text-xs text-muted-foreground">
          {campaign.catalogue_count} catalogue
          {campaign.catalogue_count === 1 ? "" : "s"} ·
          <span className="ml-1 inline-flex items-center gap-1 font-medium text-primary">
            Open
            <ArrowRight className="h-3 w-3" />
          </span>
        </p>
      </div>
    </Link>
  );
}


function CatalogueCard({ catalogue }: { catalogue: OffersIndexCatalogue }) {
  // Standalone catalogue card — links straight into the viewer.
  return (
    <Link
      href={`/offers/catalogues/${catalogue.slug}`}
      className="group block overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm transition-all hover:shadow-lg"
    >
      <div className="relative aspect-[3/4] overflow-hidden bg-muted">
        {catalogue.cover_image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={resolveAssetUrl(catalogue.cover_image_url) ?? ""}
            alt={catalogue.title}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <BookOpen className="h-10 w-10 opacity-40" />
          </div>
        )}
      </div>
      <div className="space-y-1 p-4">
        <h3 className="line-clamp-2 text-base font-semibold leading-snug">
          {catalogue.title}
        </h3>
        {catalogue.description && (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {catalogue.description}
          </p>
        )}
        <p className="pt-1 text-xs text-muted-foreground">
          {catalogue.page_count} page
          {catalogue.page_count === 1 ? "" : "s"} ·
          <span className="ml-1 inline-flex items-center gap-1 font-medium text-primary">
            Open viewer
            <ArrowRight className="h-3 w-3" />
          </span>
        </p>
      </div>
    </Link>
  );
}
