"use client";

import * as React from "react";
import { AlertTriangle, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";


interface Props {
  /** Headline rendered at the top of the modal. */
  title: string;
  /** Short copy explaining the consequence of the action. */
  description: string;
  /** Label for the confirm button (e.g. "Archive", "Delete"). */
  confirmLabel: string;
  /** Variant of the confirm button — danger uses red styling. */
  tone?: "default" | "danger";
  /**
   * Mandatory: the user must type ≥4 chars before the confirm button
   * is enabled. Set to false to make the reason optional (still
   * captured if typed). Default true.
   */
  requireReason?: boolean;
  /** Override the min-length when requireReason is true. Default 4. */
  minReasonLength?: number;
  /** Async submit handler — receives the reason string (may be empty
   *  if requireReason=false). Should throw on failure. */
  onConfirm: (reason: string) => Promise<void>;
  onClose: () => void;
}


/**
 * Phase 8 — reason-capturing confirmation dialog.
 *
 * Replaces the browser confirm() with a proper modal that requires
 * HR to type a reason before destructive / archive actions go
 * through. The reason lands in the audit log via the backend's
 * payload contract; this component just collects it.
 *
 * Usage:
 *   <ConfirmReasonDialog
 *     title="Archive this job?"
 *     description="The job is hidden from listings but the history is kept."
 *     confirmLabel="Archive"
 *     tone="danger"
 *     onConfirm={async (reason) => await hrApi.post(`/hr/jobs/${id}/archive`, { reason })}
 *     onClose={() => setOpen(false)}
 *   />
 */
export function ConfirmReasonDialog({
  title,
  description,
  confirmLabel,
  tone = "default",
  requireReason = true,
  minReasonLength = 4,
  onConfirm,
  onClose,
}: Props) {
  const [reason, setReason] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const meetsRequirement =
    !requireReason || reason.trim().length >= minReasonLength;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!meetsRequirement) return;
    setSaving(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-background/60 backdrop-blur-sm p-4"
    >
      <form
        onSubmit={submit}
        className="w-full max-w-md space-y-4 rounded-xl border border-border/60 bg-background p-5 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            <AlertTriangle
              className={`mt-0.5 h-4 w-4 shrink-0 ${
                tone === "danger" ? "text-rose-600" : "text-amber-600"
              }`}
            />
            <div>
              <h3 className="text-sm font-semibold">{title}</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {description}
              </p>
            </div>
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
          <Label className="text-xs">
            {requireReason
              ? `Reason (required, ≥ ${minReasonLength} chars)`
              : "Reason (optional)"}
          </Label>
          <Textarea
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Type why this is happening — recorded in the audit log."
            disabled={saving}
            autoFocus
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
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={saving || !meetsRequirement}
            className={
              tone === "danger"
                ? "bg-rose-600 text-white hover:bg-rose-700"
                : undefined
            }
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            {confirmLabel}
          </Button>
        </footer>
      </form>
    </div>
  );
}
