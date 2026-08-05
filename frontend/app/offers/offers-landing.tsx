"use client";

/**
 * Public offers landing — every branch, every campaign, every flyer.
 *
 * Two things this deliberately fixes from the previous version:
 *
 * 1. It renders ``all_catalogues``. The API has always returned every
 *    active + rendered catalogue regardless of campaign attachment,
 *    precisely so this page can't look empty while flyers exist — but
 *    the old landing rendered only campaigns, so a catalogue with no
 *    campaign (or whose campaign fell outside its date window) was
 *    invisible. That is what left this page blank in production.
 *
 * 2. It distinguishes "nothing published" from "couldn't reach the
 *    API". The fetch layer collapses errors into an empty index, which
 *    used to render a confident "no offers yet" during an outage.
 *
 * Filtering runs client-side over the already-fetched payload: the
 * index is one small JSON document, so filtering locally is instant
 * and lets the page stay fully cacheable at the CDN.
 */

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  BookOpen,
  Flame,
  MapPin,
  Search,
  Sparkles,
  Store,
  X,
  Zap,
} from "lucide-react";

import type {
  OfferIndexCampaign,
  OffersIndexCatalogue,
  OffersIndexResult,
} from "@/lib/public-offers";
import { cn } from "@/lib/utils";

import { CampaignCard, CatalogueCard, SectionHeading } from "./offer-cards";
import { OffersFooter } from "./offers-footer";

type FlagFilter = "killer" | "featured" | "flash" | "expired";

/**
 * Filter inputs, resolved to plain values so the logic below is pure
 * and unit-testable without rendering anything.
 *
 * ``branchName`` is the branch's display NAME, not its slug: campaign
 * and catalogue rows carry a branch label, so resolving slug → name
 * happens once in the component rather than inside every comparison.
 */
export interface CampaignFilterState {
  branchName: string | null;
  query: string;
  flags: FlagFilter[];
}

/** Case-insensitive "does this row belong to the selected branch?".
 *
 * A row with no branch of its own runs group-wide and therefore
 * belongs to EVERY branch — excluding it would hide the main weekly
 * flyer the moment a shopper picks their store.
 */
function branchMatches(
  rowBranch: string | null | undefined,
  branchName: string | null,
): boolean {
  if (!branchName) return true;
  if (!rowBranch) return true;
  return rowBranch.trim().toLowerCase() === branchName.trim().toLowerCase();
}

function textMatches(haystack: string, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return haystack.toLowerCase().includes(needle);
}

export function filterCampaigns(
  rows: OfferIndexCampaign[],
  state: CampaignFilterState,
): OfferIndexCampaign[] {
  const promo = state.flags.filter((f) => f !== "expired");
  const showExpired = state.flags.includes("expired");
  return rows.filter((c) => {
    if (!branchMatches(c.branch, state.branchName)) return false;
    if (!textMatches(`${c.title} ${c.description ?? ""} ${c.branch ?? ""}`, state.query)) {
      return false;
    }
    // Promo flags OR together — ticking Killer + Flash means "either",
    // which is how a row of filter chips reads to a shopper.
    if (promo.length > 0) {
      const hit = promo.some(
        (f) =>
          (f === "killer" && c.is_killer_offer) ||
          (f === "featured" && c.is_featured) ||
          (f === "flash" && c.is_flash_sale),
      );
      if (!hit) return false;
    }
    // "Ended" is a state, not a promo type: unticked hides expired
    // campaigns outright rather than acting as another OR term.
    if (!showExpired && c.is_expired) return false;
    return true;
  });
}

export function filterCatalogues(
  rows: OffersIndexCatalogue[],
  state: CampaignFilterState,
): OffersIndexCatalogue[] {
  return rows.filter((c) => {
    if (!branchMatches(c.branch_name, state.branchName)) return false;
    if (!textMatches(`${c.title} ${c.description ?? ""}`, state.query)) {
      return false;
    }
    // Catalogues carry only the "featured" flag; the promo flags are a
    // campaign-level concept, so they don't narrow this list.
    if (state.flags.includes("featured") && !c.is_featured) return false;
    return true;
  });
}

