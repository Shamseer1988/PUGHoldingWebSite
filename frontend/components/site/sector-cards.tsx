import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { RevealGroup } from "@/components/site/reveal";
import { SECTORS } from "@/lib/dummy-data/site-content";
import { cn } from "@/lib/utils";

/**
 * Three "Our business sectors" cards.
 *
 * Cards stagger-fade in as the row enters the viewport (driven by
 * `RevealGroup`) and lift on hover with a soft scale + shadow swap.
 * The accent glow rotates subtly under the cursor for a modern,
 * tactile feel without depending on JS.
 */
export function SectorCards() {
  return (
    <RevealGroup
      className="grid grid-cols-1 gap-6 md:grid-cols-3"
      stagger={0.12}
      direction="up"
      distance={32}
    >
      {SECTORS.map((sector) => {
        const Icon = sector.icon;
        return (
          <Link key={sector.id} href={sector.href} className="group block h-full">
            <GlassCard className="relative h-full overflow-hidden p-6 transition-all duration-300 ease-out group-hover:-translate-y-1.5 group-hover:shadow-xl group-hover:shadow-primary/10">
              <div
                aria-hidden
                className={cn(
                  "pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full opacity-50 blur-2xl transition-all duration-500 group-hover:scale-125 group-hover:opacity-80",
                  "bg-gradient-to-br",
                  sector.accent
                )}
              />
              <div
                className={cn(
                  "inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-md transition-transform duration-300 group-hover:scale-110 group-hover:rotate-3",
                  sector.accent
                )}
              >
                <Icon className="h-6 w-6" />
              </div>
              <h3 className="mt-4 text-xl font-semibold tracking-tight">
                {sector.title}
              </h3>
              <p className="mt-2 text-sm text-muted-foreground">
                {sector.description}
              </p>
              <span className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-primary">
                Explore {sector.title.toLowerCase()}
                <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
              </span>
            </GlassCard>
          </Link>
        );
      })}
    </RevealGroup>
  );
}
