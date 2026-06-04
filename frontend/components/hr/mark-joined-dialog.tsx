"use client";

import * as React from "react";
import { Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import { useHrDataBump } from "@/lib/hr/data-sync";

/**
 * Mark a candidate as joined (acceptance criterion 7).
 *
 * Lets HR confirm/adjust the joining date before flipping the offer to
 * joined: if the date changed it is persisted via ``PATCH /hr/offers/{id}``
 * first, then ``POST /hr/offers/{id}/mark-joined`` records the join.
 */
interface Props {
  offerId: number;
  candidateName?: string | null;
  joiningDate: string | null;
  onClose: () => void;
  onDone: () => void;
}

export function MarkJoinedDialog({
  offerId,
  candidateName,
  joiningDate,
  onClose,
  onDone,
}: Props) {
  const [date, setDate] = React.useState(joiningDate ?? "");
  const [remarks, setRemarks] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const bump = useHrDataBump();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (date && date !== joiningDate) {
        await hrApi.patch(`/hr/offers/${offerId}`, { joining_date: date });
      }
      await hrApi.post(
        `/hr/offers/${offerId}/mark-joined`,
        remarks.trim() ? { remarks: remarks.trim() } : {},
      );
      onDone();
      bump();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Mark joined"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-background/60 p-4 backdrop-blur-sm"
    >
      <form
        onSubmit={submit}
        className="w-full max-w-md space-y-4 rounded-xl border border-border/60 bg-background p-5 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Mark as joined</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Confirm the joining date for {candidateName ?? "this candidate"}.
            </p>
          </div>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={onClose}
            disabled={saving}
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="space-y-1.5">
          <Label htmlFor="join-date" className="text-xs">
            Joining date
          </Label>
          <Input
            id="join-date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            disabled={saving}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="join-remarks" className="text-xs">
            Note (optional)
          </Label>
          <Textarea
            id="join-remarks"
            rows={2}
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
            placeholder="Anything to record about the join…"
            disabled={saving}
          />
        </div>

        {error && (
          <p
            role="alert"
            className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300"
          >
            {error}
          </p>
        )}

        <footer className="flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Mark joined
          </Button>
        </footer>
      </form>
    </div>
  );
}
