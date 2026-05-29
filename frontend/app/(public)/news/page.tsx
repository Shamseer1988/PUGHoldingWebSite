import { NewsCard } from "@/components/site/news-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getNews, getSitePage } from "@/lib/public-api";

export const metadata = { title: "News & Events" };
// Phase A-1: listing — refresh every 5 min.
export const revalidate = 300;

export default async function NewsPage() {
  const [allNews, page] = await Promise.all([
    getNews(),
    getSitePage("news"),
  ]);
  const featured = allNews.filter((n) => n.is_featured);
  const others = allNews.filter((n) => !n.is_featured);

  return (
    <>
      <PageHero
        eyebrow={page?.hero_eyebrow ?? "News & events"}
        title={page?.hero_title ?? "What's happening at Paris United Group"}
        description={
          page?.hero_description ??
          "Store launches, partnerships, CSR initiatives, and updates from across the group."
        }
        accent="from-pug-gold-500 via-pug-gold-600 to-pug-green-600"
        imageUrl={page?.banner_image_url}
        mobileImageUrl={page?.banner_mobile_url}
        videoUrl={page?.banner_video_url}
      />

      {featured.length > 0 && (
        <Section eyebrow="Featured" title="Top stories">
          <div className="grid grid-cols-1 gap-6">
            {featured.map((item) => (
              <NewsCard key={item.slug} item={item} variant="featured" />
            ))}
          </div>
        </Section>
      )}

      <Section eyebrow="Latest" title="More from the group">
        {others.length === 0 ? (
          <p className="text-muted-foreground">No articles yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {others.map((item) => (
              <NewsCard key={item.slug} item={item} />
            ))}
          </div>
        )}
      </Section>
    </>
  );
}
