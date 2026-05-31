"use client";

/**
 * HR drawer panel — candidate assessment workflow (Phase 2).
 *
 * Lists the invites already issued to this candidate, lets HR send
 * a new one (modal picks from the templates tied to any of the
 * candidate's applied jobs), and surfaces the submission score
 * inline once the candidate finishes.
 *
 * The "no applications yet" empty state mirrors the interviews
 * panel — every assessment hangs off a job opening, which the
 * candidate must have applied to (or HR must have manually linked
 * them to) before we can offer one.
 */

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Loader2,
  Plus,
  Send,
  Trash2,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type {
  AssessmentInvite,
  AssessmentInviteStatus,
  AssessmentSubmission,
  AssessmentSummary,
  Candidate,
} from "@/lib/hr/types";
import { cn } from "@/lib/utils";


interface CandidateAssessmentsPanelProps {
  candidate: Candidate;
  onChanged?: () => void;
}


export function CandidateAssessmentsPanel({
  candidate,
  onChanged,
}: CandidateAssessmentsPanelProps) {
  const [invites, setInvites] = React.useState<AssessmentInvite[]>([]);
  const [submissions, setSubmissions] = React.useState<
    Record<number, AssessmentSubmission | null>
  >({});
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [showSendDialog, setShowSendDialog] = React.useState(false);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await hrApi.get<AssessmentInvite[]>(
        `/hr/assessments/invites?candidate_id=${candidate.id}`,
      );
      setInvites(list);
      // For every submitted invite, also fetch the submission so HR
      // can see the score inline. Failures here are non-fatal — the
      // submission card just shows a placeholder.
      const subs: Record<number, AssessmentSubmission | null> = {};
      await Promise.all(
        list
          .filter((inv) => inv.status === "submitted")
          .map(async (inv) => {
            try {
              subs[inv.id] = await hrApi.get<AssessmentSubmission>(
                `/hr/assessments/invites/${inv.id}/submission`,
              );
            } catch {
              subs[inv.id] = null;
            }
          }),
      );
      setSubmissions(subs);
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setLoading(false);
    }
  }, [candidate.id]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  async function cancelInvite(invite: AssessmentInvite) {
    if (!confirm("Cancel this assessment? The candidate's link will stop working.")) {
      return;
    }
    try {
      await hrApi.post(`/hr/assessments/invites/${invite.id}/cancel`);
      await refresh();
      onChanged?.();
    } catch (err) {
      alert((err as HrApiError).message);
    }
  }

  return (
    <section className="space-y-3 rounded-xl border border-border/40 bg-card p-5">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Assessments</h3>
          <p className="text-xs text-muted-foreground">
            Send a templated MCQ to this candidate and see their score
            inline.
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          onClick={() => setShowSendDialog(true)}
          disabled={candidate.applications.length === 0}
        >
          <Plus className="h-3.5 w-3.5" />
          Send assessment
        </Button>
      </header>

      {candidate.applications.length === 0 && (
        <p className="rounded-md border border-dashed border-border/60 p-4 text-xs text-muted-foreground">
          Assessments hang off a job opening. Link this candidate to an
          application first.
        </p>
      )}

      {error && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Loading…
        </div>
      ) : invites.length === 0 ? (
        <p className="rounded-md border border-dashed border-border/40 p-4 text-xs text-muted-foreground">
          No assessments sent yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {invites.map((inv) => (
            <InviteRow
              key={inv.id}
              invite={inv}
              submission={submissions[inv.id] ?? null}
              onCancel={() => void cancelInvite(inv)}
            />
          ))}
        </ul>
      )}

      {showSendDialog && (
        <SendAssessmentDialog
          candidate={candidate}
          onClose={() => setShowSendDialog(false)}
          onSent={() => {
            setShowSendDialog(false);
            void refresh();
            onChanged?.();
          }}
        />
      )}
    </section>
  );
}


// ---------------------------------------------------------------------------
// Invite row + status badge
// ---------------------------------------------------------------------------


