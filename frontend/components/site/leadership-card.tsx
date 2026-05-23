import { Quote } from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { type LeadershipMessage } from "@/lib/dummy-data/leadership";
import { cn } from "@/lib/utils";

interface LeadershipCardProps {
  leader: LeadershipMessage;
  /** Render the full long-form message instead of the short preview. */
  full?: boolean;
}

export function LeadershipCard({ leader, full = false }: LeadershipCardProps) {
  return (
    <GlassCard className="flex h-full flex-col gap-5 p-6">
      <div className="flex items-center gap-4">
        <Portrait accent={leader.accent} initials={leader.initials} />
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold sm:text-lg">
            {leader.name}
          </h3>
          <p className="truncate text-sm text-muted-foreground">{leader.role}</p>
        </div>
      </div>

      <div className="relative pl-6 text-sm text-foreground/90">
        <Quote
          aria-hidden
          className="absolute left-0 top-0 h-4 w-4 text-primary"
        />
        {full ? leader.fullMessage : leader.shortMessage}
      </div>

      {leader.signature && (
        <p className="font-signature mt-auto text-sm italic text-muted-foreground">
          — {leader.signature}
        </p>
      )}
    </GlassCard>
  );
}

function Portrait({
  accent,
  initials,
}: {
  accent: string;
  initials: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gradient-to-br text-base font-bold tracking-wide text-white shadow-md ring-2 ring-background",
        accent
      )}
      aria-hidden
    >
      {initials}
    </span>
  );
}
