import Link from "next/link";
import { ArrowLeft, Hourglass } from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { Section } from "@/components/site/section";
import { Button } from "@/components/ui/button";

interface ComingSoonProps {
  title: string;
  description: string;
  phaseLabel: string;
  features?: string[];
}

export function ComingSoon({
  title,
  description,
  phaseLabel,
  features,
}: ComingSoonProps) {
  return (
    <Section className="relative">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
      >
        <div className="absolute -left-32 top-[-10%] h-72 w-72 rounded-full bg-primary/20 blur-3xl" />
        <div className="absolute right-[-10%] bottom-[-10%] h-80 w-80 rounded-full bg-fuchsia-500/15 blur-3xl" />
      </div>

      <GlassCard className="mx-auto max-w-2xl p-8 sm:p-10">
        <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/60 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
          <Hourglass className="h-3.5 w-3.5 text-primary" />
          {phaseLabel}
        </div>
        <h1 className="mt-4 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
          {title}
        </h1>
        <p className="mt-3 text-pretty text-base text-muted-foreground">
          {description}
        </p>

        {features && features.length > 0 && (
          <ul className="mt-6 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
            {features.map((feature) => (
              <li
                key={feature}
                className="rounded-md border border-border/60 bg-background/40 px-3 py-2"
              >
                {feature}
              </li>
            ))}
          </ul>
        )}

        <div className="mt-8">
          <Button asChild variant="outline">
            <Link href="/">
              <ArrowLeft className="h-4 w-4" />
              Back to home
            </Link>
          </Button>
        </div>
      </GlassCard>
    </Section>
  );
}
