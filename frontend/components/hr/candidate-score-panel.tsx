"use client";

import * as React from "react";
import {
  Briefcase,
  ChevronDown,
  ChevronUp,
  Loader2,
  Pencil,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import { ScoreBadge } from "@/components/hr/score-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type {
  CandidateApplicationSummary,
  CandidateScore,
  CandidateScoreBreakdown,
} from "@/lib/hr/types";
import { cn } from "@/lib/utils";

const COMPONENT_LABELS: Record<keyof CandidateScoreBreakdown, string> = {
  relevant_experience: "Relevant experience",
  required_skills: "Required skills",
  education: "Education",
  industry_experience: "Industry / company",
  gcc_qatar_experience: "GCC / Qatar experience",
  salary_fit: "Salary fit",
  notice_period: "Notice period",
  visa_status: "Visa status",
  language_match: "Language match",
  notes: "Notes",
};

const COMPONENT_MAX: Record<string, number> = {
  relevant_experience: 25,
  required_skills: 20,
  education: 10,
  industry_experience: 10,
  gcc_qatar_experience: 10,
  salary_fit: 10,
  notice_period: 5,
  visa_status: 5,
  language_match: 5,
};

interface CandidateScorePanelProps {
  candidateId: number;
  applications: CandidateApplicationSummary[];
  onChanged: () => void;
}

export function CandidateScorePanel({
  candidateId,
  applications,
  onChanged,
}: CandidateScorePanelProps) {
  if (applications.length === 0) {
    return (
      <section className="rounded-xl border border-dashed border-border/60 bg-card p-5 text-sm text-muted-foreground">
        This candidate isn't linked to any job opening yet — score is
        per-application, so it'll appear after the first application.
      </section>
    );
  }
  return (
    <section className="space-y-3 rounded-xl border border-border/60 bg-card p-5">
      <header>
        <h3 className="text-sm font-semibold">Scoring</h3>
        <p className="text-xs text-muted-foreground">
          A rule-based 0–100 fit score per application. Hover any row for
          the explanation — override with a reason if you disagree.
        </p>
      </header>
      <div className="space-y-3">
        {applications.map((app) => (
          <ApplicationScoreRow
            key={app.id}
            candidateId={candidateId}
            application={app}
            onChanged={onChanged}
          />
        ))}
      </div>
    </section>
  );
}

interface RowProps {
  candidateId: number;
  application: CandidateApplicationSummary;
  onChanged: () => void;
}

