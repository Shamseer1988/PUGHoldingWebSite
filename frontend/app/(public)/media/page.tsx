import { MediaGallery } from "@/components/site/media-gallery";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getMediaGallery, getSitePage } from "@/lib/public-api";

export const metadata = { title: "Media Gallery" };
// Phase A-1: listing — refresh every 5 min.
export const revalidate = 300;

export default async function MediaPage() {
  // Everything on this page comes from /admin/media uploads. Tag an
  // asset with `stores`, `events`, `team`, or `campaigns` to make it
  // appear under the matching tab below.
  const [items, page] = await Promise.all([
    getMediaGallery({ limit: 60 }),
    getSitePage("media"),
  ]);

  return (
    <>
      <PageHero
        eyebrow={page?.hero_eyebrow ?? "Media"}
        title={page?.hero_title ?? "Stores, events, team, and campaigns"}
        description={
          page?.hero_description ??
          "A glimpse of life at Paris United Group — pick a category or click a tile to view it larger."
        }
        accent="from-pug-green-800 via-pug-green-600 to-pug-gold-500"
        imageUrl={page?.banner_image_url}
        mobileImageUrl={page?.banner_mobile_url}
        videoUrl={page?.banner_video_url}
      />

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
