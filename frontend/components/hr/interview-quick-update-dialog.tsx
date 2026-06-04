"use client";

import * as React from "react";
import {
  CalendarClock,
  Loader2,
  Send,
  Star,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type {
  Interview,
  InterviewFeedbackPayload,
  InterviewListRow,
  InterviewUpdatePayload,
} from "@/lib/hr/types";


interface Props {
  /**
   * Row from the global /hr/interviews list — we re-fetch the full
   * Interview detail on open so the candidate summary + existing
   * feedback are always current.
   */
  row: InterviewListRow;
  onClose: () => void;
  /** Fired after a successful submit so the parent table re-fetches. */
  onSaved: () => void;
}


type Recommendation = "hire" | "no_hire" | "maybe";


/** ISO 8601 -> 'YYYY-MM-DDTHH:mm' for an <input type="datetime-local">. */
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 16);
}


/**
 * Phase 4 — Interview quick-update popup.
 *
 * Opens from a row in /hr/interviews. Combines, in a single submit:
 *   * the candidate read-only summary
 *   * status change (scheduled / completed / no_show / cancelled /
 *     rescheduled)
 *   * full feedback form: rating, recommendation, technical &
 *     communication & cultural-fit scores, strengths, weaknesses,
 *     next action, free-text feedback
 *
 * The status change fires only when the dropdown differs from the
 * current interview status. The feedback fires only when any of the
 * feedback fields was touched. Both go through their existing backend
 * endpoints; if either fails, the modal shows the error and stays
 * open.
 *
 * Permission contract (enforced server-side already):
 *   * Interviewer       can submit feedback + change status to
 *                       completed / no_show
 *   * HR Admin/Manager  can do everything
 */
