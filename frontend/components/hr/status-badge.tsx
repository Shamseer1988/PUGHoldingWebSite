"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Unified HR status badge — the single source of truth for status
 * presentation anywhere under ``/hr/*``.
 *
 * The recruitment console renders four independent status streams:
 *
 *   - ``application`` — the candidate pipeline state machine
 *     (cv_received → … → joined | not_joined, plus the waiting_list /
 *     rejected / blacklisted side lanes). Mirrors
 *     ``app.services.candidate_workflow.PIPELINE_ORDER``.
 *   - ``offer``       — the offer lifecycle (draft → … → joined).
 *   - ``interview``   — interview round state.
 *   - ``job``         — job-opening lifecycle.
 *
 * Every stream previously defined its own colour map + label dictionary
 * in-place (``StatusChip`` in the candidates table, ``HrStatusBadge``,
 * ad-hoc spans). This component replaces all of them so HR sees one
 * consistent palette across Dashboard, Pipeline, Candidates, Offers,
 * Onboarding and Reports.
 *
 * Usage:
 *   <StatusBadge kind="application" status="shortlisted" />
 *   <StatusBadge kind="offer" status="pending_approval" />
 *
 * Pass an explicit ``label`` to override the canonical label (e.g. when
 * the API already returns a localised / server-computed string).
 */

export type StatusKind = "application" | "offer" | "interview" | "job";

export type StatusTone =
  | "neutral"
  | "info"
  | "progress"
  | "ready"
  | "success"
  | "warning"
  | "danger";

/** One taxonomy entry — the human label, a semantic tone, and the
 *  resolved Tailwind class string so consumers (and the docs) can read
 *  "label + tailwind class per (kind, status) pair" directly. */
export interface StatusTaxonomyEntry {
  label: string;
  tone: StatusTone;
  className: string;
}

// ---------------------------------------------------------------------------
// Tone → Tailwind. The tones express the funnel as a colour journey:
// neutral (inbound) → info (screening) → progress (interviewing, indigo)
// → ready (decision pending, violet) → success (won, emerald). amber
// flags "needs attention", rose flags "lost".
// ---------------------------------------------------------------------------

const TONE_CLASSES: Record<StatusTone, string> = {
  neutral: "border-border/60 bg-muted/50 text-muted-foreground",
  info: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300",
  progress:
    "border-indigo-500/30 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300",
  ready: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
  success:
    "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  warning:
    "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  danger: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
};

type RawSpec = { label: string; tone: StatusTone };

// Application pipeline — declared in PIPELINE_ORDER so
// ``statusesForKind("application")`` yields the funnel in order (used by
// the Candidates filter chips and the Pipeline lanes).
const APPLICATION: Record<string, RawSpec> = {
  cv_received: { label: "CV received", tone: "neutral" },
  ai_reviewed: { label: "AI reviewed", tone: "info" },
  hr_review_pending: { label: "HR review pending", tone: "warning" },
  shortlisted: { label: "Shortlisted", tone: "info" },
  first_interview: { label: "First interview", tone: "progress" },
  technical_interview: { label: "Technical interview", tone: "progress" },
  final_interview: { label: "Final interview", tone: "progress" },
  waiting_list: { label: "Waiting list", tone: "warning" },
  recommended_for_offer: { label: "Recommended for offer", tone: "ready" },
  selected: { label: "Selected", tone: "ready" },
  offer_sent: { label: "Offer sent", tone: "info" },
  joined: { label: "Joined", tone: "success" },
  not_joined: { label: "Not joined", tone: "danger" },
  rejected: { label: "Rejected", tone: "danger" },
  blacklisted: { label: "Blacklisted", tone: "danger" },
};

const OFFER: Record<string, RawSpec> = {
  draft: { label: "Draft", tone: "neutral" },
  pending_approval: { label: "Pending approval", tone: "warning" },
  approved: { label: "Approved", tone: "info" },
  sent: { label: "Issued", tone: "info" },
  accepted: { label: "Accepted", tone: "success" },
  declined: { label: "Declined", tone: "danger" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
  joined: { label: "Joined", tone: "success" },
  not_joined: { label: "Not joined", tone: "danger" },
};

const INTERVIEW: Record<string, RawSpec> = {
  scheduled: { label: "Scheduled", tone: "info" },
  completed: { label: "Completed", tone: "success" },
  cancelled: { label: "Cancelled", tone: "danger" },
  rescheduled: { label: "Rescheduled", tone: "warning" },
  no_show: { label: "No-show", tone: "warning" },
};

const JOB: Record<string, RawSpec> = {
  open: { label: "Open", tone: "success" },
  on_hold: { label: "On hold", tone: "warning" },
  closed: { label: "Closed", tone: "neutral" },
};

function resolve(map: Record<string, RawSpec>): Record<string, StatusTaxonomyEntry> {
  return Object.fromEntries(
    Object.entries(map).map(([key, spec]) => [
      key,
      { ...spec, className: TONE_CLASSES[spec.tone] },
    ]),
  );
}

/**
 * The canonical taxonomy: ``STATUS_TAXONOMY[kind][status]`` →
 * ``{ label, tone, className }``. Exported so non-badge consumers
 * (tooltips, lane headers, the architecture doc) share one table.
 */
export const STATUS_TAXONOMY: Record<
  StatusKind,
  Record<string, StatusTaxonomyEntry>
> = {
  application: resolve(APPLICATION),
  offer: resolve(OFFER),
  interview: resolve(INTERVIEW),
  job: resolve(JOB),
};

const NEUTRAL_FALLBACK: StatusTaxonomyEntry = {
  label: "—",
  tone: "neutral",
  className: TONE_CLASSES.neutral,
};

/** Ordered status keys for a kind — drives filter chips + kanban lanes. */
export function statusesForKind(kind: StatusKind): string[] {
  return Object.keys(STATUS_TAXONOMY[kind]);
}

/** Look up the canonical label without rendering. */
export function statusLabel(kind: StatusKind, status: string): string {
  return STATUS_TAXONOMY[kind][status]?.label ?? status;
}

/** Look up the full taxonomy entry (label + tone + className). */
export function statusEntry(
  kind: StatusKind,
  status: string,
): StatusTaxonomyEntry {
  return STATUS_TAXONOMY[kind][status] ?? { ...NEUTRAL_FALLBACK, label: status };
}

interface StatusBadgeProps {
  kind: StatusKind;
  status: string | null | undefined;
  /** Override the canonical label (e.g. a server-computed string). */
  label?: string | null;
  className?: string;
}

export function StatusBadge({ kind, status, label, className }: StatusBadgeProps) {
  if (!status) {
    return (
      <span className={cn("text-xs text-muted-foreground", className)}>—</span>
    );
  }
  const entry = STATUS_TAXONOMY[kind][status] ?? {
    ...NEUTRAL_FALLBACK,
    label: status,
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        entry.className,
        className,
      )}
    >
      {label ?? entry.label}
    </span>
  );
}
