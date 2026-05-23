import { notFound } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  CalendarDays,
  Facebook,
  Linkedin,
  Mail,
  Share2,
  User,
} from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { NewsCard } from "@/components/site/news-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  NEWS_CATEGORY_LABELS,
  getNews,
  getNewsBySlug,
} from "@/lib/dummy-data/news";
import { cn } from "@/lib/utils";

export function generateStaticParams() {
  return getNews().map((n) => ({ slug: n.slug }));
}

interface NewsDetailPageProps {
  params: { slug: string };
}

export function generateMetadata({ params }: NewsDetailPageProps) {
  const item = getNewsBySlug(params.slug);
  return { title: item ? item.title : "News not found" };
}

export default function NewsDetailPage({ params }: NewsDetailPageProps) {
  const item = getNewsBySlug(params.slug);
  if (!item) notFound();

  const related = getNews()
    .filter((n) => n.slug !== item.slug && n.category === item.category)
    .slice(0, 3);

  return (
    <>
      <PageHero
        eyebrow={NEWS_CATEGORY_LABELS[item.category]}
        title={item.title}
        description={item.summary}
        accent={item.cover}
      >
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <CalendarDays className="h-4 w-4" />
            <time dateTime={item.publishedAt}>
              {new Date(item.publishedAt).toLocaleDateString(undefined, {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
            </time>
          </span>
          <span aria-hidden>·</span>
          <span className="inline-flex items-center gap-1">
            <User className="h-4 w-4" />
            {item.author}
          </span>
        </div>
      </PageHero>

      <Section className="pt-12">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[2fr_1fr]">
          <article className="prose prose-slate dark:prose-invert max-w-none">
            <GlassCard className="overflow-hidden p-0">
              <div
                aria-hidden
                className={cn(
                  "aspect-[16/8] w-full bg-gradient-to-br",
                  item.cover
                )}
              />
              <div className="p-6 sm:p-8">
                <Badge variant="muted">{NEWS_CATEGORY_LABELS[item.category]}</Badge>
                <p className="mt-4 text-base text-foreground/90 sm:text-lg">
                  {item.body}
                </p>

                {item.gallery && item.gallery.length > 0 && (
                  <>
                    <h3 className="mt-8 text-base font-semibold">Gallery</h3>
                    <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                      {item.gallery.map((g, i) => (
                        <span
                          key={i}
                          aria-hidden
                          className={cn(
                            "block aspect-[4/3] rounded-lg bg-gradient-to-br opacity-90",
                            g
                          )}
                        />
                      ))}
                    </div>
                  </>
                )}
              </div>
            </GlassCard>
          </article>

          <aside className="space-y-4">
            <GlassCard className="p-6">
              <h3 className="text-base font-semibold">Share</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Spread the word about this story.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <ShareButton icon={<Linkedin className="h-4 w-4" />} label="LinkedIn" />
                <ShareButton icon={<Facebook className="h-4 w-4" />} label="Facebook" />
                <ShareButton icon={<Mail className="h-4 w-4" />} label="Email" />
                <ShareButton icon={<Share2 className="h-4 w-4" />} label="Copy link" />
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Share targets are wired in Phase 6.
              </p>
            </GlassCard>

            <GlassCard className="p-6">
              <h3 className="text-base font-semibold">All news</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Browse every update from Paris United Group.
              </p>
              <Button asChild variant="outline" className="mt-5 w-full">
                <Link href="/news">
                  <ArrowLeft className="h-4 w-4" />
                  Back to news
                </Link>
              </Button>
            </GlassCard>
          </aside>
        </div>
      </Section>

      {related.length > 0 && (
        <Section eyebrow="Related stories" title="More like this">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {related.map((r) => (
              <NewsCard key={r.slug} item={r} />
            ))}
          </div>
        </Section>
      )}
    </>
  );
}

function ShareButton({
  icon,
  label,
}: {
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      className="inline-flex items-center gap-2 rounded-md border border-border/60 bg-background/40 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
    >
      {icon}
      {label}
    </button>
  );
}
