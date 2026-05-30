"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  Clock,
  Filter,
  Flame,
  MapPin,
  Search,
  Sparkles,
  Tag,
  X,
  Zap,
} from "lucide-react";

import { PageHero } from "@/components/site/page-hero";
import type {
  OfferIndexCampaign,
  OffersIndex,
} from "@/lib/public-offers";
import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";


// Banner image for the offers landing hero. CSP allows ``https:``
// img-src (see ``frontend/next.config.mjs``) so a CDN URL works
// out of the box; swap with a CMS-managed value once the
// ``site_settings`` table grows an ``offers_banner_image_url`` key.
const OFFERS_BANNER_IMAGE =
  "https://images.unsplash.com/photo-1607082352121-fa243f3dde32?auto=format&fit=crop&w=1920&q=80";


// ---------------------------------------------------------------------------
// Filter types — all derive from existing OfferCampaign fields, no new DB
// columns required. Multi-select shape so the operator can combine "Killer
// + Featured" or "Running + Expired" the same way as the branch facet.
// ---------------------------------------------------------------------------

type OfferType = "killer" | "featured" | "flash";
type Status = "running" | "expired";

const OFFER_TYPES: OfferType[] = ["killer", "featured", "flash"];
const STATUSES: Status[] = ["running", "expired"];


interface Props {
  index: OffersIndex;
  initialBranch?: string;
  initialQuery?: string;
}


