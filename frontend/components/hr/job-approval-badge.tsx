"use client";

import * as React from "react";

import type { ApprovalStatus, PublishStatus } from "@/lib/hr/types";
import { Badge } from "@/components/ui/badge";

interface JobApprovalBadgeProps {
  approvalStatus?: ApprovalStatus;
  publishStatus?: PublishStatus;
  hasPendingRevision?: boolean;
}

const APPROVAL_LABEL: Record<ApprovalStatus, string> = {
  draft: "Draft",
  pending_approval: "Pending approval",
  approved: "Approved",
  rejected: "Rejected",
  revision_required: "Revision required",
};

const APPROVAL_COLOR: Record<ApprovalStatus, string> = {
  draft: "bg-slate-100 text-slate-700",
  pending_approval: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-rose-100 text-rose-800",
  revision_required: "bg-orange-100 text-orange-800",
};

const PUBLISH_LABEL: Record<PublishStatus, string> = {
  draft: "Not yet public",
  published: "Live on public site",
  unpublished: "Hidden from public",
};

const PUBLISH_COLOR: Record<PublishStatus, string> = {
  draft: "bg-slate-100 text-slate-600",
  published: "bg-emerald-100 text-emerald-800",
  unpublished: "bg-amber-100 text-amber-800",
};

/**
 * Compact pair of badges showing where a job sits in the approval workflow
 * and whether it's currently visible on the public site.
 */
export function JobApprovalBadge({
  approvalStatus,
  publishStatus,
  hasPendingRevision,
}: JobApprovalBadgeProps) {
  if (!approvalStatus && !publishStatus) {
    return null;
  }
  return (
    <span className="inline-flex flex-wrap gap-1.5">
      {approvalStatus ? (
        <Badge className={APPROVAL_COLOR[approvalStatus]}>
          {APPROVAL_LABEL[approvalStatus]}
        </Badge>
      ) : null}
      {publishStatus ? (
        <Badge className={PUBLISH_COLOR[publishStatus]}>
          {PUBLISH_LABEL[publishStatus]}
        </Badge>
      ) : null}
      {hasPendingRevision ? (
        <Badge className="bg-violet-100 text-violet-800">
          Pending edit
        </Badge>
      ) : null}
    </span>
  );
}
