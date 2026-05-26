"use client";

import * as React from "react";
import {
  AlertTriangle,
  Ban,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  Loader2,
  MapPin,
  Plus,
  RefreshCw,
  Star,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  User as UserIcon,
  Video,
  Phone,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type {
  Candidate,
  CandidateApplicationSummary,
  Interview,
  InterviewCreatePayload,
  InterviewFeedbackPayload,
  InterviewSummaryForApplication,
} from "@/lib/hr/types";
import { cn } from "@/lib/utils";


interface CandidateInterviewsPanelProps {
  candidate: Candidate;
  onChanged: () => void;
}

export function CandidateInterviewsPanel({
  candidate,
  onChanged,
}: CandidateInterviewsPanelProps) {
  const [scheduleFor, setScheduleFor] = React.useState<number | null>(null);

  if (candidate.applications.length === 0) {
    return (
      <section className="rounded-xl border border-dashed border-border/60 bg-card p-5 text-sm text-muted-foreground">
        Interviews are scheduled per application — link this candidate to a job first.
      </section>
    );
  }

  return (
    <section className="space-y-3 rounded-xl border border-border/60 bg-card p-5">
      <header className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">Interviews</h3>
          <p className="text-xs text-muted-foreground">
            Schedule rounds, capture feedback, and track outcomes per application.
          </p>
        </div>
      </header>

      <div className="space-y-3">
        {candidate.applications.map((app) => (
          <ApplicationInterviewsBlock
            key={app.id}
            application={app}
            onSchedule={() => setScheduleFor(app.id)}
            onChanged={onChanged}
          />
        ))}
      </div>

      {scheduleFor !== null && (
        <ScheduleDialog
          applicationId={scheduleFor}
          onClose={() => setScheduleFor(null)}
          onSaved={() => {
            setScheduleFor(null);
            onChanged();
          }}
        />
      )}
    </section>
  );
}


function ApplicationInterviewsBlock({
  application,
  onSchedule,
  onChanged,
}: {
  application: CandidateApplicationSummary;
  onSchedule: () => void;
  onChanged: () => void;
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-background/40">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <CalendarClock className="h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">
            {application.job_title ?? "Unlinked application"}
          </p>
          <p className="text-[11px] text-muted-foreground">
            {application.interview_count} interview
            {application.interview_count === 1 ? "" : "s"}
            {application.next_interview_at && (
              <>
                {" · "}Next:{" "}
                {new Date(application.next_interview_at).toLocaleString()}
              </>
            )}
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={onSchedule}>
          <Plus className="h-3.5 w-3.5" />
          Schedule
        </Button>
      </div>

      {application.interviews.length === 0 ? (
        <p className="border-t border-border/60 px-4 py-3 text-xs text-muted-foreground">
          No interviews scheduled yet.
        </p>
      ) : (
        <ul className="divide-y divide-border/60 border-t border-border/60">
          {application.interviews.map((iv) => (
            <InterviewRow key={iv.id} interview={iv} onChanged={onChanged} />
          ))}
        </ul>
      )}
    </div>
  );
}


function InterviewRow({
  interview,
  onChanged,
}: {
  interview: InterviewSummaryForApplication;
  onChanged: () => void;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const [detail, setDetail] = React.useState<Interview | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [statusBusy, setStatusBusy] = React.useState<string | null>(null);
  const [deleting, setDeleting] = React.useState(false);
  const [showFeedback, setShowFeedback] = React.useState(false);

  React.useEffect(() => {
    if (!expanded || detail) return;
    void loadDetail();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded]);

  async function loadDetail() {
    setLoading(true);
    try {
      const data = await hrApi.get<Interview>(`/hr/interviews/${interview.id}`);
      setDetail(data);
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setLoading(false);
    }
  }

  async function changeStatus(next: string) {
    setStatusBusy(next);
    setError(null);
    try {
      await hrApi.post(`/hr/interviews/${interview.id}/status`, {
        new_status: next,
      });
      setDetail(null);
      if (expanded) await loadDetail();
      onChanged();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setStatusBusy(null);
    }
  }

  async function remove() {
    if (!confirm("Delete this interview? Feedback will also be deleted.")) return;
    setDeleting(true);
    setError(null);
    try {
      await hrApi.delete(`/hr/interviews/${interview.id}`);
      onChanged();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setDeleting(false);
    }
  }

  const ModeIcon = interview.mode === "online"
    ? Video
    : interview.mode === "phone"
      ? Phone
      : MapPin;

  return (
    <li>
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <button
          type="button"
          onClick={() => setExpanded((o) => !o)}
          className="min-w-0 flex-1 text-left"
          aria-expanded={expanded}
        >
          <p className="flex items-center gap-2 text-sm">
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider">
              R{interview.round_number}
            </span>
            <span className="font-medium">{interview.round_name}</span>
            <ModeIcon className="h-3 w-3 text-muted-foreground" />
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {new Date(interview.scheduled_at).toLocaleString()} ·{" "}
            {interview.duration_minutes} min
            {interview.interviewer_name && (
              <>
                {" · "}
                <UserIcon className="-mt-0.5 inline h-3 w-3" />{" "}
                {interview.interviewer_name}
              </>
            )}
          </p>
        </button>
        <StatusPill status={interview.status} label={interview.status_label} />
      </div>

      {expanded && (
        <div className="border-t border-border/60 bg-background/60 p-4">
          {loading && (
            <p className="text-xs text-muted-foreground">
              <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" />
              Loading interview…
            </p>
          )}

          {error && (
            <p
              role="alert"
              className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300"
            >
              <AlertTriangle className="mr-1 inline h-3.5 w-3.5" />
              {error}
            </p>
          )}

          {detail && (
            <div className="space-y-3 text-xs">
              {detail.location_or_link && (
                <p>
                  <span className="text-muted-foreground">
                    {detail.mode === "online" ? "Meeting link: " : "Location: "}
                  </span>
                  {detail.mode === "online" ? (
                    <a
                      href={detail.location_or_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      {detail.location_or_link}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : (
                    <span>{detail.location_or_link}</span>
                  )}
                </p>
              )}

              {/* Status actions */}
              {detail.status === "scheduled" && (
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => changeStatus("completed")}
                    disabled={statusBusy !== null}
                  >
                    {statusBusy === "completed" ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-3 w-3" />
                    )}
                    Mark completed
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => changeStatus("no_show")}
                    disabled={statusBusy !== null}
                  >
                    No-show
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => changeStatus("rescheduled")}
                    disabled={statusBusy !== null}
                  >
                    <RefreshCw className="h-3 w-3" />
                    Reschedule
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => changeStatus("cancelled")}
                    disabled={statusBusy !== null}
                  >
                    <Ban className="h-3 w-3" />
                    Cancel
                  </Button>
                  <span className="flex-1" />
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={remove}
                    disabled={deleting}
                    className="text-rose-600 hover:text-rose-700"
                  >
                    {deleting ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Trash2 className="h-3 w-3" />
                    )}
                  </Button>
                </div>
              )}

              {/* Feedback list */}
              {detail.feedback.length > 0 && (
                <div className="space-y-2">
                  <p className="font-medium">Feedback</p>
                  <ul className="space-y-2">
                    {detail.feedback.map((fb) => (
                      <li
                        key={fb.id}
                        className="rounded-md border border-border/60 bg-background/40 p-3"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          {typeof fb.rating === "number" && (
                            <span className="inline-flex items-center gap-0.5 text-amber-600">
                              {Array.from({ length: 5 }).map((_, i) => (
                                <Star
                                  key={i}
                                  className={cn(
                                    "h-3 w-3",
                                    i < (fb.rating ?? 0) && "fill-current"
                                  )}
                                />
                              ))}
                              <span className="ml-0.5 text-foreground">
                                {fb.rating}/5
                              </span>
                            </span>
                          )}
                          {fb.recommendation && (
                            <RecommendationPill value={fb.recommendation} />
                          )}
                          {fb.submitted_by_email && (
                            <span className="text-muted-foreground">
                              · {fb.submitted_by_email}
                            </span>
                          )}
                          <span className="text-muted-foreground">
                            · {new Date(fb.created_at).toLocaleString()}
                          </span>
                        </div>
                        {fb.feedback && (
                          <p className="mt-1 whitespace-pre-wrap text-foreground/90">
                            {fb.feedback}
                          </p>
                        )}
                        {(fb.technical_score !== null ||
                          fb.communication_score !== null ||
                          fb.cultural_fit_score !== null) && (
                          <ul className="mt-1.5 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                            {fb.technical_score !== null && (
                              <li>Tech: {fb.technical_score}/10</li>
                            )}
                            {fb.communication_score !== null && (
                              <li>Comms: {fb.communication_score}/10</li>
                            )}
                            {fb.cultural_fit_score !== null && (
                              <li>Culture: {fb.cultural_fit_score}/10</li>
                            )}
                          </ul>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Submit feedback */}
              {detail.status !== "cancelled" && detail.status !== "no_show" && (
                <>
                  {showFeedback ? (
                    <FeedbackForm
                      interviewId={detail.id}
                      onCancel={() => setShowFeedback(false)}
                      onSaved={() => {
                        setShowFeedback(false);
                        setDetail(null);
                        void loadDetail();
                        onChanged();
                      }}
                    />
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setShowFeedback(true)}
                    >
                      <Plus className="h-3 w-3" />
                      Add feedback
                    </Button>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </li>
  );
}


function FeedbackForm({
  interviewId,
  onCancel,
  onSaved,
}: {
  interviewId: number;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [rating, setRating] = React.useState<string>("4");
  const [recommendation, setRecommendation] = React.useState("hire");
  const [feedback, setFeedback] = React.useState("");
  const [tech, setTech] = React.useState("");
  const [comms, setComms] = React.useState("");
  const [culture, setCulture] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload: InterviewFeedbackPayload = {
        rating: rating ? Number(rating) : null,
        recommendation,
        feedback: feedback.trim() || null,
        technical_score: tech ? Number(tech) : null,
        communication_score: comms ? Number(comms) : null,
        cultural_fit_score: culture ? Number(culture) : null,
      };
      await hrApi.post(`/hr/interviews/${interviewId}/feedback`, payload);
      onSaved();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="space-y-3 rounded-md border border-border/60 bg-background/40 p-3"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label className="text-xs">Rating (1–5)</Label>
          <Input
            type="number"
            min="1"
            max="5"
            value={rating}
            onChange={(e) => setRating(e.target.value)}
            disabled={saving}
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Recommendation</Label>
          <Select
            value={recommendation}
            onChange={(e) => setRecommendation(e.target.value)}
            disabled={saving}
          >
            <option value="hire">Hire</option>
            <option value="maybe">Maybe</option>
            <option value="no_hire">No hire</option>
          </Select>
        </div>
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Feedback notes</Label>
        <Textarea
          rows={3}
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          disabled={saving}
          placeholder="Strengths, weaknesses, follow-up topics…"
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label className="text-xs">Technical (0–10)</Label>
          <Input
            type="number"
            min="0"
            max="10"
            value={tech}
            onChange={(e) => setTech(e.target.value)}
            disabled={saving}
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Communication</Label>
          <Input
            type="number"
            min="0"
            max="10"
            value={comms}
            onChange={(e) => setComms(e.target.value)}
            disabled={saving}
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Cultural fit</Label>
          <Input
            type="number"
            min="0"
            max="10"
            value={culture}
            onChange={(e) => setCulture(e.target.value)}
            disabled={saving}
          />
        </div>
      </div>
      {error && (
        <p
          role="alert"
          className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300"
        >
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={saving}>
          {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Submit feedback
        </Button>
      </div>
    </form>
  );
}


function ScheduleDialog({
  applicationId,
  onClose,
  onSaved,
}: {
  applicationId: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [roundName, setRoundName] = React.useState("");
  const [roundNumber, setRoundNumber] = React.useState("1");
  const [scheduledAt, setScheduledAt] = React.useState("");
  const [duration, setDuration] = React.useState("60");
  const [mode, setMode] = React.useState<"online" | "phone" | "in_person">("online");
  const [locationLink, setLocationLink] = React.useState("");
  const [interviewerId, setInterviewerId] = React.useState("");
  // Default ON — the most common HR workflow is "schedule AND notify
  // the candidate immediately". HR has to actively untick to save a
  // draft without emailing.
  const [sendEmail, setSendEmail] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload: InterviewCreatePayload = {
        application_id: applicationId,
        round_name: roundName.trim(),
        round_number: Number(roundNumber) || 1,
        scheduled_at: new Date(scheduledAt).toISOString(),
        duration_minutes: Number(duration) || 60,
        mode,
        location_or_link: locationLink.trim() || null,
        interviewer_id: interviewerId ? Number(interviewerId) : null,
        send_email_now: sendEmail,
      };
      await hrApi.post("/hr/interviews", payload);
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
      aria-label="Schedule interview"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-background/60 backdrop-blur-sm p-4"
    >
      <form
        onSubmit={submit}
        className="w-full max-w-lg space-y-4 rounded-xl border border-border/60 bg-background p-5 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Schedule interview</h3>
            <p className="text-xs text-muted-foreground">
              Online and in-person rounds need a meeting link or location.
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
              Round name <span className="text-rose-500">*</span>
            </Label>
            <Input
              value={roundName}
              onChange={(e) => setRoundName(e.target.value)}
              placeholder="e.g. First interview, Technical screen"
              required
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Round number</Label>
            <Input
              type="number"
              min="1"
              max="20"
              value={roundNumber}
              onChange={(e) => setRoundNumber(e.target.value)}
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
          <div className="space-y-1.5 sm:col-span-2">
            <Label>
              Scheduled at <span className="text-rose-500">*</span>
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
          <div className="space-y-1.5">
            <Label>Interviewer user id (optional)</Label>
            <Input
              value={interviewerId}
              onChange={(e) => setInterviewerId(e.target.value)}
              placeholder="e.g. 42"
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>
              {mode === "online"
                ? "Meeting link"
                : mode === "in_person"
                  ? "Location"
                  : "Notes (optional)"}
              {mode !== "phone" && <span className="text-rose-500"> *</span>}
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
              required={mode !== "phone"}
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
              Send invitation email to candidate immediately
            </span>
            <span className="block text-muted-foreground">
              Branded HTML email with the round details, date/time, and a
              &ldquo;Join meeting&rdquo; button pointing to the link above.
              Untick to save the interview silently and send later via the
              interview row&apos;s resend button.
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
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Schedule
          </Button>
        </footer>
      </form>
    </div>
  );
}


function StatusPill({ status, label }: { status: string; label: string }) {
  let tone =
    "border-primary/30 bg-primary/10 text-primary";
  if (status === "completed") {
    tone =
      "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  } else if (status === "cancelled") {
    tone =
      "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300";
  } else if (status === "no_show") {
    tone =
      "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300";
  } else if (status === "rescheduled") {
    tone =
      "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
  }
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        tone
      )}
    >
      {label}
    </span>
  );
}

function RecommendationPill({ value }: { value: string }) {
  if (value === "hire") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">
        <ThumbsUp className="h-3 w-3" />
        Hire
      </span>
    );
  }
  if (value === "no_hire") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold text-rose-700 dark:text-rose-300">
        <ThumbsDown className="h-3 w-3" />
        No hire
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:text-amber-300">
      Maybe
    </span>
  );
}