export function OffersLanding({ index, initialBranch, initialQuery }: Props) {
  const router = useRouter();
  const params = useSearchParams();

  // Filter state — initialised from URL params so an external link to
  // ``/offers?type=killer,featured&status=running`` opens with those
  // chips already toggled. Subsequent toggles update state + push the
  // URL via ``router.replace`` so navigation stays shareable AND the
  // filtering itself happens in-memory (no server round-trip on every
  // chip click).
  const [branch, setBranch] = React.useState<string>(initialBranch ?? "");
  const [query, setQuery] = React.useState<string>(initialQuery ?? "");
  const [searchInput, setSearchInput] = React.useState<string>(
    initialQuery ?? "",
  );
  const [types, setTypes] = React.useState<OfferType[]>(() =>
    parseCsvParam<OfferType>(params?.get("type"), OFFER_TYPES),
  );
  const [statuses, setStatuses] = React.useState<Status[]>(() =>
    parseCsvParam<Status>(params?.get("status"), STATUSES),
  );

  // Sync state → URL whenever a filter changes. ``scroll: false`` keeps
  // the user's scroll position when they tap a chip mid-page.
  React.useEffect(() => {
    const sp = new URLSearchParams();
    if (branch) sp.set("branch", branch);
    if (query) sp.set("q", query);
    if (types.length > 0) sp.set("type", types.join(","));
    if (statuses.length > 0) sp.set("status", statuses.join(","));
    const qs = sp.toString();
    router.replace(qs ? `/offers?${qs}` : "/offers", { scroll: false });
  }, [branch, query, types, statuses, router]);

  function toggleType(t: OfferType) {
    setTypes((cur) =>
      cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t],
    );
  }

  function toggleStatus(s: Status) {
    setStatuses((cur) =>
      cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s],
    );
  }

  function clearAll() {
    setBranch("");
    setQuery("");
    setSearchInput("");
    setTypes([]);
    setStatuses([]);
  }

  function onSubmitSearch(e: React.FormEvent) {
    e.preventDefault();
    setQuery(searchInput.trim());
  }

  const activeFilterCount =
    (branch ? 1 : 0) +
    (query ? 1 : 0) +
    types.length +
    statuses.length;

  // ----- Filtered + sorted view ------------------------------------------
  //
  // All filtering runs client-side on the already-fetched index. Active
  // campaigns sort above expired ones; within each group the backend's
  // server-side order (sort_order + created_at desc, see
  // ``app/api/endpoints/marketing_public.py``) is preserved.
  const filtered = React.useMemo(
    () =>
      filterCampaigns(index.all_campaigns, {
        branch,
        query,
        types,
        statuses,
      }),
    [index.all_campaigns, branch, query, types, statuses],
  );

  return (
    <main className="min-h-screen bg-background">
      {/* ----- Hero banner -----
          ``size="compact"`` is the offers-specific variant — the
          filter bar + results grid below the hero are the page's
          working surface, so the operator wants the hero to occupy
          less of the first scroll-fold than it does on
          companies / careers / news / about / contact / etc. The
          default ``size`` matches the existing 16/20/24 padding so
          other consumers of ``<PageHero>`` are unaffected. */}
      <PageHero
        size="compact"
        eyebrow="Paris United Group"
        title="Live offers across every branch."
        description="Browse the latest campaigns from our retail partners — flash sales, killer deals and the seasonal catalogues that go with them. Tap a campaign to open its catalogue collection."
        imageUrl={OFFERS_BANNER_IMAGE}
      />

      {/* ----- Filter bar ----- */}
      <section className="border-b border-border/60 bg-background">
        <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6 sm:py-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
            {/* Search */}
            <form
              onSubmit={onSubmitSearch}
              role="search"
              className="flex w-full items-center gap-1 rounded-full border border-border/70 bg-card p-1 sm:max-w-md"
            >
              <Search className="ml-2 h-4 w-4 shrink-0 text-muted-foreground" />
              <input
                type="search"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onBlur={() => setQuery(searchInput.trim())}
                placeholder="Search campaigns…"
                aria-label="Search offers"
                className="min-w-0 flex-1 bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground"
              />
              {searchInput && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchInput("");
                    setQuery("");
                  }}
                  aria-label="Clear search"
                  className="rounded-full p-1 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
              <button
                type="submit"
                className="rounded-full bg-pug-gold-500 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-pug-green-900 transition-colors hover:bg-pug-gold-400"
              >
                Search
              </button>
            </form>

            {/* Branch dropdown — kept as a native select so the
                design system stays untouched and mobile gets the OS
                picker for free. Empty = all branches. */}
            <label className="flex w-full items-center gap-2 sm:w-auto">
              <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Branch
              </span>
              <select
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                aria-label="Filter by branch"
                className="min-w-0 flex-1 rounded-full border border-border/70 bg-card px-3 py-1.5 text-sm outline-none focus:border-pug-gold-400 sm:flex-initial"
              >
                <option value="">All branches</option>
                {index.branches.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>

            {activeFilterCount > 0 && (
              <button
                type="button"
                onClick={clearAll}
                className="inline-flex items-center gap-1 self-start rounded-full border border-border/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground hover:border-foreground/40 hover:text-foreground sm:self-auto"
              >
                <X className="h-3 w-3" />
                Clear ({activeFilterCount})
              </button>
            )}
          </div>

          {/* Chip rows — types + status. Both are independent multi-
              selects. Visually grouped under a small "Filter" label
              so the operator scans the page top-down. */}
          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              <Filter className="h-3 w-3" />
              Type
            </span>
            <TypeChip
              kind="killer"
              active={types.includes("killer")}
              onClick={() => toggleType("killer")}
            />
            <TypeChip
              kind="featured"
              active={types.includes("featured")}
              onClick={() => toggleType("featured")}
            />
            <TypeChip
              kind="flash"
              active={types.includes("flash")}
              onClick={() => toggleType("flash")}
            />

            <span className="ml-2 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Status
            </span>
            <StatusChip
              kind="running"
              active={statuses.includes("running")}
              onClick={() => toggleStatus("running")}
            />
            <StatusChip
              kind="expired"
              active={statuses.includes("expired")}
              onClick={() => toggleStatus("expired")}
            />
          </div>
        </div>
      </section>

      {/* ----- Results grid ----- */}
      <section className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        {filtered.length > 0 ? (
          <>
            <header className="mb-5 flex items-baseline justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                {filtered.length} campaign
                {filtered.length === 1 ? "" : "s"}
              </h2>
            </header>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {filtered.map((c) => (
                <CampaignCard key={c.slug} campaign={c} />
              ))}
            </div>
          </>
        ) : (
          <EmptyState
            hasFilters={activeFilterCount > 0}
            onClear={clearAll}
          />
        )}
      </section>
    </main>
  );
}


// ---------------------------------------------------------------------------
// Filtering — pure, exported for vitest
// ---------------------------------------------------------------------------


export interface CampaignFilterState {
  branch: string;
  query: string;
  types: OfferType[];
  statuses: Status[];
}


