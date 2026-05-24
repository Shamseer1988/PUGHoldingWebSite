import { MediaGallery } from "@/components/site/media-gallery";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getMediaGallery } from "@/lib/public-api";

export const metadata = { title: "Media Gallery" };
export const revalidate = 60;

export default async function MediaPage() {
  // Everything on this page comes from /admin/media uploads. Tag an
  // asset with `stores`, `events`, `team`, or `campaigns` to make it
  // appear under the matching tab below.
  const items = await getMediaGallery({ limit: 60 });

  return (
    <>
      <PageHero
        eyebrow="Media"
        title="Stores, events, team, and campaigns"
        description="A glimpse of life at Paris United Group — pick a category or click a tile to view it larger."
        accent="from-rose-500 via-fuchsia-500 to-violet-500"
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
