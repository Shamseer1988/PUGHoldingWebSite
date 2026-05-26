"use client";

import * as React from "react";
import {
  CheckCircle2,
  Eye,
  EyeOff,
  RotateCcw,
  Send,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type { ApprovalStatus, JobOpening, PublishStatus } from "@/lib/hr/types";

interface Props {
  job: JobOpening;
  onUpdated: (job: JobOpening) => void;
  /** Whether this user can approve (HR Manager). */
  canApprove?: boolean;
}

type Action =
  | "submit-approval"
  | "approve"
  | "reject"
  | "request-revision"
  | "publish"
  | "unpublish";

const ACTION_LABEL: Record<Action, string> = {
  "submit-approval": "Submit for approval",
  approve: "Approve",
  reject: "Reject",
  "request-revision": "Request revision",
  publish: "Publish",
  unpublish: "Unpublish",
};

/**
 * Approval workflow buttons for an HR Job. Picks which buttons to show
 * based on the job's current approval / publish status.
 */
export function JobApprovalActions({ job, onUpdated, canApprove = true }: Props) {
  const [remarks, setRemarks] = React.useState("");
  const [showRemarks, setShowRemarks] = React.useState<Action | null>(null);
  const [busy, setBusy] = React.useState<Action | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const approval = (job.approval_status ?? "draft") as ApprovalStatus;
  const publish = (job.publish_status ?? "draft") as PublishStatus;

  const fire = React.useCallback(
    async (action: Action) => {
      setBusy(action);
      setError(null);
      try {
        const body =
          action === "reject"
            ? { remarks: remarks.trim() }
            : remarks.trim()
              ? { remarks: remarks.trim() }
              : undefined;
        const updated = await hrApi.post<JobOpening>(
          `/hr/jobs/${job.id}/${action}`,
          body,
        );
        onUpdated(updated);
        setRemarks("");
        setShowRemarks(null);
      } catch (err) {
        if (err instanceof HrApiError) {
          setError(err.message);
        } else {
          setError("Unexpected error");
        }
      } finally {
        setBusy(null);
      }
    },
    [job.id, remarks, onUpdated],
  );

  const renderBtn = (
    action: Action,
    icon: React.ReactNode,
    variant: "default" | "secondary" | "destructive" | "outline" = "secondary",
  ) => {
    const needsRemark = action === "reject" || action === "request-revision";
    if (needsRemark && showRemarks !== action) {
      return (
        <Button
          key={action}
          type="button"
          variant={variant}
          size="sm"
          onClick={() => setShowRemarks(action)}
          disabled={busy !== null}
        >
          {icon}
          <span className="ml-1">{ACTION_LABEL[action]}</span>
        </Button>
      );
    }
    return (
      <Button
        key={action}
        type="button"
        variant={variant}
        size="sm"
        onClick={() => fire(action)}
        disabled={
          busy !== null ||
          (action === "reject" && remarks.trim().length < 4)
        }
      >
        {busy === action ? "…" : icon}
        <span className="ml-1">{ACTION_LABEL[action]}</span>
      </Button>
    );
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {approval === "draft" || approval === "rejected" || approval === "revision_required" ? (
          renderBtn("submit-approval", <Send className="h-3.5 w-3.5" />, "default")
        ) : null}

        {canApprove && approval === "pending_approval"
          ? renderBtn("approve", <CheckCircle2 className="h-3.5 w-3.5" />, "default")
          : null}

        {canApprove && approval === "pending_approval"
          ? renderBtn("request-revision", <RotateCcw className="h-3.5 w-3.5" />, "outline")
          : null}

        {canApprove && approval === "pending_approval"
          ? renderBtn("reject", <XCircle className="h-3.5 w-3.5" />, "destructive")
          : null}

        {approval === "approved" && publish !== "published"
          ? renderBtn("publish", <Eye className="h-3.5 w-3.5" />, "default")
          : null}

        {approval === "approved" && publish === "published"
          ? renderBtn("unpublish", <EyeOff className="h-3.5 w-3.5" />, "secondary")
          : null}
      </div>

      {showRemarks ? (
        <div className="space-y-1.5 rounded-md border border-amber-200 bg-amber-50 p-3">
          <label className="text-xs font-medium text-amber-900">
            {showRemarks === "reject"
              ? "Rejection reason (required, ≥ 4 chars)"
              : "Reason / notes"}
          </label>
          <Textarea
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
            rows={2}
            className="text-sm"
            placeholder="Provide a clear note for the HR Executive…"
          />
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setShowRemarks(null);
                setRemarks("");
                setError(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : null}

      {error ? (
        <p className="text-xs text-rose-700">{error}</p>
      ) : null}
    </div>
  );
}
