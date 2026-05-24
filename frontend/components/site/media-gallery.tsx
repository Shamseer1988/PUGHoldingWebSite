"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Maximize2, Play, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  MEDIA_CATEGORY_LABELS,
  type MediaCategory,
  type MediaItem,
} from "@/lib/dummy-data/media";
import { cn } from "@/lib/utils";

interface MediaGalleryProps {
  items: MediaItem[];
}

export function MediaGallery({ items }: MediaGalleryProps) {
  const categories = React.useMemo<("all" | MediaCategory)[]>(() => {
    const set = new Set<MediaCategory>(items.map((i) => i.category));
    return ["all", ...Array.from(set)];
  }, [items]);

  const [active, setActive] = React.useState<"all" | MediaCategory>("all");
  const [lightbox, setLightbox] = React.useState<MediaItem | null>(null);

  const filtered = React.useMemo(
    () => (active === "all" ? items : items.filter((i) => i.category === active)),
    [items, active]
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

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        {categories.map((cat) => (
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
            {cat === "all" ? "All" : MEDIA_CATEGORY_LABELS[cat]}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {filtered.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setLightbox(item)}
            className={cn(
              "group relative overflow-hidden rounded-xl border border-border/60 bg-gradient-to-br shadow-sm transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              item.aspect,
              item.accent
            )}
            aria-label={`Open ${item.title}`}
          >
            <span className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/0 to-black/20" />
            <span className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-full bg-black/40 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-white backdrop-blur">
              {item.kind === "video" ? <Play className="h-3 w-3" /> : null}
              {item.kind}
            </span>
            <span className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-2 p-3 text-left text-white">
              <span>
                <span className="block text-xs font-medium opacity-80">
                  {MEDIA_CATEGORY_LABELS[item.category]}
                </span>
                <span className="block text-sm font-semibold leading-snug">
                  {item.title}
                </span>
              </span>
              <Maximize2 className="h-4 w-4 opacity-0 transition-opacity group-hover:opacity-100" />
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
                <div
                  className={cn(
                    "aspect-video w-full overflow-hidden rounded-2xl bg-gradient-to-br shadow-2xl",
                    lightbox.accent
                  )}
                  aria-hidden
                >
                  <span className="flex h-full w-full items-center justify-center text-3xl font-semibold text-white/90">
                    {lightbox.kind === "video" ? (
                      <Play className="h-12 w-12 opacity-80" />
                    ) : (
                      MEDIA_CATEGORY_LABELS[lightbox.category]
                    )}
                  </span>
                </div>
                <div className="mt-4 flex items-start justify-between gap-3 rounded-xl border border-border/60 bg-background/85 p-4 backdrop-blur">
                  <div>
                    <Badge variant="soft">
                      {MEDIA_CATEGORY_LABELS[lightbox.category]}
                    </Badge>
                    <h3 className="mt-1 text-base font-semibold">
                      {lightbox.title}
                    </h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {lightbox.description}
                    </p>
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
