"use client";

import * as React from "react";

import { cn } from "@/lib/utils";


/**
 * Unified HR status badge (Phase 10).
 *
 * The HR module ships with five status streams that previously each
 * defined their own colour map + label dictionary in-place — job
 * lifecycle, job approval, candidate pipeline, interview state, offer
 * state. This component is the single source of truth for status
 * presentation so HR sees consistent colours across every screen.
 *
 * Usage:
 *   <HrStatusBadge kind="candidate" value="shortlisted" />
 *   <HrStatusBadge kind="offer" value="pending_approval" />
 *
 * Pass an explicit ``label`` to override the canonical label
 * (e.g. when the API returns a translated string).
 */


export type HrStatusKind =
  | "job"
  | "approval"
  | "publish"
  | "candidate"
  | "interview"
  | "offer";


type Tone = "neutral" | "info" | "success" | "warning" | "danger";


interface BadgeSpec {
  label: string;
  tone: Tone;
}


// ---------------------------------------------------------------------------
// Canonical label + tone tables — one block per stream so the audit
// trail is easy to scan.
// ---------------------------------------------------------------------------


const JOB: Record<string, BadgeSpec> = {
  open: { label: "Open", tone: "success" },
  on_hold: { label: "On hold", tone: "warning" },
  closed: { label: "Closed", tone: "neutral" },
};

const APPROVAL: Record<string, BadgeSpec> = {
  draft: { label: "Draft", tone: "neutral" },
  pending_approval: { label: "Pending approval", tone: "warning" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Rejected", tone: "danger" },
  revision_required: { label: "Revision required", tone: "warning" },
};

const PUBLISH: Record<string, BadgeSpec> = {
  draft: { label: "Draft", tone: "neutral" },
  published: { label: "Live", tone: "success" },
  unpublished: { label: "Unpublished", tone: "neutral" },
};

const CANDIDATE: Record<string, BadgeSpec> = {
  cv_received: { label: "CV received", tone: "info" },
  ai_reviewed: { label: "AI reviewed", tone: "info" },
  hr_review_pending: { label: "HR review pending", tone: "warning" },
  shortlisted: { label: "Shortlisted", tone: "info" },
  first_interview: { label: "First interview", tone: "info" },
  technical_interview: { label: "Technical interview", tone: "info" },
  final_interview: { label: "Final interview", tone: "info" },
  waiting_list: { label: "Waiting list", tone: "warning" },
  recommended_for_offer: { label: "Recommended for offer", tone: "success" },
  selected: { label: "Selected", tone: "success" },
  offer_sent: { label: "Offer sent", tone: "info" },
  joined: { label: "Joined", tone: "success" },
  not_joined: { label: "Not joined", tone: "danger" },
  rejected: { label: "Rejected", tone: "danger" },
  blacklisted: { label: "Blacklisted", tone: "danger" },
};

const INTERVIEW: Record<string, BadgeSpec> = {
  scheduled: { label: "Scheduled", tone: "info" },
  completed: { label: "Completed", tone: "success" },
  cancelled: { label: "Cancelled", tone: "danger" },
  rescheduled: { label: "Rescheduled", tone: "warning" },
  no_show: { label: "No-show", tone: "warning" },
};

const OFFER: Record<string, BadgeSpec> = {
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


const TABLES: Record<HrStatusKind, Record<string, BadgeSpec>> = {
  job: JOB,
  approval: APPROVAL,
  publish: PUBLISH,
  candidate: CANDIDATE,
  interview: INTERVIEW,
  offer: OFFER,
};


const TONE_CLASSES: Record<Tone, string> = {
  neutral: "border-border/60 bg-muted/50 text-muted-foreground",
  info: "border-primary/30 bg-primary/10 text-primary",
  success:
    "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  warning:
    "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  danger:
    "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
};


interface Props {
  kind: HrStatusKind;
  value: string;
  /** Override the canonical label. */
  label?: string;
  className?: string;
}


export function HrStatusBadge({ kind, value, label, className }: Props) {
  const spec = TABLES[kind][value] ?? {
    label: value || "—",
    tone: "neutral" as const,
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        TONE_CLASSES[spec.tone],
        className,
      )}
    >
      {label ?? spec.label}
    </span>
  );
}


/** Lookup the canonical label without rendering — handy when other
 *  components need the same string (e.g. in tooltips). */
export function statusLabel(kind: HrStatusKind, value: string): string {
  return TABLES[kind][value]?.label ?? value;
}
