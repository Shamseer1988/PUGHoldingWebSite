import { NewsCard } from "@/components/site/news-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getFeaturedNews, getNews } from "@/lib/dummy-data/news";

export const metadata = { title: "News & Events" };

export default function NewsPage() {
  const featured = getFeaturedNews();
  const others = getNews().filter(
    (n) => !featured.some((f) => f.slug === n.slug)
  );

  return (
    <>
      <PageHero
        eyebrow="News & events"
        title="What's happening at Paris United Group"
        description="Store launches, partnerships, CSR initiatives, and updates from across the group."
        accent="from-amber-500 via-orange-500 to-rose-500"
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
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {others.map((item) => (
            <NewsCard key={item.slug} item={item} />
          ))}
        </div>
      </Section>
    </>
  );
}
