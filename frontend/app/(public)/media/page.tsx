import { Image as ImageIcon, Video } from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { MediaGallery } from "@/components/site/media-gallery";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getMedia } from "@/lib/dummy-data/media";
import { getMediaGallery, resolveAssetUrl } from "@/lib/public-api";

export const metadata = { title: "Media Gallery" };
export const revalidate = 60;

export default async function MediaPage() {
  const [uploads, items] = await Promise.all([
    getMediaGallery({ limit: 60 }),
    Promise.resolve(getMedia()),
  ]);

  return (
    <>
      <PageHero
        eyebrow="Media"
        title="Stores, events, team, and campaigns"
        description="A glimpse of life at Paris United Group — pick a category or click a tile to view it larger."
        accent="from-rose-500 via-fuchsia-500 to-violet-500"
      />

      {uploads.length > 0 && (
        <Section
          eyebrow="From the CMS"
          title="Recent uploads"
          description="Latest images and videos shared by our team."
        >
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {uploads.map((asset) => {
              const url = resolveAssetUrl(asset.url) ?? asset.url;
              return (
                <GlassCard
                  key={asset.id}
                  className="group overflow-hidden p-0"
                >
                  <div className="relative aspect-video w-full overflow-hidden bg-muted">
                    {asset.kind === "video" ? (
                      <video
                        src={url}
                        controls
                        preload="metadata"
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={url}
                        alt={asset.alt_text ?? asset.title ?? "Media asset"}
                        loading="lazy"
                        className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                      />
                    )}
                    <span className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-full border border-white/30 bg-black/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white backdrop-blur">
                      {asset.kind === "video" ? (
                        <Video className="h-3 w-3" />
                      ) : (
                        <ImageIcon className="h-3 w-3" />
                      )}
                      {asset.kind}
                    </span>
                  </div>
                  {(asset.title || asset.tags) && (
                    <div className="space-y-1 p-3">
                      {asset.title && (
                        <p className="truncate text-sm font-medium">
                          {asset.title}
                        </p>
                      )}
                      {asset.tags && (
                        <p className="flex flex-wrap gap-1 text-[10px] text-muted-foreground">
                          {asset.tags
                            .split(",")
                            .map((t) => t.trim())
                            .filter(Boolean)
                            .slice(0, 3)
                            .map((tag) => (
                              <span
                                key={tag}
                                className="rounded-full bg-muted px-1.5 py-0.5 font-medium uppercase tracking-wider"
                              >
                                {tag}
                              </span>
                            ))}
                        </p>
                      )}
                    </div>
                  )}
                </GlassCard>
              );
            })}
          </div>
        </Section>
      )}

      <Section
        eyebrow="Featured stories"
        title="Around the group"
        description="A curated peek at the stores, events, team moments, and campaigns we've highlighted."
        className="pt-10"
      >
        <MediaGallery items={items} />
      </Section>
    </>
  );
}
