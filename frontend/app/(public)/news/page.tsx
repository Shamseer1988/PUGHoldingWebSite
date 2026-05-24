import { NewsCard } from "@/components/site/news-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getNews, getSiteSettings } from "@/lib/public-api";

export const metadata = { title: "News & Events" };
export const revalidate = 60;

export default async function NewsPage() {
  const [allNews, settings] = await Promise.all([
    getNews(),
    getSiteSettings(),
  ]);
  const featured = allNews.filter((n) => n.is_featured);
  const others = allNews.filter((n) => !n.is_featured);

  return (
    <>
      <PageHero
        eyebrow="News & events"
        title="What's happening at Paris United Group"
        description="Store launches, partnerships, CSR initiatives, and updates from across the group."
        accent="from-pug-gold-500 via-pug-gold-600 to-pug-green-600"
        imageUrl={settings.news_banner_image_url}
        mobileImageUrl={settings.news_banner_mobile_url}
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