const FLAGS: { key: FlagFilter; label: string; Icon: typeof Flame }[] = [
  { key: "killer", label: "Killer offers", Icon: Flame },
  { key: "featured", label: "Featured", Icon: Sparkles },
  { key: "flash", label: "Flash sales", Icon: Zap },
  { key: "expired", label: "Ended", Icon: BookOpen },
];

interface Props {
  index: OffersIndexResult;
  initialBranch?: string;
  initialQuery?: string;
}

export function OffersLanding({ index, initialBranch, initialQuery }: Props) {
  const [branch, setBranch] = React.useState(initialBranch ?? "");
  const [query, setQuery] = React.useState(initialQuery ?? "");
  const [flags, setFlags] = React.useState<Set<FlagFilter>>(new Set());

  function toggleFlag(f: FlagFilter) {
    setFlags((prev) => {
      const next = new Set(prev);
      if (next.has(f)) next.delete(f);
      else next.add(f);
      return next;
    });
  }

  const selectedBranch = React.useMemo(
    () => index.branches.find((b) => b.slug === branch) ?? null,
    [index.branches, branch],
  );

  const filterState: CampaignFilterState = React.useMemo(
    () => ({
      branchName: selectedBranch?.name ?? null,
      query,
      flags: [...flags],
    }),
    [selectedBranch, query, flags],
  );

  const campaigns = React.useMemo(
    () => filterCampaigns(index.all_campaigns, filterState),
    [index.all_campaigns, filterState],
  );
  const catalogues = React.useMemo(
    () => filterCatalogues(index.all_catalogues, filterState),
    [index.all_catalogues, filterState],
  );

  const hasFilters = Boolean(branch || query.trim() || flags.size);
  const nothingToShow = campaigns.length === 0 && catalogues.length === 0;

  return (
    <div className="min-h-screen bg-[#f7f5f0] dark:bg-[#0f1512]">
      <header className="bg-[#17382f] text-white">
        <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-5xl">
            Offers &amp; Catalogues
          </h1>
          <p className="mt-3 max-w-2xl text-sm text-white/70 sm:text-base">
            The latest hypermarket flyers, killer offers and flash sales from
            Paris United Group — refreshed weekly across every branch.
          </p>

          {index.branches.length > 0 && (
            <div className="mt-8">
              <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-white/45">
                Shop by branch
              </p>
              <div className="flex flex-wrap gap-2">
                {index.branches.map((b) => (
                  <Link
                    key={b.slug}
                    href={`/offers/${b.slug}`}
                    className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/5 px-3.5 py-2 text-xs text-white/85 transition-colors hover:border-[#b89c5c] hover:bg-[#b89c5c]/15 hover:text-white"
                  >
                    <Store className="h-3.5 w-3.5 text-[#b89c5c]" aria-hidden />
                    {b.name}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        {index.unavailable && (
          <div
            role="alert"
            className="mb-8 flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-900 dark:text-amber-200"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <div>
              <p className="font-medium">Offers are temporarily unavailable</p>
              <p className="mt-0.5 text-amber-800/80 dark:text-amber-200/70">
                We couldn&apos;t load the latest catalogues just now. Please
                refresh in a moment.
              </p>
            </div>
          </div>
        )}

        <div className="mb-8 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-black/5 dark:bg-white/[0.04] dark:ring-white/10">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black/35 dark:text-white/35"
                aria-hidden
              />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search offers and catalogues"
                aria-label="Search offers and catalogues"
                className="w-full rounded-xl border border-black/10 bg-[#f7f5f0] py-2.5 pl-9 pr-3 text-sm text-[#17382f] outline-none transition-colors placeholder:text-black/35 focus:border-[#b89c5c] dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder:text-white/35"
              />
            </div>

            <div className="relative sm:w-56">
              <MapPin
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-black/35 dark:text-white/35"
                aria-hidden
              />
              <select
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                aria-label="Filter by branch"
                className="w-full appearance-none rounded-xl border border-black/10 bg-[#f7f5f0] py-2.5 pl-9 pr-8 text-sm text-[#17382f] outline-none transition-colors focus:border-[#b89c5c] dark:border-white/10 dark:bg-white/5 dark:text-white"
              >
                <option value="">All branches</option>
                {index.branches.map((b) => (
                  <option key={b.slug} value={b.slug}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            {FLAGS.map(({ key, label, Icon }) => {
              const on = flags.has(key);
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleFlag(key)}
                  aria-pressed={on}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                    on
                      ? "border-[#17382f] bg-[#17382f] text-white dark:border-[#b89c5c] dark:bg-[#b89c5c] dark:text-[#17382f]"
                      : "border-black/10 bg-transparent text-black/60 hover:border-[#b89c5c] hover:text-[#17382f] dark:border-white/15 dark:text-white/60 dark:hover:text-white",
                  )}
                >
                  <Icon className="h-3 w-3" aria-hidden />
                  {label}
                </button>
              );
            })}

            {hasFilters && (
              <button
                type="button"
                onClick={() => {
                  setBranch("");
                  setQuery("");
                  setFlags(new Set());
                }}
                className="inline-flex items-center gap-1 rounded-full px-2.5 py-1.5 text-xs text-black/45 underline-offset-2 hover:underline dark:text-white/45"
              >
                <X className="h-3 w-3" aria-hidden />
                Clear
              </button>
            )}
          </div>

          {selectedBranch && (
            <p className="mt-3 text-xs text-black/50 dark:text-white/50">
              Showing {selectedBranch.name} plus group-wide offers.{" "}
              <Link
                href={`/offers/${selectedBranch.slug}`}
                className="font-medium text-[#17382f] underline underline-offset-2 dark:text-[#d8c9a3]"
              >
                Open the {selectedBranch.name} page
              </Link>
            </p>
          )}
        </div>

        {nothingToShow && !index.unavailable && (
          <div className="rounded-3xl border border-dashed border-black/10 bg-white/60 px-6 py-16 text-center dark:border-white/10 dark:bg-white/[0.03]">
            <BookOpen className="mx-auto h-8 w-8 text-[#17382f]/30 dark:text-white/25" />
            <h2 className="mt-4 text-lg font-semibold text-[#17382f] dark:text-white">
              {hasFilters
                ? "Nothing matches those filters"
                : "No offers published yet"}
            </h2>
            <p className="mx-auto mt-2 max-w-sm text-sm text-black/55 dark:text-white/55">
              {hasFilters
                ? "Try clearing a filter or picking a different branch."
                : "New catalogues appear here as soon as they're published."}
            </p>
          </div>
        )}

        {catalogues.length > 0 && (
          <section className="mb-14">
            <SectionHeading
              title="Latest catalogues"
              subtitle={`${catalogues.length} flyer${catalogues.length === 1 ? "" : "s"} available`}
            />
            <div className="grid grid-cols-2 gap-4 sm:gap-5 lg:grid-cols-4">
              {catalogues.map((c) => (
                <CatalogueCard key={c.slug} catalogue={c} />
              ))}
            </div>
          </section>
        )}

        {campaigns.length > 0 && (
          <section>
            <SectionHeading
              title="Campaigns"
              subtitle={`${campaigns.length} campaign${campaigns.length === 1 ? "" : "s"}`}
            />
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {campaigns.map((c) => (
                <CampaignCard key={c.slug} campaign={c} />
              ))}
            </div>
          </section>
        )}
      </main>

      <OffersFooter />
    </div>
  );
}