function InviteRow({
  invite,
  submission,
  onCancel,
}: {
  invite: AssessmentInvite;
  submission: AssessmentSubmission | null;
  onCancel: () => void;
}) {
  const canCancel = invite.status !== "submitted" && invite.status !== "cancelled";
  return (
    <li className="rounded-md border border-border/40 p-3">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <ClipboardList className="h-4 w-4 text-muted-foreground" />
        <span className="font-medium">Assessment #{invite.assessment_id}</span>
        <StatusPill status={invite.status} />
        <span className="text-xs text-muted-foreground">
          Sent{" "}
          {invite.sent_at
            ? new Date(invite.sent_at).toLocaleDateString()
            : "—"}
        </span>
        {submission && (
          <span
            className={cn(
              "ml-auto rounded-md px-2 py-0.5 text-xs font-medium",
              submission.passed === true
                ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : submission.passed === false
                  ? "bg-amber-500/10 text-amber-700 dark:text-amber-300"
                  : "bg-muted text-muted-foreground",
            )}
          >
            {submission.score ?? 0} / {submission.max_score ?? 0}
            {submission.passed === true && " — passed"}
            {submission.passed === false && " — did not pass"}
          </span>
        )}
        {canCancel && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={onCancel}
            className="ml-auto h-7 px-2 text-xs"
          >
            <Trash2 className="h-3 w-3" />
            Cancel
          </Button>
        )}
      </div>
    </li>
  );
}


function StatusPill({ status }: { status: AssessmentInviteStatus }) {
  const styles: Record<AssessmentInviteStatus, string> = {
    pending: "bg-muted text-muted-foreground",
    sent: "bg-sky-500/10 text-sky-700 dark:text-sky-300",
    opened: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
    submitted: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    expired: "bg-rose-500/10 text-rose-700 dark:text-rose-300",
    cancelled: "bg-muted text-muted-foreground line-through",
  };
  return (
    <span
      className={cn(
        "rounded-md px-2 py-0.5 text-xs font-medium capitalize",
        styles[status],
      )}
    >
      {status}
    </span>
  );
}


// ---------------------------------------------------------------------------
// Send dialog
// ---------------------------------------------------------------------------


function SendAssessmentDialog({
  candidate,
  onClose,
  onSent,
}: {
  candidate: Candidate;
  onClose: () => void;
  onSent: () => void;
}) {
  const [templates, setTemplates] = React.useState<AssessmentSummary[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const [applicationId, setApplicationId] = React.useState<number | null>(
    candidate.applications[0]?.id ?? null,
  );
  const [expiresAt, setExpiresAt] = React.useState<string>("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const jobIds = Array.from(
          new Set(
            candidate.applications
              .map((a) => a.job_opening_id)
              .filter((v): v is number => v !== null),
          ),
        );
        // Fetch templates per job and dedupe (one job → many templates,
        // but the lifecycle is usually one active template per job).
        const lists = await Promise.all(
          jobIds.map(async (jid) => {
            const res = await hrApi.get<{ items: AssessmentSummary[] }>(
              `/hr/assessments?job_opening_id=${jid}&is_active=true`,
            );
            return res.items;
          }),
        );
        if (!cancelled) {
          const all = lists.flat();
          setTemplates(all);
          setSelectedId(all[0]?.id ?? null);
        }
      } catch (err) {
        if (!cancelled) {
          setError((err as HrApiError).message);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [candidate.applications]);

  async function send() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        candidate_id: candidate.id,
      };
      if (applicationId !== null) body.application_id = applicationId;
      if (expiresAt) {
        // Convert from the datetime-local format to ISO with offset.
        body.expires_at = new Date(expiresAt).toISOString();
      }
      await hrApi.post(`/hr/assessments/${selectedId}/invites`, body);
      onSent();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-xl border border-border/40 bg-background p-5 shadow-2xl">
        <header className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold">Send assessment</h3>
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

        {loading ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Loading templates…
          </div>
        ) : templates.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No active assessment templates exist for this candidate's
            applied jobs. Create one from the Assessments page first.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="template">Template</Label>
              <Select
                id="template"
                value={String(selectedId ?? "")}
                onChange={(e) => setSelectedId(Number(e.target.value))}
              >
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                    {t.time_limit_minutes
                      ? ` · ${t.time_limit_minutes} min`
                      : ""}
                  </option>
                ))}
              </Select>
            </div>

            {candidate.applications.length > 0 && (
              <div className="space-y-2">
                <Label htmlFor="application">Link to application</Label>
                <Select
                  id="application"
                  value={String(applicationId ?? "")}
                  onChange={(e) =>
                    setApplicationId(
                      e.target.value === "" ? null : Number(e.target.value),
                    )
                  }
                >
                  <option value="">(no link)</option>
                  {candidate.applications.map((a) => (
                    <option key={a.id} value={a.id}>
                      #{a.id} · {a.job_title ?? "(unspecified)"}
                    </option>
                  ))}
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="expires">Expires at (optional)</Label>
              <input
                id="expires"
                type="datetime-local"
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
                className="flex h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm"
              />
            </div>

            {error && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
                <span>{error}</span>
              </div>
            )}

            <Button
              type="button"
              className="w-full"
              disabled={!selectedId || busy}
              onClick={() => void send()}
            >
              {busy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-3.5 w-3.5" />
              )}
              Send invitation email
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
