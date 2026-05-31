"use client";

import * as React from "react";

import { ConfirmReasonDialog } from "@/components/hr/confirm-reason-dialog";
import { hrApi } from "@/lib/hr/api";

/**
 * Mark a candidate as a no-show / not-joined (acceptance criterion 7).
 *
 * Captures a mandatory reason (the backend requires ≥4 chars) and calls
 * ``POST /hr/offers/{id}/mark-not-joined``. Thin wrapper over the shared
 * ConfirmReasonDialog so the reason-capture UX stays consistent.
 */
interface Props {
  offerId: number;
  candidateName?: string | null;
  onClose: () => void;
  onDone: () => void;
}

export function MarkNotJoinedDialog({
  offerId,
  candidateName,
  onClose,
  onDone,
}: Props) {
  return (
    <ConfirmReasonDialog
      title="Mark as not joined"
      description={`Record why ${
        candidateName ?? "this candidate"
      } did not join. This is kept on the offer and in the audit log.`}
      confirmLabel="Mark not joined"
      tone="danger"
      requireReason
      minReasonLength={4}
      onConfirm={async (reason) => {
        await hrApi.post(`/hr/offers/${offerId}/mark-not-joined`, { reason });
        onDone();
      }}
      onClose={onClose}
    />
  );
}
