import { Quote } from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { Section } from "@/components/site/section";
import { resolveAssetUrl } from "@/lib/public-api";

interface HomeFounderMessageProps {
  imageUrl: string | null;
  name: string | null;
  role: string | null;
  message: string | null;
}

export function HomeFounderMessage({
  imageUrl,
  name,
  role,
  message,
}: HomeFounderMessageProps) {
  if (!message && !name) return null;
  const image = resolveAssetUrl(imageUrl);

  return (
    <Section className="py-16 sm:py-20">
      <GlassCard className="relative overflow-hidden p-0">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 top-1/2 hidden h-72 w-72 -translate-y-1/2 rounded-full bg-pug-gold-500/15 blur-3xl lg:block"
        />
        <div className="grid items-stretch gap-0 lg:grid-cols-[1fr_1.4fr]">
          <div className="relative min-h-[280px] overflow-hidden bg-gradient-to-br from-pug-green-700/30 via-pug-gold-500/20 to-pug-green-500/20 lg:min-h-full">
            {image ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={image}
                alt={name ?? "Founder"}
                loading="lazy"
                className="absolute inset-0 h-full w-full object-cover"
              />
            ) : (
              <div
                aria-hidden
                className="absolute inset-0 flex items-center justify-center text-6xl font-bold text-white/40"
              >
                {(name ?? "PUG").slice(0, 1)}
              </div>
            )}
          </div>

          <div className="flex flex-col justify-center gap-5 p-8 sm:p-10 lg:p-12">
            <span className="inline-flex w-fit items-center rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground backdrop-blur">
              Founder's note
            </span>
            {message && (
              <div className="relative pl-7 text-pretty text-base text-foreground/90 sm:text-lg">
                <Quote
                  aria-hidden
                  className="absolute left-0 top-1 h-5 w-5 text-primary"
                />
                <p className="whitespace-pre-line">{message}</p>
              </div>
            )}
            <div className="mt-2 border-t border-border/60 pt-4">
              {name && (
                <p className="font-semibold tracking-tight">{name}</p>
              )}
              {role && (
                <p className="text-sm text-muted-foreground">{role}</p>
              )}
            </div>
          </div>
        </div>
      </GlassCard>
    </Section>
  );
}
