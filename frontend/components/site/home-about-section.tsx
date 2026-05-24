import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { Section } from "@/components/site/section";
import { Button } from "@/components/ui/button";
import { resolveAssetUrl } from "@/lib/public-api";

interface HomeAboutSectionProps {
  imageUrl: string | null;
  title: string | null;
  body: string | null;
}

export function HomeAboutSection({
  imageUrl,
  title,
  body,
}: HomeAboutSectionProps) {
  if (!title && !body && !imageUrl) return null;
  const image = resolveAssetUrl(imageUrl);

  return (
    <Section className="py-16 sm:py-20">
      <div className="grid items-center gap-10 lg:grid-cols-[1.1fr_1fr]">
        <div className="relative">
          {image ? (
            <GlassCard className="relative overflow-hidden p-0">
              <div className="relative aspect-[4/3] w-full overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={image}
                  alt={title ?? "About Paris United Group"}
                  loading="lazy"
                  className="absolute inset-0 h-full w-full object-cover"
                />
              </div>
            </GlassCard>
          ) : (
            <GlassCard className="aspect-[4/3] w-full bg-gradient-to-br from-pug-green-500/40 via-pug-gold-500/30 to-pug-green-700/30" />
          )}
          <div
            aria-hidden
            className="pointer-events-none absolute -bottom-6 -right-6 h-32 w-32 rounded-full bg-pug-gold-500/20 blur-3xl"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute -left-6 -top-6 h-32 w-32 rounded-full bg-pug-green-600/20 blur-3xl"
          />
        </div>

        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            About the group
          </span>
          {title && (
            <h2 className="mt-4 text-balance text-2xl font-semibold tracking-tight sm:text-3xl lg:text-4xl">
              {title}
            </h2>
          )}
          {body && (
            <p className="mt-4 whitespace-pre-line text-pretty text-muted-foreground sm:text-lg">
              {body}
            </p>
          )}
          <div className="mt-6">
            <Button asChild variant="outline">
              <Link href="/about">
                Read our story
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </Section>
  );
}
