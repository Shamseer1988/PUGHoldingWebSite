import { MediaGallery } from "@/components/site/media-gallery";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getMedia } from "@/lib/dummy-data/media";

export const metadata = { title: "Media Gallery" };

export default function MediaPage() {
  const items = getMedia();

  return (
    <>
      <PageHero
        eyebrow="Media"
        title="Stores, events, team, and campaigns"
        description="A glimpse of life at Paris United Group — pick a category or click a tile to view it larger."
        accent="from-rose-500 via-fuchsia-500 to-violet-500"
      />

      <Section className="pt-10">
        <MediaGallery items={items} />
      </Section>
    </>
  );
}
