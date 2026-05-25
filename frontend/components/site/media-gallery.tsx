"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Images,
  ImageIcon,
  Maximize2,
  Play,
  Sparkles,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  resolveAssetUrl,
  type PublicMediaAsset,
} from "@/lib/public-api";
import { cn } from "@/lib/utils";


/**
 * Public-side gallery powered by the admin Media Gallery.
 *
 * Renders as a glass-album: a soft, brand-aligned panel with category
 * pills, masonry-style tiles, and a lightbox. Categories are derived
 * from the asset's `tags` field — tag an asset `stores`, `events`,
 * `team`, or `campaigns` to file it under the matching tab.
 *
 * Per-asset visibility is controlled server-side (`is_public` flag on
 * MediaAsset) — hidden assets never reach this component.
 */

export type MediaCategory = "stores" | "events" | "team" | "campaigns";
const CATEGORIES: MediaCategory[] = ["stores", "events", "team", "campaigns"];
const CATEGORY_LABELS: Record<MediaCategory, string> = {
  stores: "Stores",
  events: "Events",
  team: "Team",
  campaigns: "Campaigns",
};

// Per-category accent tints used on the tile hover + lightbox badge.
const CATEGORY_ACCENT: Record<MediaCategory, string> = {
  stores: "from-pug-gold-400/70 to-pug-gold-600/70",
  events: "from-rose-400/70 to-pug-gold-500/70",
  team: "from-pug-green-400/70 to-pug-green-700/70",
  campaigns: "from-sky-400/70 to-violet-500/70",
};

interface MediaGalleryProps {
  items: PublicMediaAsset[];
}

interface DerivedItem {
  asset: PublicMediaAsset;
  url: string;
  category: MediaCategory | null;
  title: string;
  description: string | null;
}

function tokenize(tags: string | null): string[] {
  if (!tags) return [];
  return tags
    .split(",")
    .map((t) => t.trim().toLowerCase())
    .filter(Boolean);
}

function deriveCategory(tokens: string[]): MediaCategory | null {
  for (const cat of CATEGORIES) {
    if (tokens.includes(cat)) return cat;
  }
  return null;
}

/**
 * Decide whether a tile spans 2 columns (or 2 rows) so the grid feels
 * editorial rather than a flat 4×N. Stable per-id so layout doesn't
 * shuffle on re-render.
 */
function tileSpan(id: number, index: number): string {
  // Every 5th tile gets a wide span; every 9th gets a tall span. Both
  // sparingly so the masonry feels intentional, not chaotic.
  if (index % 9 === 4) return "sm:col-span-2 sm:row-span-2";
  if (id % 7 === 0) return "lg:col-span-2";
  return "";
}


