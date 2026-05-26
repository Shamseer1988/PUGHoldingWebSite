"use client";

import * as React from "react";
import { AlertCircle, CheckCircle2, Loader2, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type {
  BulkCandidateStatusChangeResult,
  BulkCandidateStatusChangeRow,
} from "@/lib/hr/types";

interface Props {
  selectedApplicationIds: number[];
  open: boolean;
  onClose: () => void;
  onCompleted: (result: BulkCandidateStatusChangeResult) => void;
}

const STATUS_OPTIONS = [
  { value: "shortlisted", label: "Shortlist" },
  { value: "hr_review_pending", label: "Mark HR Review Pending" },
  { value: "rejected", label: "Reject (reason required)" },
  { value: "selected", label: "Selected" },
  { value: "first_interview", label: "Move to First Interview" },
  { value: "technical_interview", label: "Move to Technical Interview" },
  { value: "final_interview", label: "Move to Final Interview" },
  { value: "offer_sent", label: "Offer Sent" },
  { value: "joined", label: "Joined" },
];

export function BulkStatusModal({
  selectedApplicationIds,
  open,
  onClose,
  onCompleted,
}: Props) {
  const [newStatus, setNewStatus] = React.useState("shortlisted");
  const [remarks, setRemarks] = React.useState("");
  const [rejectionReason, setRejectionReason] = React.useState("");
  const [sendEmail, setSendEmail] = React.useState(false);
  const [allOrNothing, setAllOrNothing] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<BulkCandidateStatusChangeResult | null>(
    null,
  );

  React.useEffect(() => {
    if (!open) {
      setNewStatus("shortlisted");
      setRemarks("");
      setRejectionReason("");
      setSendEmail(false);
      setAllOrNothing(false);
      setError(null);
      setResult(null);
    }
  }, [open]);

  if (!open) return null;

  const requiresReason = newStatus === "rejected";

  async function apply() {
    if (requiresReason && rejectionReason.trim().length < 4) {
      setError("A rejection reason of at least 4 characters is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = {
        application_ids: selectedApplicationIds,
        new_status: newStatus,
        remarks: remarks.trim() || undefined,
        rejection_reason: requiresReason ? rejectionReason.trim() : undefined,
        send_email: sendEmail,
        all_or_nothing: allOrNothing,
      };
      const res = await hrApi.post<BulkCandidateStatusChangeResult>(
        "/hr/candidates/applications/bulk-status",
        body,
      );
      setResult(res);
      onCompleted(res);
    } catch (err) {
      if (err instanceof HrApiError) {
        setError(err.message);
      } else {
        setError("Unexpected error");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Bulk status change
            </h2>
            <p className="text-sm text-slate-600">
              {selectedApplicationIds.length} application
              {selectedApplicationIds.length === 1 ? "" : "s"} selected.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>

        {result ? (
          <div className="space-y-3">
            <div className="flex gap-4 rounded-md border bg-slate-50 p-3 text-sm">
              <div>
                <span className="font-semibold text-emerald-700">
                  {result.success_count}
                </span>{" "}
                succeeded
              </div>
              <div>
                <span className="font-semibold text-rose-700">
                  {result.failed_count}
                </span>{" "}
                failed
              </div>
              <div>
                <span className="font-semibold">{result.total}</span> total
              </div>
            </div>

            <div className="max-h-80 overflow-y-auto rounded border">
              <table className="w-full text-xs">
                <thead className="bg-slate-100 text-left">
                  <tr>
                    <th className="px-2 py-1.5">App #</th>
                    <th className="px-2 py-1.5">Was</th>
                    <th className="px-2 py-1.5">Now</th>
                    <th className="px-2 py-1.5">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row: BulkCandidateStatusChangeRow) => (
                    <tr key={row.application_id} className="border-t">
                      <td className="px-2 py-1">{row.application_id}</td>
                      <td className="px-2 py-1 text-slate-500">
                        {row.old_status ?? "—"}
                      </td>
                      <td className="px-2 py-1">{row.new_status ?? "—"}</td>
                      <td className="px-2 py-1">
                        {row.success ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700">
                            <CheckCircle2 className="h-3.5 w-3.5" /> OK
                          </span>
                        ) : (
                          <span
                            className="inline-flex items-center gap-1 text-rose-700"
                            title={row.error ?? ""}
                          >
                            <XCircle className="h-3.5 w-3.5" />{" "}
                            {row.error ?? "Failed"}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end">
              <Button onClick={onClose}>Done</Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <Label htmlFor="bulk-status">New status</Label>
              <Select
                id="bulk-status"
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
            </div>

            {requiresReason ? (
              <div>
                <Label htmlFor="bulk-reason">
                  Rejection reason (required, ≥ 4 chars)
                </Label>
                <Textarea
                  id="bulk-reason"
                  rows={2}
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                />
              </div>
            ) : null}

            <div>
              <Label htmlFor="bulk-remarks">Remarks (optional)</Label>
              <Textarea
                id="bulk-remarks"
                rows={2}
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
              />
            </div>

            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={sendEmail}
                  onChange={(e) => setSendEmail(e.target.checked)}
                />
                Send branded email to each candidate
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={allOrNothing}
                  onChange={(e) => setAllOrNothing(e.target.checked)}
                />
                All or nothing
              </label>
            </div>

            {error ? (
              <div className="flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
                <AlertCircle className="mt-0.5 h-4 w-4" />
                <span>{error}</span>
              </div>
            ) : null}

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={onClose} disabled={busy}>
                Cancel
              </Button>
              <Button onClick={apply} disabled={busy}>
                {busy ? (
                  <span className="inline-flex items-center gap-1.5">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Applying…
                  </span>
                ) : (
                  `Apply to ${selectedApplicationIds.length} application${
                    selectedApplicationIds.length === 1 ? "" : "s"
                  }`
                )}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
