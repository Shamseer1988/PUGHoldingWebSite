"use client";

import * as React from "react";
import {
  AlertTriangle,
  BookOpen,
  Brain,
  Briefcase,
  CheckCircle2,
  HelpCircle,
  Info,
  Loader2,
  RotateCcw,
  Shield,
  Sparkles,
  Trash2,
  Wand2,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type {
  AIRecommendation,
  AIReviewGenerateResult,
  CandidateAIReview,
  CandidateApplicationSummary,
} from "@/lib/hr/types";
import { cn } from "@/lib/utils";

interface CandidateAIReviewPanelProps {
  candidateId: number;
  applications: CandidateApplicationSummary[];
  onChanged: () => void;
}

export function CandidateAIReviewPanel({
  candidateId,
  applications,
  onChanged,
}: CandidateAIReviewPanelProps) {
  if (applications.length === 0) {
    return (
      <section className="rounded-xl border border-dashed border-border/60 bg-card p-5 text-sm text-muted-foreground">
        AI review is per-application — link this candidate to a job opening
        first.
      </section>
    );
  }
  return (
    <section className="space-y-3 rounded-xl border border-border/60 bg-card p-5">
      <header>
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">AI candidate review</h3>
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-700 dark:text-amber-300">
            <Shield className="h-3 w-3" />
            Advisory only
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          A structured second-pair-of-eyes review. The AI never selects or
          rejects a candidate — the final decision is always yours.
        </p>
      </header>
      <div className="space-y-3">
        {applications.map((app) => (
          <ApplicationAIReviewRow
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

function ApplicationAIReviewRow({
  candidateId,
  application,
  onChanged,
}: RowProps) {
  const preview = application.ai_review;
  const [full, setFull] = React.useState<CandidateAIReview | null>(null);
  const [loadingFull, setLoadingFull] = React.useState(false);
  const [generating, setGenerating] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [info, setInfo] = React.useState<string | null>(null);

  // Pull the full review when a preview exists.
  React.useEffect(() => {
    if (!preview) {
      setFull(null);
      return;
    }
    void loadFull();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview?.id]);

  async function loadFull() {
    setLoadingFull(true);
    try {
      const data = await hrApi.get<CandidateAIReview>(
        `/hr/candidates/${candidateId}/applications/${application.id}/ai-review`
      );
      setFull(data);
    } catch {
      // Quietly ignore — the preview already tells HR there's something.
    } finally {
      setLoadingFull(false);
    }
  }

  async function generate() {
    setGenerating(true);
    setError(null);
    setInfo(null);
    try {
      const result = await hrApi.post<AIReviewGenerateResult>(
        `/hr/candidates/${candidateId}/applications/${application.id}/ai-review`
      );
      setFull(result.review);
      if (result.mode === "mock") {
        setInfo("Generated in mock mode — admin can switch to live in AI Settings.");
      }
      onChanged();
    } catch (err) {
      const e = err as HrApiError;
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  }

  async function remove() {
    if (!confirm("Delete this AI review? You can regenerate it any time.")) return;
    setDeleting(true);
    setError(null);
    try {
      await hrApi.delete(
        `/hr/candidates/${candidateId}/applications/${application.id}/ai-review`
      );
      setFull(null);
      onChanged();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setDeleting(false);
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
          {preview ? (
            <p className="text-[11px] text-muted-foreground">
              {preview.model_name ?? "AI"} ·{" "}
              {new Date(preview.generated_at).toLocaleString()}
            </p>
          ) : (
            <p className="text-[11px] text-muted-foreground">
              No AI review generated yet.
            </p>
          )}
        </div>
        <RecommendationChip value={preview?.recommendation ?? null} />
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={generate}
            disabled={generating}
            className="px-2"
          >
            {generating ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : preview ? (
              <RotateCcw className="h-3.5 w-3.5" />
            ) : (
              <Wand2 className="h-3.5 w-3.5" />
            )}
            {preview ? "Regenerate" : "Generate"}
          </Button>
          {preview && (
            <Button
              size="sm"
              variant="ghost"
              onClick={remove}
              disabled={deleting}
              className="px-2 text-rose-600 hover:text-rose-700"
            >
              {deleting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
            </Button>
          )}
        </div>
      </div>

      {error && (
        <p
          role="alert"
          className="border-t border-border/60 bg-rose-500/5 px-4 py-2 text-xs text-rose-600 dark:text-rose-300"
        >
          {error}
        </p>
      )}

      {info && (
        <p className="border-t border-border/60 bg-amber-500/5 px-4 py-2 text-xs text-amber-700 dark:text-amber-300">
          <Info className="mr-1 inline h-3.5 w-3.5" />
          {info}
        </p>
      )}

      {loadingFull && !full && (
        <p className="border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
          <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" />
          Loading review…
        </p>
      )}

      {full && (
        <div className="space-y-4 border-t border-border/60 bg-background/60 p-4">
          {full.summary && (
            <ReviewSection icon={<Sparkles className="h-3.5 w-3.5" />} title="Summary">
              <p className="text-foreground/90">{full.summary}</p>
            </ReviewSection>
          )}
          {full.strengths && (
            <ReviewSection
              icon={<CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />}
              title="Strengths"
            >
              <pre className="whitespace-pre-wrap font-sans text-foreground/90">
                {full.strengths}
              </pre>
            </ReviewSection>
          )}
          {full.weaknesses && (
            <ReviewSection
              icon={<XCircle className="h-3.5 w-3.5 text-rose-600" />}
              title="Weaknesses"
            >
              <pre className="whitespace-pre-wrap font-sans text-foreground/90">
                {full.weaknesses}
              </pre>
            </ReviewSection>
          )}
          {full.missing_information && (
            <ReviewSection
              icon={<HelpCircle className="h-3.5 w-3.5 text-amber-600" />}
              title="Missing information"
            >
              <pre className="whitespace-pre-wrap font-sans text-foreground/90">
                {full.missing_information}
              </pre>
            </ReviewSection>
          )}
          {full.risk_points && (
            <ReviewSection
              icon={<AlertTriangle className="h-3.5 w-3.5 text-orange-600" />}
              title="Risk points"
            >
              <pre className="whitespace-pre-wrap font-sans text-foreground/90">
                {full.risk_points}
              </pre>
            </ReviewSection>
          )}
          {full.suggested_questions && (
            <ReviewSection
              icon={<BookOpen className="h-3.5 w-3.5 text-primary" />}
              title="Suggested interview questions"
            >
              <pre className="whitespace-pre-wrap font-sans text-foreground/90">
                {full.suggested_questions}
              </pre>
            </ReviewSection>
          )}

          <p className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-700 dark:text-amber-300">
            <Brain className="mt-0.5 h-3.5 w-3.5" />
            This AI review is advisory. Selection, rejection, and any
            blacklisting must be done manually by an HR user — the AI cannot
            and does not perform those actions.
          </p>
        </div>
      )}
    </div>
  );
}

function ReviewSection({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {icon}
        {title}
      </p>
      <div className="text-xs leading-relaxed">{children}</div>
    </div>
  );
}

function RecommendationChip({
  value,
}: {
  value: string | null | undefined;
}) {
  const tone: Record<AIRecommendation, string> = {
    strong_fit:
      "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    possible_fit:
      "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    weak_fit:
      "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
    needs_more_info:
      "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300",
  };
  const labels: Record<AIRecommendation, string> = {
    strong_fit: "Strong fit",
    possible_fit: "Possible fit",
    weak_fit: "Weak fit",
    needs_more_info: "Needs more info",
  };
  if (!value) {
    return (
      <span className="inline-flex items-center rounded-full bg-muted/60 px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
        —
      </span>
    );
  }
  const knownValue =
    value && (value as AIRecommendation) in labels
      ? (value as AIRecommendation)
      : null;
  if (!knownValue) {
    return (
      <span className="inline-flex items-center rounded-full border border-border/60 bg-background/60 px-2 py-0.5 text-[11px] font-medium capitalize text-muted-foreground">
        {String(value).replace(/_/g, " ")}
      </span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold",
        tone[knownValue]
      )}
    >
      <Brain className="h-3 w-3" />
      {labels[knownValue]}
    </span>
  );
}