function ApplicationScoreRow({ candidateId, application, onChanged }: RowProps) {
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState<"recompute" | "clear" | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [overrideOpen, setOverrideOpen] = React.useState(false);

  const score = application.score;

  async function recompute() {
    setBusy("recompute");
    setError(null);
    try {
      await hrApi.post<CandidateScore>(
        `/hr/candidates/${candidateId}/applications/${application.id}/score/recompute`
      );
      onChanged();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setBusy(null);
    }
  }

  async function clearOverride() {
    setBusy("clear");
    setError(null);
    try {
      await hrApi.delete(
        `/hr/candidates/${candidateId}/applications/${application.id}/score/override`
      );
      onChanged();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="rounded-lg border border-border/60 bg-background/40">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <Briefcase className="h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">
            {application.job_title ?? "Unlinked application"}
          </p>
          <p className="text-[11px] text-muted-foreground">
            Status: <span className="capitalize">{application.status.replace(/_/g, " ")}</span>
          </p>
        </div>
        <ScoreBadge
          total={score?.total ?? null}
          overridden={Boolean(score?.is_manual_override)}
        />
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={recompute}
            disabled={busy !== null || !application.job_opening_id}
            className="px-2"
          >
            {busy === "recompute" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            Recompute
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setOverrideOpen(true)}
            disabled={!application.job_opening_id && !score}
            className="px-2"
          >
            <Pencil className="h-3.5 w-3.5" />
            Override
          </Button>
          {score?.is_manual_override && (
            <Button
              size="sm"
              variant="ghost"
              onClick={clearOverride}
              disabled={busy !== null}
              className="px-2"
            >
              {busy === "clear" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RotateCcw className="h-3.5 w-3.5" />
              )}
              Reset
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="px-2"
          >
            {open ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
            Breakdown
          </Button>
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="border-t border-border/60 px-4 py-2 text-xs text-rose-600 dark:text-rose-300"
        >
          {error}
        </p>
      )}

      {score?.is_manual_override && (
        <p className="flex items-start gap-2 border-t border-border/60 bg-amber-500/5 px-4 py-2 text-[11px] text-amber-700 dark:text-amber-300">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5" />
          <span>
            <strong>Manual override</strong>
            {score.override_reason ? ` — ${score.override_reason}` : ""}
          </span>
        </p>
      )}

      {open && (
        <div className="border-t border-border/60 bg-background/60 p-4">
          {score?.breakdown ? (
            <Breakdown breakdown={score.breakdown} />
          ) : (
            <p className="text-xs text-muted-foreground">
              No breakdown yet. Click Recompute to generate one.
            </p>
          )}
        </div>
      )}

      {overrideOpen && (
        <OverrideDialog
          candidateId={candidateId}
          application={application}
          onClose={() => setOverrideOpen(false)}
          onSaved={() => {
            setOverrideOpen(false);
            onChanged();
          }}
        />
      )}
    </div>
  );
}

function Breakdown({ breakdown }: { breakdown: CandidateScoreBreakdown }) {
  const keys: (keyof CandidateScoreBreakdown)[] = [
    "relevant_experience",
    "required_skills",
    "education",
    "industry_experience",
    "gcc_qatar_experience",
    "salary_fit",
    "notice_period",
    "visa_status",
    "language_match",
  ];

  return (
    <ul className="space-y-2">
      {keys.map((key) => {
        const value = breakdown[key] as number;
        const max = COMPONENT_MAX[key];
        const note = breakdown.notes?.[key];
        const pct = max > 0 ? Math.round((value / max) * 100) : 0;
        return (
          <li key={key} className="text-xs">
            <div className="flex items-center gap-3">
              <span className="w-40 shrink-0 text-foreground">
                {COMPONENT_LABELS[key]}
              </span>
              <span className="flex-1">
                <span
                  className="block h-1.5 rounded-full bg-muted"
                  aria-hidden
                >
                  <span
                    className={cn(
                      "block h-full rounded-full",
                      pct >= 80
                        ? "bg-emerald-500"
                        : pct >= 60
                          ? "bg-amber-500"
                          : pct >= 40
                            ? "bg-orange-500"
                            : "bg-rose-500"
                    )}
                    style={{ width: `${pct}%` }}
                  />
                </span>
              </span>
              <span className="w-12 shrink-0 text-right font-medium tabular-nums">
                {value}/{max}
              </span>
            </div>
            {note && (
              <p className="ml-43 mt-0.5 pl-0 text-[11px] text-muted-foreground sm:ml-40">
                {note}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

interface OverrideDialogProps {
  candidateId: number;
  application: CandidateApplicationSummary;
  onClose: () => void;
  onSaved: () => void;
}

function OverrideDialog({
  candidateId,
  application,
  onClose,
  onSaved,
}: OverrideDialogProps) {
  const [total, setTotal] = React.useState<string>(
    application.score ? String(application.score.total) : "75"
  );
  const [reason, setReason] = React.useState(
    application.score?.override_reason ?? ""
  );
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const parsedTotal = parseInt(total, 10);
    if (!Number.isFinite(parsedTotal) || parsedTotal < 0 || parsedTotal > 100) {
      setError("Score must be between 0 and 100.");
      return;
    }
    if (reason.trim().length < 4) {
      setError("Reason is required (at least a few characters).");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await hrApi.post(
        `/hr/candidates/${candidateId}/applications/${application.id}/score/override`,
        { total: parsedTotal, reason: reason.trim() }
      );
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
      aria-label="Override score"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-background/60 backdrop-blur-sm p-4"
    >
      <form
        onSubmit={save}
        className="w-full max-w-md space-y-4 rounded-xl border border-border/60 bg-background p-5 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Override score</h3>
            <p className="text-xs text-muted-foreground">
              {application.job_title ?? "Application"} — a reason is mandatory
              and will be saved in the audit log.
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

        <div className="space-y-1.5">
          <Label>New score (0–100)</Label>
          <Input
            type="number"
            min="0"
            max="100"
            step="1"
            value={total}
            onChange={(e) => setTotal(e.target.value)}
            required
            disabled={saving}
          />
        </div>

        <div className="space-y-1.5">
          <Label>
            Reason <span className="text-rose-500">*</span>
          </Label>
          <Textarea
            rows={4}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Peer screen revealed strong leadership signal not captured by the parser"
            required
            disabled={saving}
          />
        </div>

        {error && (
          <p role="alert" className="text-xs text-rose-600 dark:text-rose-300">
            {error}
          </p>
        )}

        <footer className="flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Save override
          </Button>
        </footer>
      </form>
    </div>
  );
}