export function MediaGallery({ items }: MediaGalleryProps) {
  const derived = React.useMemo<DerivedItem[]>(
    () =>
      items.map((asset) => {
        const tokens = tokenize(asset.tags);
        return {
          asset,
          url: resolveAssetUrl(asset.url) ?? asset.url,
          category: deriveCategory(tokens),
          title: asset.title ?? asset.original_name ?? "Untitled",
          description: asset.alt_text,
        };
      }),
    [items]
  );

  const counts = React.useMemo<Record<"all" | MediaCategory, number>>(() => {
    const base = { all: derived.length, stores: 0, events: 0, team: 0, campaigns: 0 };
    for (const d of derived) {
      if (d.category) base[d.category]++;
    }
    return base;
  }, [derived]);

  const availableCategories = React.useMemo<("all" | MediaCategory)[]>(() => {
    return ["all", ...CATEGORIES.filter((c) => counts[c] > 0)];
  }, [counts]);

  const [active, setActive] = React.useState<"all" | MediaCategory>("all");
  const [lightbox, setLightbox] = React.useState<DerivedItem | null>(null);

  const filtered = React.useMemo(
    () =>
      active === "all"
        ? derived
        : derived.filter((item) => item.category === active),
    [derived, active]
  );

  React.useEffect(() => {
    if (!lightbox) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setLightbox(null);
    }
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [lightbox]);

  if (items.length === 0) {
    return (
      <GlassAlbumShell>
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-pug-gold-500/15 text-pug-gold-700 ring-1 ring-pug-gold-500/30 dark:text-pug-gold-300">
            <Images className="h-6 w-6" />
          </span>
          <p className="text-sm font-medium text-foreground">
            No media uploaded yet.
          </p>
          <p className="max-w-md text-xs text-muted-foreground">
            Upload images or videos in <em>Admin → Media gallery</em> and tag
            them <code className="rounded bg-muted px-1">stores</code>,{" "}
            <code className="rounded bg-muted px-1">events</code>,{" "}
            <code className="rounded bg-muted px-1">team</code>, or{" "}
            <code className="rounded bg-muted px-1">campaigns</code> so they
            appear here under the matching tab.
          </p>
        </div>
      </GlassAlbumShell>
    );
  }

  return (
    <>
      <GlassAlbumShell>
        {/* Header with category pills + counter. */}
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-pug-gold-500/15 text-pug-gold-700 ring-1 ring-pug-gold-500/30 dark:text-pug-gold-300">
              <Sparkles className="h-5 w-5" />
            </span>
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-pug-gold-700/80 dark:text-pug-gold-300/80">
                Photo album
              </p>
              <p className="text-sm text-muted-foreground">
                <span className="font-semibold text-foreground">
                  {counts[active === "all" ? "all" : active]}
                </span>{" "}
                {active === "all"
                  ? "stories"
                  : `${CATEGORY_LABELS[active as MediaCategory].toLowerCase()} stories`}
              </p>
            </div>
          </div>

          {availableCategories.length > 1 && (
            <div
              role="tablist"
              aria-label="Filter media by category"
              className="flex flex-wrap items-center gap-1.5 rounded-full border border-border/50 bg-background/60 p-1 backdrop-blur"
            >
              {availableCategories.map((cat) => {
                const label =
                  cat === "all" ? "All" : CATEGORY_LABELS[cat];
                const count = counts[cat];
                const isActive = active === cat;
                return (
                  <button
                    key={cat}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    onClick={() => setActive(cat)}
                    className={cn(
                      "relative inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition",
                      isActive
                        ? "bg-pug-green-700 text-white shadow-sm dark:bg-pug-gold-500 dark:text-pug-green-900"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {label}
                    <span
                      className={cn(
                        "rounded-full px-1.5 py-px text-[10px] font-semibold",
                        isActive
                          ? "bg-white/20 text-white dark:bg-pug-green-900/20 dark:text-pug-green-900"
                          : "bg-muted text-muted-foreground"
                      )}
                    >
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </header>

        {/* Editorial album grid. */}
        <div className="grid auto-rows-[10rem] grid-cols-2 gap-3 sm:auto-rows-[12rem] sm:grid-cols-3 sm:gap-4 lg:grid-cols-4">
          <AnimatePresence mode="popLayout">
            {filtered.map((item, index) => (
              <motion.button
                key={item.asset.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.28, delay: index * 0.015 }}
                type="button"
                onClick={() => setLightbox(item)}
                aria-label={`Open ${item.title}`}
                className={cn(
                  "group relative overflow-hidden rounded-2xl border border-white/20 bg-pug-green-900/5 shadow-[0_8px_30px_-12px_rgba(15,53,32,0.25)] ring-1 ring-black/[0.04] transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_18px_45px_-15px_rgba(15,53,32,0.45)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pug-gold-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background dark:bg-white/[0.03] dark:ring-white/10",
                  tileSpan(item.asset.id, index)
                )}
              >
                {/* Media */}
                {item.asset.kind === "video" ? (
                  <video
                    src={item.url}
                    muted
                    playsInline
                    preload="metadata"
                    className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-[1.08]"
                  />
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={item.url}
                    alt={item.description ?? item.title}
                    loading="lazy"
                    decoding="async"
                    className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-[1.08]"
                  />
                )}

                {/* Per-category coloured glow on hover */}
                <span
                  aria-hidden
                  className={cn(
                    "pointer-events-none absolute inset-0 bg-gradient-to-tr opacity-0 mix-blend-overlay transition-opacity duration-500 group-hover:opacity-100",
                    item.category
                      ? CATEGORY_ACCENT[item.category]
                      : "from-pug-gold-400/60 to-pug-green-700/60"
                  )}
                />

                {/* Bottom shade for legibility */}
                <span
                  aria-hidden
                  className="pointer-events-none absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-pug-green-900/85 via-pug-green-900/30 to-transparent"
                />

                {/* Top-right kind chip + expand glyph */}
                <span className="absolute right-2.5 top-2.5 flex items-center gap-1.5">
                  <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-pug-green-900/45 text-white opacity-0 backdrop-blur transition-opacity duration-300 group-hover:opacity-100">
                    <Maximize2 className="h-3.5 w-3.5" />
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full bg-pug-green-900/55 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-white backdrop-blur">
                    {item.asset.kind === "video" ? (
                      <Play className="h-3 w-3" />
                    ) : (
                      <ImageIcon className="h-3 w-3" />
                    )}
                    {item.asset.kind}
                  </span>
                </span>

                {/* Caption */}
                <span className="absolute inset-x-0 bottom-0 p-3 text-left text-white sm:p-4">
                  {item.category && (
                    <span className="mb-1 inline-flex items-center rounded-full border border-pug-gold-300/50 bg-pug-gold-500/30 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.18em] text-pug-gold-50 backdrop-blur">
                      {CATEGORY_LABELS[item.category]}
                    </span>
                  )}
                  <span className="block text-sm font-semibold leading-snug drop-shadow-sm sm:text-base">
                    {item.title}
                  </span>
                </span>
              </motion.button>
            ))}
          </AnimatePresence>
        </div>
      </GlassAlbumShell>

      {/* Lightbox */}
      <AnimatePresence>
        {lightbox && (
          <>
            <motion.div
              key="bg"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setLightbox(null)}
              className="fixed inset-0 z-50 bg-pug-green-900/85 backdrop-blur-md"
              aria-hidden
            />
            <motion.div
              key="box"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              role="dialog"
              aria-modal="true"
              aria-label={lightbox.title}
              className="fixed inset-4 z-50 flex items-center justify-center sm:inset-12"
            >
              <div className="relative w-full max-w-5xl">
                <div className="aspect-video w-full overflow-hidden rounded-2xl bg-pug-green-900 shadow-[0_30px_80px_-20px_rgba(0,0,0,0.7)] ring-1 ring-white/10">
                  {lightbox.asset.kind === "video" ? (
                    <video
                      src={lightbox.url}
                      controls
                      autoPlay
                      playsInline
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={lightbox.url}
                      alt={lightbox.description ?? lightbox.title}
                      className="h-full w-full object-contain"
                    />
                  )}
                </div>
                <div className="mt-4 flex items-start justify-between gap-3 rounded-2xl border border-white/15 bg-white/[0.06] p-4 backdrop-blur-md">
                  <div className="text-white">
                    {lightbox.category && (
                      <Badge
                        variant="soft"
                        className="border-pug-gold-300/40 bg-pug-gold-500/20 text-pug-gold-100"
                      >
                        {CATEGORY_LABELS[lightbox.category]}
                      </Badge>
                    )}
                    <h3 className="mt-1 text-base font-semibold sm:text-lg">
                      {lightbox.title}
                    </h3>
                    {lightbox.description && (
                      <p className="mt-1 text-sm text-white/80">
                        {lightbox.description}
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setLightbox(null)}
                    className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/10 text-white hover:bg-white/20"
                    aria-label="Close"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}


/**
 * Glass-album shell — a soft frosted panel with a subtle inner glow.
 * Encapsulates the brand background so individual tiles can stay
 * focused on their content.
 */
function GlassAlbumShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative isolate overflow-hidden rounded-3xl border border-white/40 bg-white/40 p-5 shadow-[0_30px_60px_-30px_rgba(15,53,32,0.25)] backdrop-blur-xl sm:p-7 dark:border-white/10 dark:bg-pug-green-900/30">
      {/* Ambient gradient blobs to give the panel depth. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 -left-24 -z-10 h-64 w-64 rounded-full bg-pug-gold-300/30 blur-3xl dark:bg-pug-gold-500/15"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-40 -right-16 -z-10 h-72 w-72 rounded-full bg-pug-green-400/20 blur-3xl dark:bg-pug-green-700/30"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-br from-white/0 via-white/0 to-pug-gold-100/30 dark:to-pug-green-900/40"
      />
      {children}
    </div>
  );
}
