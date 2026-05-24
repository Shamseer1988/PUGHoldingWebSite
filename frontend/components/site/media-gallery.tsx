"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ImageIcon, Play, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  resolveAssetUrl,
  type PublicMediaAsset,
} from "@/lib/public-api";
import { cn } from "@/lib/utils";


/**
 * Public-side gallery powered by the admin Media Gallery.
 *
 * Categories ("stores", "events", "team", "campaigns") are derived
 * from the asset's `tags` field. Tags can be added when editing the
 * asset under /admin/media. Assets without one of those tags are
 * still shown under "All".
 *
 * Renders real images / videos — no more placeholder gradients — and
 * opens each tile in a lightbox on click.
 */

export type MediaCategory = "stores" | "events" | "team" | "campaigns";
const CATEGORIES: MediaCategory[] = ["stores", "events", "team", "campaigns"];
const CATEGORY_LABELS: Record<MediaCategory, string> = {
  stores: "Stores",
  events: "Events",
  team: "Team",
  campaigns: "Campaigns",
};

interface MediaGalleryProps {
  items: PublicMediaAsset[];
}

interface DerivedItem {
  asset: PublicMediaAsset;
  /** Resolved URL (handles relative API paths). */
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

  const availableCategories = React.useMemo<
    ("all" | MediaCategory)[]
  >(() => {
    const set = new Set<MediaCategory>();
    for (const item of derived) {
      if (item.category) set.add(item.category);
    }
    return ["all", ...CATEGORIES.filter((c) => set.has(c))];
  }, [derived]);

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
      <div className="rounded-2xl border border-dashed border-border/60 bg-background/50 p-10 text-center text-sm text-muted-foreground">
        <ImageIcon className="mx-auto mb-3 h-8 w-8 opacity-50" />
        <p>No media uploaded yet.</p>
        <p className="mt-1 text-xs">
          Upload images or videos in <em>Admin → Media gallery</em> and tag
          them <code className="rounded bg-muted px-1">stores</code>,{" "}
          <code className="rounded bg-muted px-1">events</code>,{" "}
          <code className="rounded bg-muted px-1">team</code>, or{" "}
          <code className="rounded bg-muted px-1">campaigns</code> so they
          appear here under the matching tab.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {availableCategories.length > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          {availableCategories.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setActive(cat)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                active === cat
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border/60 bg-background/60 text-muted-foreground hover:text-foreground"
              )}
              aria-pressed={active === cat}
            >
              {cat === "all" ? "All" : CATEGORY_LABELS[cat]}
            </button>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {filtered.map((item) => (
          <button
            key={item.asset.id}
            type="button"
            onClick={() => setLightbox(item)}
            className="group relative aspect-[4/3] overflow-hidden rounded-xl border border-border/60 bg-muted shadow-sm transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            aria-label={`Open ${item.title}`}
          >
            {item.asset.kind === "video" ? (
              <video
                src={item.url}
                muted
                playsInline
                preload="metadata"
                className="h-full w-full object-cover"
              />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={item.url}
                alt={item.description ?? item.title}
                loading="lazy"
                decoding="async"
                className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
              />
            )}
            <span
              aria-hidden
              className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/65 via-black/0 to-black/0"
            />
            <span className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-full bg-black/55 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-white backdrop-blur">
              {item.asset.kind === "video" ? (
                <Play className="h-3 w-3" />
              ) : (
                <ImageIcon className="h-3 w-3" />
              )}
              {item.asset.kind}
            </span>
            <span className="absolute inset-x-0 bottom-0 p-3 text-left text-white">
              {item.category && (
                <span className="block text-[10px] font-medium uppercase tracking-wider opacity-80">
                  {CATEGORY_LABELS[item.category]}
                </span>
              )}
              <span className="block text-sm font-semibold leading-snug">
                {item.title}
              </span>
            </span>
          </button>
        ))}
      </div>

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
              className="fixed inset-0 z-50 bg-background/80 backdrop-blur-md"
              aria-hidden
            />
            <motion.div
              key="box"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ duration: 0.25 }}
              role="dialog"
              aria-modal="true"
              aria-label={lightbox.title}
              className="fixed inset-4 z-50 flex items-center justify-center sm:inset-12"
            >
              <div className="relative w-full max-w-4xl">
                <div className="aspect-video w-full overflow-hidden rounded-2xl bg-black shadow-2xl">
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
                <div className="mt-4 flex items-start justify-between gap-3 rounded-xl border border-border/60 bg-background/85 p-4 backdrop-blur">
                  <div>
                    {lightbox.category && (
                      <Badge variant="soft">
                        {CATEGORY_LABELS[lightbox.category]}
                      </Badge>
                    )}
                    <h3 className="mt-1 text-base font-semibold">
                      {lightbox.title}
                    </h3>
                    {lightbox.description && (
                      <p className="mt-1 text-sm text-muted-foreground">
                        {lightbox.description}
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setLightbox(null)}
                    className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border/60 bg-background hover:bg-muted"
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
    </div>
  );
}