export function filterCampaigns(
  campaigns: OfferIndexCampaign[],
  state: CampaignFilterState,
): OfferIndexCampaign[] {
  const needle = state.query.trim().toLowerCase();
  const branchNorm = state.branch.trim();
  const wantRunning = state.statuses.includes("running");
  const wantExpired = state.statuses.includes("expired");

  return campaigns.filter((c) => {
    if (branchNorm && c.branch !== branchNorm) return false;

    if (state.types.length > 0) {
      const matches =
        (state.types.includes("killer") && c.is_killer_offer) ||
        (state.types.includes("featured") && c.is_featured) ||
        (state.types.includes("flash") && c.is_flash_sale);
      if (!matches) return false;
    }

    // Status: empty selection = no filter; single = filter strictly;
    // both selected = no filter (they cancel out).
    if (state.statuses.length === 1) {
      if (wantRunning && c.is_expired) return false;
      if (wantExpired && !c.is_expired) return false;
    }

    if (needle) {
      const haystack = `${c.title} ${c.description ?? ""} ${c.branch ?? ""}`.toLowerCase();
      if (!haystack.includes(needle)) return false;
    }

    return true;
  });
}


function parseCsvParam<T extends string>(
  raw: string | null | undefined,
  allowed: readonly T[],
): T[] {
  if (!raw) return [];
  const parts = raw
    .split(",")
    .map((v) => v.trim().toLowerCase())
    .filter(Boolean);
  return parts.filter((v): v is T => (allowed as readonly string[]).includes(v));
}


// ---------------------------------------------------------------------------
// Chips
// ---------------------------------------------------------------------------


function TypeChip({
  kind,
  active,
  onClick,
}: {
  kind: OfferType;
  active: boolean;
  onClick: () => void;
}) {
  const meta = TYPE_CHIP_META[kind];
  const Icon = meta.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider transition-colors",
        active ? meta.activeClass : meta.inactiveClass,
      )}
    >
      <Icon className="h-3 w-3" />
      {meta.label}
    </button>
  );
}


const TYPE_CHIP_META: Record<
  OfferType,
  {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    activeClass: string;
    inactiveClass: string;
  }
> = {
  killer: {
    label: "Killer",
    icon: Flame,
    activeClass: "border-rose-500 bg-rose-500 text-white",
    inactiveClass:
      "border-rose-500/30 bg-rose-500/5 text-rose-700 hover:border-rose-500/60 dark:text-rose-300",
  },
  featured: {
    label: "Featured",
    icon: Sparkles,
    activeClass: "border-pug-gold-500 bg-pug-gold-500 text-pug-green-900",
    inactiveClass:
      "border-pug-gold-500/30 bg-pug-gold-500/5 text-pug-gold-700 hover:border-pug-gold-500/60 dark:text-pug-gold-300",
  },
  flash: {
    label: "Flash",
    icon: Zap,
    activeClass: "border-sky-500 bg-sky-500 text-white",
    inactiveClass:
      "border-sky-500/30 bg-sky-500/5 text-sky-700 hover:border-sky-500/60 dark:text-sky-300",
  },
};


function StatusChip({
  kind,
  active,
  onClick,
}: {
  kind: Status;
  active: boolean;
  onClick: () => void;
}) {
  const isExpired = kind === "expired";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider transition-colors",
        active
          ? isExpired
            ? "border-foreground bg-foreground text-background"
            : "border-emerald-500 bg-emerald-500 text-white"
          : isExpired
            ? "border-border/70 bg-card text-muted-foreground hover:border-foreground/40"
            : "border-emerald-500/30 bg-emerald-500/5 text-emerald-700 hover:border-emerald-500/60 dark:text-emerald-300",
      )}
    >
      {isExpired ? <Clock className="h-3 w-3" /> : <Sparkles className="h-3 w-3" />}
      {isExpired ? "Expired" : "Running"}
    </button>
  );
}


// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------


