import Link from "next/link";
import { ArrowUpRight, CalendarDays } from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { Badge } from "@/components/ui/badge";
import type { NewsItem } from "@/lib/admin/types";
import { normaliseMediaUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";

const NEWS_CATEGORY_LABELS: Record<NewsItem["category"], string> = {
  company: "Company",
  event: "Event",
  press: "Press",
  csr: "CSR",
};

interface NewsCardProps {
  item: NewsItem;
  variant?: "default" | "featured";
}

export function NewsCard({ item, variant = "default" }: NewsCardProps) {
  const featured = variant === "featured";
  const coverImage = normaliseMediaUrl(item.cover_image_url);
  return (
    <Link href={`/news/${item.slug}`} className="group block h-full">
      <GlassCard
        className={cn(
          "flex h-full flex-col overflow-hidden p-0",
          featured && "lg:flex-row"
        )}
      >
        <div
          aria-hidden
          className={cn(
            "relative w-full overflow-hidden",
            !coverImage && "bg-gradient-to-br",
            !coverImage && item.cover,
            featured ? "aspect-[16/9] lg:aspect-auto lg:w-1/2" : "aspect-[16/9]"
          )}
        >
          {coverImage && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={coverImage}
              alt=""
              loading="lazy"
              className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
            />
          )}
          <span className="absolute inset-0 bg-gradient-to-t from-black/50 via-black/10 to-transparent" />
          <span className="absolute left-3 top-3">
            <Badge variant="default" className="bg-white/90 text-foreground">
              {NEWS_CATEGORY_LABELS[item.category]}
            </Badge>
          </span>
        </div>

        <div
          className={cn(
            "flex flex-1 flex-col p-5",
            featured && "lg:p-7"
          )}
        >
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <CalendarDays className="h-3.5 w-3.5" />
            <time dateTime={item.published_at}>
              {formatDate(item.published_at)}
            </time>
            {item.author && (
              <>
                <span aria-hidden>·</span>
                <span>{item.author}</span>
              </>
            )}
          </div>
          <h3
            className={cn(
              "mt-2 text-balance text-lg font-semibold leading-snug tracking-tight group-hover:text-primary",
              featured && "lg:text-2xl"
            )}
          >
            {item.title}
          </h3>
          {item.summary && (
            <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">
              {item.summary}
            </p>
          )}
          <span className="mt-auto inline-flex items-center gap-1 pt-4 text-sm font-medium text-primary">
            Read more
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </span>
        </div>
      </GlassCard>
    </Link>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export { NEWS_CATEGORY_LABELS };
