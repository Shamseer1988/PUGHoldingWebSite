"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  EyeOff,
  FileEdit,
  Loader2,
  RotateCcw,
  Send,
  XCircle,
} from "lucide-react";

import { hrApi, HrApiError } from "@/lib/hr/api";
import type { JobApprovalHistoryItem } from "@/lib/hr/types";
import { cn } from "@/lib/utils";


interface Props {
  jobId: number;
  /**
   * Bump this prop after any approval action so the timeline re-fetches.
   * Default behavior: load once on mount.
   */
  refreshKey?: number | string;
}


/**
 * Renders the approval-history timeline for a JobOpening — read-only,
 * fetches GET /hr/jobs/{id}/approval-history. Each row is one
 * transition recorded in hr_job_approval_history (submit, approve,
 * reject, request-revision, publish, unpublish, revision-submitted,
 * revision-approve, revision-reject).
 */
export function JobApprovalTimeline({ jobId, refreshKey }: Props) {
  const [items, setItems] = React.useState<JobApprovalHistoryItem[] | null>(
    null
  );
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setItems(null);
    setError(null);
    hrApi
      .get<JobApprovalHistoryItem[]>(`/hr/jobs/${jobId}/approval-history`)
      .then((rows) => {
        if (!cancelled) setItems(rows);
      })
      .catch((err) => {
        if (!cancelled) setError((err as HrApiError).message);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, refreshKey]);

  if (error) {
    return (
      <p
        role="alert"
        className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300"
      >
        <AlertTriangle className="mr-1 inline h-3.5 w-3.5" />
        {error}
      </p>
    );
  }

  if (items === null) {
    return (
      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading approval history…
      </p>
    );
  }

  if (items.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border/60 bg-card px-3 py-4 text-center text-xs text-muted-foreground">
        No approval events yet — submit the job for approval to start the audit
        trail.
      </p>
    );
  }

  return (
    <ol className="space-y-3">
      {items.map((entry) => (
        <TimelineRow key={entry.id} entry={entry} />
      ))}
    </ol>
  );
}


// ---------------------------------------------------------------------------
// Row rendering
// ---------------------------------------------------------------------------


interface RowVisuals {
  Icon: React.ComponentType<{ className?: string }>;
  label: string;
  tone: "neutral" | "success" | "warning" | "danger" | "info";
}


const ACTION_META: Record<string, RowVisuals> = {
  // hr_job_approval_history actions emitted by the backend.
  submit: { Icon: Send, label: "Submitted for approval", tone: "info" },
  approve: { Icon: CheckCircle2, label: "Approved", tone: "success" },
  reject: { Icon: XCircle, label: "Rejected", tone: "danger" },
  request_revision: {
    Icon: RotateCcw,
    label: "Changes requested",
    tone: "warning",
  },
  revision_submitted: {
    Icon: FileEdit,
    label: "Revision submitted",
    tone: "info",
  },
  revision_approved: {
    Icon: CheckCircle2,
    label: "Revision approved",
    tone: "success",
  },
  revision_rejected: {
    Icon: XCircle,
    label: "Revision rejected",
    tone: "danger",
  },
  publish: { Icon: Eye, label: "Published", tone: "success" },
  unpublish: { Icon: EyeOff, label: "Unpublished", tone: "warning" },
};


const TONE_CLASSES: Record<RowVisuals["tone"], string> = {
  neutral: "border-border/60 bg-muted/50 text-muted-foreground",
  success:
    "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  warning:
    "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  danger:
    "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
  info:
    "border-primary/30 bg-primary/10 text-primary",
};


function TimelineRow({ entry }: { entry: JobApprovalHistoryItem }) {
  const meta = ACTION_META[entry.action] ?? {
    Icon: FileEdit,
    label: entry.action.replace(/_/g, " "),
    tone: "neutral" as const,
  };
  const Icon = meta.Icon;
  const changedFieldKeys = entry.changed_fields
    ? Object.keys(entry.changed_fields)
    : [];

  return (
    <li className="flex gap-3">
      <span
        className={cn(
          "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border",
          TONE_CLASSES[meta.tone]
        )}
      >
        <Icon className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0 flex-1 rounded-md border border-border/60 bg-card px-3 py-2 text-xs">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="font-medium">{meta.label}</p>
          <p className="text-[11px] text-muted-foreground">
            {new Date(entry.created_at).toLocaleString()}
          </p>
        </div>
        {(entry.old_approval_status || entry.new_approval_status) && (
          <p className="mt-1 text-[11px] text-muted-foreground">
            {entry.old_approval_status ?? "—"}
            <span className="mx-1">→</span>
            {entry.new_approval_status ?? "—"}
          </p>
        )}
        {entry.actor_email && (
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            by {entry.actor_email}
          </p>
        )}
        {entry.remarks && (
          <p className="mt-1 whitespace-pre-wrap rounded bg-muted/40 px-2 py-1 text-[11px] text-foreground/90">
            {entry.remarks}
          </p>
        )}
        {changedFieldKeys.length > 0 && (
          <p className="mt-1 text-[11px] text-muted-foreground">
            Changed: <code className="text-foreground/80">{changedFieldKeys.join(", ")}</code>
          </p>
        )}
      </div>
    </li>
  );
}