export function InterviewQuickUpdateDialog({ row, onClose, onSaved }: Props) {
  const [detail, setDetail] = React.useState<Interview | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);

  // Form state — initialised after the detail loads.
  const [status, setStatus] = React.useState(row.status);
  const [rating, setRating] = React.useState<number | "">("");
  const [recommendation, setRecommendation] = React.useState<
    Recommendation | ""
  >("");
  const [technical, setTechnical] = React.useState<number | "">("");
  const [communication, setCommunication] = React.useState<number | "">("");
  const [culturalFit, setCulturalFit] = React.useState<number | "">("");
  const [feedback, setFeedback] = React.useState("");
  const [strengths, setStrengths] = React.useState("");
  const [weaknesses, setWeaknesses] = React.useState("");
  const [nextAction, setNextAction] = React.useState("");

  // Reschedule fields — shown and submitted only when status === "rescheduled".
  const [scheduledAt, setScheduledAt] = React.useState("");
  const [duration, setDuration] = React.useState("60");
  const [mode, setMode] = React.useState<"online" | "phone" | "in_person">(
    "online"
  );
  const [locationLink, setLocationLink] = React.useState("");
  const [rescheduleReason, setRescheduleReason] = React.useState("");
  const [reassignInterviewerId, setReassignInterviewerId] = React.useState("");
  const [sendRescheduleEmail, setSendRescheduleEmail] = React.useState(true);

  // Fetch fresh detail when the modal opens.
  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    hrApi
      .get<Interview>(`/hr/interviews/${row.id}`)
      .then((data) => {
        if (cancelled) return;
        setDetail(data);
        setStatus(data.status);
        // Seed the reschedule fields from the live interview so the operator
        // edits the real schedule the moment they pick "Rescheduled".
        setScheduledAt(toLocalInput(data.scheduled_at));
        setDuration(String(data.duration_minutes ?? 60));
        setMode((data.mode as "online" | "phone" | "in_person") ?? "online");
        setLocationLink(data.location_or_link ?? "");
        setReassignInterviewerId(
          data.interviewer_id ? String(data.interviewer_id) : ""
        );
        const latest = data.feedback?.[data.feedback.length - 1];
        if (latest) {
          setRating(latest.rating ?? "");
          setRecommendation((latest.recommendation as Recommendation) ?? "");
          setTechnical(latest.technical_score ?? "");
          setCommunication(latest.communication_score ?? "");
          setCulturalFit(latest.cultural_fit_score ?? "");
          setFeedback(latest.feedback ?? "");
          setStrengths(latest.strengths ?? "");
          setWeaknesses(latest.weaknesses ?? "");
          setNextAction(latest.next_action ?? "");
        }
      })
      .catch((err) => {
        if (!cancelled) setError((err as HrApiError).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [row.id]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!detail) return;
    setSaving(true);
    setError(null);
    try {
      // 1. Reschedule first when the operator moved the status to
      //    "rescheduled": a PATCH that moves the date/mode/location (and,
      //    optionally, transfers the interview to another HR user) and fires
      //    the branded "rescheduled" email when the date actually changed.
      if (status === "rescheduled") {
        const reschedulePayload: InterviewUpdatePayload = {
          scheduled_at: new Date(scheduledAt).toISOString(),
          duration_minutes: Number(duration) || 60,
          mode,
          location_or_link: locationLink.trim() || null,
          reschedule_reason: rescheduleReason.trim() || null,
          send_email_now: sendRescheduleEmail,
        };
        if (reassignInterviewerId.trim()) {
          reschedulePayload.interviewer_id = Number(reassignInterviewerId);
        }
        await hrApi.patch(`/hr/interviews/${row.id}`, reschedulePayload);
      }
      // 2. Status change if it diverges from current
      if (status !== detail.status) {
        await hrApi.post(`/hr/interviews/${row.id}/status`, {
          new_status: status,
        });
      }
      // 3. Feedback (only when anything was filled in — avoids inserting
      //    an empty row)
      const fbPayload: InterviewFeedbackPayload = {};
      if (rating !== "") fbPayload.rating = Number(rating);
      if (recommendation) fbPayload.recommendation = recommendation;
      if (technical !== "") fbPayload.technical_score = Number(technical);
      if (communication !== "")
        fbPayload.communication_score = Number(communication);
      if (culturalFit !== "")
        fbPayload.cultural_fit_score = Number(culturalFit);
      if (feedback.trim()) fbPayload.feedback = feedback.trim();
      if (strengths.trim()) fbPayload.strengths = strengths.trim();
      if (weaknesses.trim()) fbPayload.weaknesses = weaknesses.trim();
      if (nextAction.trim()) fbPayload.next_action = nextAction.trim();

      if (Object.keys(fbPayload).length > 0) {
        await hrApi.post(`/hr/interviews/${row.id}/feedback`, fbPayload);
      }
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
      aria-label="Quick update interview"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-background/60 backdrop-blur-sm p-4"
    >
      <form
        onSubmit={submit}
        className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl border border-border/60 bg-background shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-border/60 px-5 py-3">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold">
              Update interview — {row.candidate_name}
            </h3>
            <p className="truncate text-xs text-muted-foreground">
              {row.round_name}
              {row.job_title ? ` · ${row.job_title}` : ""} ·{" "}
              {new Date(row.scheduled_at).toLocaleString()}
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

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {loading && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
            </p>
          )}
          {!loading && detail && (
            <>
              {/* --- Candidate read-only summary --- */}
              <section className="rounded-md border border-border/60 bg-card px-3 py-2 text-xs">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Candidate
                </p>
                <p className="mt-0.5 font-medium">{row.candidate_name}</p>
                {row.interviewer_email && (
                  <p className="mt-0.5 text-muted-foreground">
                    Interviewer: {row.interviewer_name ?? row.interviewer_email}
                  </p>
                )}
                {detail.location_or_link && (
                  <p className="mt-0.5 truncate text-muted-foreground">
                    Location/Link: {detail.location_or_link}
                  </p>
                )}
              </section>

              {/* --- Status --- */}
              <div className="space-y-1.5">
                <Label>Interview status</Label>
                <Select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  disabled={saving}
                >
                  <option value="scheduled">Scheduled</option>
                  <option value="completed">Completed</option>
                  <option value="no_show">No-show</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="rescheduled">Rescheduled</option>
                </Select>
              </div>

              {/* --- Reschedule fields — only when status = rescheduled --- */}
              {status === "rescheduled" && (
                <section className="space-y-3 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-3">
                  <p className="flex items-center gap-1.5 text-xs font-medium">
                    <CalendarClock className="h-3.5 w-3.5 text-amber-600" />
                    New schedule
                  </p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5 sm:col-span-2">
                      <Label>
                        New date &amp; time{" "}
                        <span className="text-rose-500">*</span>
                      </Label>
                      <Input
                        type="datetime-local"
                        value={scheduledAt}
                        onChange={(e) => setScheduledAt(e.target.value)}
                        required={status === "rescheduled"}
                        disabled={saving}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Duration (min)</Label>
                      <Input
                        type="number"
                        min={5}
                        max={480}
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
                          setMode(
                            e.target.value as "online" | "phone" | "in_person"
                          )
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
                        value={rescheduleReason}
                        onChange={(e) => setRescheduleReason(e.target.value)}
                        placeholder="e.g. Interviewer travel; candidate exam conflict."
                        disabled={saving}
                      />
                    </div>
                    <div className="space-y-1.5 sm:col-span-2">
                      <Label>
                        Transfer / reassign to HR Executive (user id)
                      </Label>
                      <Input
                        value={reassignInterviewerId}
                        onChange={(e) =>
                          setReassignInterviewerId(e.target.value)
                        }
                        placeholder="e.g. 42 — leave as-is to keep the current owner"
                        disabled={saving}
                      />
                    </div>
                  </div>
                  <label className="flex items-start gap-2 text-xs">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 rounded border-border accent-primary"
                      checked={sendRescheduleEmail}
                      onChange={(e) => setSendRescheduleEmail(e.target.checked)}
                      disabled={saving}
                    />
                    <span>
                      <span className="font-medium">
                        Send updated interview email to the candidate
                      </span>
                      <span className="block text-muted-foreground">
                        Branded email with the new schedule + reason. Sent only
                        when the date actually changes.
                      </span>
                    </span>
                  </label>
                </section>
              )}

              {/* --- Feedback form (hidden while rescheduling) --- */}
              {status !== "rescheduled" && (
                <>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label className="flex items-center gap-1.5">
                    <Star className="h-3.5 w-3.5 text-amber-500" />
                    Overall rating (1-5)
                  </Label>
                  <Input
                    type="number"
                    min={1}
                    max={5}
                    value={rating}
                    onChange={(e) =>
                      setRating(e.target.value === "" ? "" : Number(e.target.value))
                    }
                    disabled={saving}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Recommendation</Label>
                  <Select
                    value={recommendation}
                    onChange={(e) =>
                      setRecommendation(e.target.value as Recommendation | "")
                    }
                    disabled={saving}
                  >
                    <option value="">—</option>
                    <option value="hire">Hire</option>
                    <option value="maybe">Maybe</option>
                    <option value="no_hire">No hire</option>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label>Technical score (0-10)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={10}
                    value={technical}
                    onChange={(e) =>
                      setTechnical(
                        e.target.value === "" ? "" : Number(e.target.value)
                      )
                    }
                    disabled={saving}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Communication score (0-10)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={10}
                    value={communication}
                    onChange={(e) =>
                      setCommunication(
                        e.target.value === "" ? "" : Number(e.target.value)
                      )
                    }
                    disabled={saving}
                  />
                </div>
                <div className="space-y-1.5 sm:col-span-2">
                  <Label>Cultural fit score (0-10)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={10}
                    value={culturalFit}
                    onChange={(e) =>
                      setCulturalFit(
                        e.target.value === "" ? "" : Number(e.target.value)
                      )
                    }
                    disabled={saving}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="flex items-center gap-1.5">
                  <ThumbsUp className="h-3.5 w-3.5 text-emerald-600" />
                  Strengths
                </Label>
                <Textarea
                  rows={2}
                  value={strengths}
                  onChange={(e) => setStrengths(e.target.value)}
                  placeholder="What did the candidate do well?"
                  disabled={saving}
                />
              </div>

              <div className="space-y-1.5">
                <Label className="flex items-center gap-1.5">
                  <ThumbsDown className="h-3.5 w-3.5 text-rose-600" />
                  Concerns / areas to improve
                </Label>
                <Textarea
                  rows={2}
                  value={weaknesses}
                  onChange={(e) => setWeaknesses(e.target.value)}
                  placeholder="What are the open questions?"
                  disabled={saving}
                />
              </div>

              <div className="space-y-1.5">
                <Label>Next action</Label>
                <Input
                  value={nextAction}
                  onChange={(e) => setNextAction(e.target.value)}
                  placeholder="e.g. Schedule technical round / Move to offer / Reject"
                  disabled={saving}
                />
              </div>

              <div className="space-y-1.5">
                <Label>Full feedback notes (optional)</Label>
                <Textarea
                  rows={3}
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  disabled={saving}
                />
              </div>
                </>
              )}
            </>
          )}

          {error && (
            <p
              role="alert"
              className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300"
            >
              {error}
            </p>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-border/60 px-5 py-3">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={saving || loading}>
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            Save update
          </Button>
        </footer>
      </form>
    </div>
  );
}
