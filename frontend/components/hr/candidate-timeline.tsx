"use client";

import * as React from "react";
import {
  Briefcase,
  CalendarClock,
  FileEdit,
  Handshake,
  Inbox,
  Loader2,
  MoveRight,
  ShieldAlert,
} from "lucide-react";

import { hrApi, HrApiError } from "@/lib/hr/api";
import type { CandidateTimelineEvent } from "@/lib/hr/types";
import { cn } from "@/lib/utils";


interface Props {
  candidateId: number;
  refreshKey?: number | string;
}


/**
 * Unified per-candidate timeline showing recruitment + interview +
 * offer events in one chronological feed (newest first). Backed by
 * GET /hr/candidates/{id}/timeline (Phase 3 endpoint).
 *
 * Streams are tone-coded so HR can scan the feed quickly:
 *   recruitment → primary (blue/green)
 *   interview   → info     (indigo)
 *   offer       → success  (emerald)
 *   system      → muted    (neutral grey)
 */
export function CandidateTimeline({ candidateId, refreshKey }: Props) {
  const [events, setEvents] = React.useState<CandidateTimelineEvent[] | null>(
    null
  );
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setEvents(null);
    setError(null);
    hrApi
      .get<CandidateTimelineEvent[]>(`/hr/candidates/${candidateId}/timeline`)
      .then((rows) => {
        if (!cancelled) setEvents(rows);
      })
      .catch((err) => {
        if (!cancelled) setError((err as HrApiError).message);
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId, refreshKey]);

  if (error) {
    return (
      <p
        role="alert"
        className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300"
      >
        <ShieldAlert className="mr-1 inline h-3.5 w-3.5" />
        {error}
      </p>
    );
  }

  if (events === null) {
    return (
      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading timeline…
      </p>
    );
  }

  if (events.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border/60 bg-card px-3 py-4 text-center text-xs text-muted-foreground">
        No events yet — the timeline fills in as HR moves the candidate through
        the pipeline.
      </p>
    );
  }

  return (
    <ol className="space-y-3" aria-label="Candidate timeline">
      {events.map((evt, idx) => (
        <TimelineRow key={`${evt.stream}-${evt.action}-${evt.ref_id}-${idx}`} evt={evt} />
      ))}
    </ol>
  );
}


// ---------------------------------------------------------------------------
// Row rendering
// ---------------------------------------------------------------------------


const STREAM_META: Record<
  string,
  { Icon: React.ComponentType<{ className?: string }>; tone: string; label: string }
> = {
  recruitment: {
    Icon: Briefcase,
    tone:
      "border-primary/30 bg-primary/10 text-primary",
    label: "Recruitment",
  },
  interview: {
    Icon: CalendarClock,
    tone:
      "border-indigo-500/30 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300",
    label: "Interview",
  },
  offer: {
    Icon: Handshake,
    tone:
      "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    label: "Offer",
  },
  system: {
    Icon: FileEdit,
    tone: "border-border/60 bg-muted/50 text-muted-foreground",
    label: "System",
  },
};


function TimelineRow({ evt }: { evt: CandidateTimelineEvent }) {
  const meta = STREAM_META[evt.stream] ?? STREAM_META.system;
  const Icon = meta.Icon;
  return (
    <li className="flex gap-3">
      <span
        className={cn(
          "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border",
          meta.tone
        )}
        aria-hidden
      >
        <Icon className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0 flex-1 rounded-md border border-border/60 bg-card px-3 py-2 text-xs">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="font-medium">{evt.title}</p>
          <p className="text-[11px] text-muted-foreground">
            {new Date(evt.occurred_at).toLocaleString()}
          </p>
        </div>
        <p className="mt-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
          {meta.label}
          {evt.actor_email ? ` · ${evt.actor_email}` : ""}
        </p>
        {(evt.old_status || evt.new_status) && (
          <p className="mt-1 inline-flex items-center gap-1 text-[11px] text-muted-foreground">
            {evt.old_status ?? "—"}
            <MoveRight className="h-3 w-3" />
            <span className="font-medium text-foreground/90">
              {evt.new_status ?? "—"}
            </span>
          </p>
        )}
        {evt.description && (
          <p className="mt-1 whitespace-pre-wrap rounded bg-muted/40 px-2 py-1 text-[11px] text-foreground/90">
            {evt.description}
          </p>
        )}
      </div>
    </li>
  );
}


/**
 * Empty-state placeholder for surfaces that haven't yet plumbed in the
 * full timeline — kept here so multiple HR pages share one look.
 */
export function CandidateTimelineEmpty() {
  return (
    <div className="flex items-center gap-2 rounded-md border border-dashed border-border/60 bg-card p-3 text-xs text-muted-foreground">
      <Inbox className="h-3.5 w-3.5" />
      No timeline events yet.
    </div>
  );
}
