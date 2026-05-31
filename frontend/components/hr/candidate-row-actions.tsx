"use client";

import * as React from "react";
import {
  CalendarPlus,
  ClipboardList,
  Handshake,
  Maximize2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { statusLabel } from "@/components/hr/status-badge";
import { cn } from "@/lib/utils";

/**
 * Inline candidate action cluster (acceptance criterion 3).
 *
 *   [ Update Status ▾ ] [ Schedule Interview ] [ Send Assessment ]
 *   [ Issue Offer ] [ Open 360° ]
 *
 * Used both in the Candidates table and on the Pipeline kanban cards, so
 * it stays presentational: the parent owns the actual flows (status
 * change, offer dialog, drawer) and passes them in as callbacks. Button
 * enablement is derived from the application's current status and is
 * exported as a pure helper so it can be unit-tested against the
 * backend's ALLOWED_TRANSITIONS rules.
 */

// Final application states have no outgoing transitions
// (mirrors candidate_workflow.FINAL_STATUSES).
export const FINAL_APPLICATION_STATUSES = new Set([
  "joined",
  "not_joined",
  "rejected",
  "blacklisted",
]);

// "Issue Offer" is only valid once a candidate is recommended/selected
// (mirrors the offer-eligibility rule in the spec + offers service).
export const OFFER_ELIGIBLE_STATUSES = new Set([
  "recommended_for_offer",
  "selected",
]);

export interface CandidateActionEnablement {
  updateStatus: boolean;
  scheduleInterview: boolean;
  sendAssessment: boolean;
  issueOffer: boolean;
  open360: boolean;
}

/**
 * Which actions are available for an application at ``status``.
 *
 * ``allowedNext`` is the list of legal next statuses from
 * ``GET /hr/candidates/workflow/meta`` (i.e. ALLOWED_TRANSITIONS for the
 * current status); update-status is enabled exactly when that list is
 * non-empty, so the UI never offers a move the backend would reject.
 */
export function candidateActionEnablement(
  status: string | null | undefined,
  allowedNext: readonly string[],
): CandidateActionEnablement {
  const isFinal = !!status && FINAL_APPLICATION_STATUSES.has(status);
  const active = !!status && !isFinal;
  return {
    updateStatus: allowedNext.length > 0,
    scheduleInterview: active,
    sendAssessment: active,
    issueOffer: !!status && OFFER_ELIGIBLE_STATUSES.has(status),
    open360: true,
  };
}

interface CandidateRowActionsProps {
  status: string | null;
  /** Most-recent application id; null = candidate has no application
   *  to act on yet (only "Open 360°" stays enabled). */
  applicationId: number | null;
  /** Allowed next statuses for ``status`` (from workflow meta). */
  allowedNext: readonly string[];
  onUpdateStatus: (target: string) => void;
  onScheduleInterview: () => void;
  onSendAssessment: () => void;
  onIssueOffer: () => void;
  onOpen360: () => void;
  className?: string;
}

export function CandidateRowActions({
  status,
  applicationId,
  allowedNext,
  onUpdateStatus,
  onScheduleInterview,
  onSendAssessment,
  onIssueOffer,
  onOpen360,
  className,
}: CandidateRowActionsProps) {
  const enablement = candidateActionEnablement(status, allowedNext);
  const hasApp = applicationId != null;

  return (
    <div
      className={cn("flex items-center justify-end gap-1", className)}
      // Actions must not bubble up to a row-level "open drawer" click.
      onClick={(e) => e.stopPropagation()}
    >
      <Select
        aria-label="Update status"
        title={
          enablement.updateStatus && hasApp
            ? "Move to the next stage"
            : "No further status changes available"
        }
        value=""
        disabled={!enablement.updateStatus || !hasApp}
        onChange={(e) => {
          const target = e.target.value;
          if (target) onUpdateStatus(target);
        }}
        className="h-8 w-[8.5rem] py-0 text-xs"
      >
        <option value="">Update status…</option>
        {allowedNext.map((s) => (
          <option key={s} value={s}>
            {statusLabel("application", s)}
          </option>
        ))}
      </Select>

      <ActionIcon
        label="Schedule interview"
        icon={CalendarPlus}
        disabled={!enablement.scheduleInterview || !hasApp}
        onClick={onScheduleInterview}
      />
      <ActionIcon
        label="Send assessment"
        icon={ClipboardList}
        disabled={!enablement.sendAssessment || !hasApp}
        onClick={onSendAssessment}
      />
      <ActionIcon
        label="Issue offer"
        icon={Handshake}
        disabled={!enablement.issueOffer || !hasApp}
        onClick={onIssueOffer}
      />
      <ActionIcon
        label="Open 360°"
        icon={Maximize2}
        onClick={onOpen360}
      />
    </div>
  );
}

function ActionIcon({
  label,
  icon: Icon,
  disabled,
  onClick,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="h-8 w-8 px-0"
      disabled={disabled}
      onClick={onClick}
      aria-label={label}
      title={label}
    >
      <Icon className="h-4 w-4" />
    </Button>
  );
}