function EmptyState({
  hasFilters,
  onClear,
}: {
  hasFilters: boolean;
  onClear: () => void;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-border/60 bg-card p-12 text-center">
      <Tag className="mx-auto mb-3 h-8 w-8 text-muted-foreground/60" />
      <p className="text-base font-semibold">
        {hasFilters ? "No campaigns match these filters." : "No campaigns yet."}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        {hasFilters
          ? "Loosen a chip or clear them all to see everything."
          : "Check back soon — new campaigns go up every week."}
      </p>
      {hasFilters && (
        <button
          type="button"
          onClick={onClear}
          className="mt-4 inline-flex items-center gap-1 rounded-full border border-border/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider hover:border-foreground/40"
        >
          <X className="h-3 w-3" />
          Clear filters
        </button>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Campaign card — preserved from the previous design with an extra
// "emphasis ring" for Killer + Featured rows so they read louder than
// regular campaigns inside the same grid.
// ---------------------------------------------------------------------------


function CampaignCard({ campaign }: { campaign: OfferIndexCampaign }) {
  const cover = campaign.cover_image_url ?? campaign.banner_image_url;
  const expired = campaign.is_expired;
  const emphasis = expired
    ? null
    : campaign.is_killer_offer
      ? "killer"
      : campaign.is_featured
        ? "featured"
        : null;

  return (
    <Link
      href={`/offers/${campaign.slug}`}
      aria-label={
        expired ? `${campaign.title} (expired campaign)` : campaign.title
      }
      className={cn(
        "group block overflow-hidden rounded-2xl border bg-card shadow-sm transition-all hover:shadow-lg",
        expired && "border-border/60 opacity-80 hover:opacity-100",
        !expired && !emphasis && "border-border/60",
        emphasis === "killer" &&
          "border-rose-500/40 ring-1 ring-rose-500/20 hover:ring-rose-500/40",
        emphasis === "featured" &&
          "border-pug-gold-500/40 ring-1 ring-pug-gold-500/20 hover:ring-pug-gold-500/40",
      )}
      style={
        !expired && campaign.theme_color && !emphasis
          ? { boxShadow: `0 1px 0 ${campaign.theme_color}22 inset` }
          : undefined
      }
    >
      <div
        className="relative aspect-[3/4] overflow-hidden bg-muted"
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
            className={cn(
              "h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]",
              expired && "grayscale-[40%]",
            )}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <Tag className="h-8 w-8 opacity-40" />
          </div>
        )}
        {expired && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-foreground/15"
          />
        )}
        {/* Flag chips */}
        <div className="absolute left-3 top-3 flex flex-wrap gap-1">
          {expired && (
            <Pill tone="dark" icon={Clock} label="Expired" />
          )}
          {!expired && campaign.is_killer_offer && (
            <Pill tone="rose" icon={Flame} label="Killer" />
          )}
          {!expired && campaign.is_flash_sale && (
            <Pill tone="sky" icon={Zap} label="Flash" />
          )}
          {!expired && campaign.is_featured && (
            <Pill tone="gold" icon={Sparkles} label="Featured" />
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
        <h3
          className={cn(
            "line-clamp-2 text-base font-semibold leading-snug",
            expired && "text-muted-foreground",
          )}
        >
          {campaign.title}
        </h3>
        {campaign.description && (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {campaign.description}
          </p>
        )}
        <p className="pt-1 text-xs text-muted-foreground">
          {campaign.catalogue_count} catalogue
          {campaign.catalogue_count === 1 ? "" : "s"}
          {campaign.end_date && (
            <>
              {" · "}
              {expired ? "Ended " : "Ends "}
              {formatEndDate(campaign.end_date)}
            </>
          )}
          {" · "}
          <span className="ml-1 inline-flex items-center gap-1 font-medium text-primary">
            {expired ? "View" : "Open"}
            <ArrowRight className="h-3 w-3" />
          </span>
        </p>
      </div>
    </Link>
  );
}


function Pill({
  tone,
  icon: Icon,
  label,
}: {
  tone: "rose" | "sky" | "gold" | "dark";
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
        tone === "rose" && "bg-rose-600/95 text-white",
        tone === "sky" && "bg-sky-600/95 text-white",
        tone === "gold" && "bg-pug-gold-500/95 text-pug-green-800",
        tone === "dark" && "bg-foreground/85 text-background",
      )}
    >
      <Icon className="h-2.5 w-2.5" />
      {label}
    </span>
  );
}


function formatEndDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}
