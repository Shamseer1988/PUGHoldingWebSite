"use client";

import * as React from "react";
import { Loader2, RefreshCw, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type { Interview, InterviewUpdatePayload } from "@/lib/hr/types";


interface Props {
  /** The interview being rescheduled (need at least id + current schedule). */
  interview: Pick<
    Interview,
    "id"
    | "scheduled_at"
    | "duration_minutes"
    | "mode"
    | "location_or_link"
  >;
  onClose: () => void;
  /** Called after a successful PATCH so the parent re-fetches. */
  onSaved: () => void;
}


/**
 * Phase 5 — Reschedule interview dialog.
 *
 * Lets HR (with hr:interviews:reschedule) edit the live date/time/mode/
 * location/link plus capture a reason and optionally fire the branded
 * "interview rescheduled" email to the candidate. Sends a single PATCH;
 * the backend records old vs new in the audit log and only fires the
 * email when scheduled_at actually changed AND send_email_now=true.
 */
export function RescheduleInterviewDialog({ interview, onClose, onSaved }: Props) {
  // Convert ISO -> 'YYYY-MM-DDTHH:mm' for the datetime-local input.
  function toLocalInput(iso: string): string {
    const d = new Date(iso);
    const off = d.getTimezoneOffset();
    return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 16);
  }

  const [scheduledAt, setScheduledAt] = React.useState(
    toLocalInput(interview.scheduled_at)
  );
  const [duration, setDuration] = React.useState(
    String(interview.duration_minutes)
  );
  const [mode, setMode] = React.useState<"online" | "phone" | "in_person">(
    (interview.mode as "online" | "phone" | "in_person") ?? "online"
  );
  const [locationLink, setLocationLink] = React.useState(
    interview.location_or_link ?? ""
  );
  const [reason, setReason] = React.useState("");
  const [sendEmail, setSendEmail] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload: InterviewUpdatePayload = {
        scheduled_at: new Date(scheduledAt).toISOString(),
        duration_minutes: Number(duration) || 60,
        mode,
        location_or_link: locationLink.trim() || null,
        reschedule_reason: reason.trim() || null,
        send_email_now: sendEmail,
      };
      await hrApi.patch(`/hr/interviews/${interview.id}`, payload);
      onSaved();
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
      aria-label="Reschedule interview"
      // ``text-left`` resets any inherited text-align — this dialog is
      // mounted inside an action-cell that's ``text-right`` for column
      // alignment, and without the reset the form labels render
      // right-aligned. ``ltr:text-left`` would be the same; we use the
      // plain class so it survives if the app later adds a global
      // ``dir`` toggle.
      className="fixed inset-0 z-[60] flex items-center justify-center bg-background/60 backdrop-blur-sm p-4 text-left"
    >
      <form
        onSubmit={submit}
        className="w-full max-w-lg space-y-4 rounded-xl border border-border/60 bg-background p-5 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Reschedule interview</h3>
            <p className="text-xs text-muted-foreground">
              Change the date / time / mode / location and optionally notify
              the candidate.
            </p>
          </div>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label>
              New date &amp; time <span className="text-rose-500">*</span>
            </Label>
            <Input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              required
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Duration (min)</Label>
            <Input
              type="number"
              min="5"
              max="480"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Mode</Label>
            <Select
              value={mode}
              onChange={(e) =>
                setMode(e.target.value as "online" | "phone" | "in_person")
              }
              disabled={saving}
            >
              <option value="online">Online</option>
              <option value="phone">Phone</option>
              <option value="in_person">In person</option>
            </Select>
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>
              {mode === "online"
                ? "Meeting link"
                : mode === "in_person"
                  ? "Location"
                  : "Notes (optional)"}
            </Label>
            <Input
              value={locationLink}
              onChange={(e) => setLocationLink(e.target.value)}
              placeholder={
                mode === "online"
                  ? "https://meet.example.com/abc"
                  : mode === "in_person"
                    ? "HQ Boardroom, 5th floor"
                    : "Dial-out number, etc."
              }
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Reason for reschedule</Label>
            <Textarea
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Interviewer travel; candidate exam conflict; tech issue."
              disabled={saving}
            />
          </div>
        </div>

        <label className="flex items-start gap-2 text-xs">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 rounded border-border accent-primary"
            checked={sendEmail}
            onChange={(e) => setSendEmail(e.target.checked)}
            disabled={saving}
          />
          <span>
            <span className="font-medium">
              Send updated interview email to candidate
            </span>
            <span className="block text-muted-foreground">
              Branded HTML email with the new schedule and the reason above.
              Untick to save the reschedule silently and notify manually
              later.
            </span>
          </span>
        </label>

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
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Reschedule
          </Button>
        </footer>
      </form>
    </div>
  );
}
