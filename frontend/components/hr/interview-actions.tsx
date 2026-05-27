"use client";

import * as React from "react";
import {
  Ban,
  CheckCircle2,
  Loader2,
  Mail,
  RefreshCw,
  UserX,
} from "lucide-react";

import { RescheduleInterviewDialog } from "@/components/hr/reschedule-interview-dialog";
import { Button } from "@/components/ui/button";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type { InterviewMode } from "@/lib/hr/types";
import { cn } from "@/lib/utils";


interface InterviewActionsProps {
  interviewId: number;
  status: string;
  /** Called after any successful action so the parent can refresh. */
  onChanged: () => void;
  /**
   * Compact mode: icon-only buttons with title tooltips. Used inside
   * the dense rows of the global /hr/interviews table. The expanded
   * candidate panel uses the full text labels (compact = false).
   */
  compact?: boolean;
  /**
   * Current schedule fields. When supplied (which is the normal case),
   * the "Reschedule" button opens the rich RescheduleInterviewDialog
   * that lets HR change date/time/mode/location and notify the
   * candidate. Without this the button silently no-ops; the legacy
   * status-only "rescheduled" path is no longer exposed since it
   * doesn't change the actual schedule.
   */
  scheduleMeta?: {
    scheduled_at: string;
    duration_minutes: number;
    mode: InterviewMode | string;
    location_or_link: string | null;
  };
}

/**
 * Row-level action buttons for an interview. Shared by the global
 * interview table and the per-candidate interviews panel.
 *
 * Action set:
 *  - Send invitation email   — always available, calls /send-email
 *  - Mark completed          — only when status === 'scheduled'
 *  - No-show                 — only when status === 'scheduled'
 *  - Reschedule              — only when status === 'scheduled'
 *  - Cancel                  — only when status === 'scheduled'
 *
 * Each click is fire-and-forget from the user's perspective; the
 * button shows a spinner while the request is in flight, and the
 * component surfaces any error inline.
 */
export function InterviewActions({
  interviewId,
  status,
  onChanged,
  compact = false,
  scheduleMeta,
}: InterviewActionsProps) {
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [rescheduleOpen, setRescheduleOpen] = React.useState(false);

  async function changeStatus(next: string) {
    setBusy(next);
    setError(null);
    try {
      await hrApi.post(`/hr/interviews/${interviewId}/status`, {
        new_status: next,
      });
      onChanged();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setBusy(null);
    }
  }

  async function sendEmail() {
    setBusy("email");
    setError(null);
    try {
      await hrApi.post(`/hr/interviews/${interviewId}/send-email`, {});
      onChanged();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setBusy(null);
    }
  }

  const canChangeStatus = status === "scheduled";

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-1.5",
        compact && "justify-end"
      )}
    >
      <ActionButton
        compact={compact}
        icon={Mail}
        label="Send invitation email"
        title="Send the branded interview invitation email to the candidate"
        onClick={sendEmail}
        busy={busy === "email"}
        disabled={busy !== null}
      />
      {canChangeStatus && (
        <>
          <ActionButton
            compact={compact}
            icon={CheckCircle2}
            label="Mark completed"
            title="Mark this interview as completed"
            onClick={() => changeStatus("completed")}
            busy={busy === "completed"}
            disabled={busy !== null}
          />
          <ActionButton
            compact={compact}
            icon={UserX}
            label="No-show"
            title="Candidate did not show up"
            onClick={() => changeStatus("no_show")}
            busy={busy === "no_show"}
            disabled={busy !== null}
          />
          <ActionButton
            compact={compact}
            icon={RefreshCw}
            label="Reschedule"
            title={
              scheduleMeta
                ? "Edit date, time, mode, location and optionally notify the candidate"
                : "Mark as rescheduled (status-only — meta not available)"
            }
            onClick={() =>
              scheduleMeta
                ? setRescheduleOpen(true)
                : changeStatus("rescheduled")
            }
            busy={busy === "rescheduled"}
            disabled={busy !== null}
          />
          <ActionButton
            compact={compact}
            icon={Ban}
            label="Cancel"
            title="Cancel this interview"
            onClick={() => changeStatus("cancelled")}
            busy={busy === "cancelled"}
            disabled={busy !== null}
            tone="danger"
          />
        </>
      )}
      {error && (
        <span
          role="alert"
          title={error}
          className="text-[11px] text-rose-600 dark:text-rose-400"
        >
          {compact ? "Error" : error}
        </span>
      )}
      {rescheduleOpen && scheduleMeta && (
        <RescheduleInterviewDialog
          interview={{
            id: interviewId,
            scheduled_at: scheduleMeta.scheduled_at,
            duration_minutes: scheduleMeta.duration_minutes,
            mode: scheduleMeta.mode,
            location_or_link: scheduleMeta.location_or_link,
          }}
          onClose={() => setRescheduleOpen(false)}
          onSaved={() => {
            setRescheduleOpen(false);
            onChanged();
          }}
        />
      )}
    </div>
  );
}


interface ActionButtonProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  title: string;
  onClick: () => void;
  busy: boolean;
  disabled: boolean;
  compact: boolean;
  tone?: "danger";
}

function ActionButton({
  icon: Icon,
  label,
  title,
  onClick,
  busy,
  disabled,
  compact,
  tone,
}: ActionButtonProps) {
  return (
    <Button
      type="button"
      size={compact ? "icon" : "sm"}
      variant="outline"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={label}
      className={cn(
        tone === "danger" && "text-rose-600 hover:text-rose-700",
        compact && "h-7 w-7"
      )}
    >
      {busy ? (
        <Loader2 className={cn(compact ? "h-3.5 w-3.5" : "h-3 w-3", "animate-spin")} />
      ) : (
        <Icon className={cn(compact ? "h-3.5 w-3.5" : "h-3 w-3")} />
      )}
      {!compact && <span className="ml-1">{label}</span>}
    </Button>
  );
}
