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

import { Button } from "@/components/ui/button";
import { hrApi, HrApiError } from "@/lib/hr/api";
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
}: InterviewActionsProps) {
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

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
            title="Mark as rescheduled — then create a new interview row with the new date"
            onClick={() => changeStatus("rescheduled")}
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
