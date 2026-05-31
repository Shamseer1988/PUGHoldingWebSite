"use client";

import * as React from "react";
import { CheckCircle2, Loader2, X, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type { Assessment, AssessmentSubmission } from "@/lib/hr/types";

/**
 * Submission review drawer (acceptance criterion 6).
 *
 * Reuses ``GET /hr/assessments/invites/{invite_id}/submission`` for the
 * candidate's answers and ``GET /hr/assessments/{assessment_id}`` for
 * the question paper, then renders each question with the candidate's
 * selected choices, per-question correctness, and the total score.
 *
 * The full pass/fail-per-question + override-score + approve-&-advance
 * controls land with the assessment review engine; this drawer is the
 * read surface those build on.
 */

interface Props {
  inviteId: number;
  assessmentId: number;
  candidateName?: string | null;
  onClose: () => void;
}

export function SubmissionReviewDrawer({
  inviteId,
  assessmentId,
  candidateName,
  onClose,
}: Props) {
  const [submission, setSubmission] =
    React.useState<AssessmentSubmission | null>(null);
  const [assessment, setAssessment] = React.useState<Assessment | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      hrApi.get<AssessmentSubmission>(
        `/hr/assessments/invites/${inviteId}/submission`,
      ),
      hrApi.get<Assessment>(`/hr/assessments/${assessmentId}`),
    ])
      .then(([sub, asm]) => {
        if (cancelled) return;
        setSubmission(sub);
        setAssessment(asm);
      })
      .catch((err: HrApiError) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [inviteId, assessmentId]);

  const answersByQuestion = React.useMemo(() => {
    const map = new Map<number, AssessmentSubmission["answers"][number]>();
    submission?.answers.forEach((a) => map.set(a.question_id, a));
    return map;
  }, [submission]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Submission review"
      className="fixed inset-0 z-50 flex justify-end bg-background/60 backdrop-blur-sm"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
        aria-label="Close review"
        tabIndex={-1}
      />
      <aside className="relative flex h-full w-full max-w-2xl flex-col border-l border-border/60 bg-background shadow-2xl">
        <header className="flex items-center justify-between gap-3 border-b border-border/60 px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold">
              {candidateName ?? "Submission review"}
            </h2>
            <p className="truncate text-xs text-muted-foreground">
              {assessment?.title ?? "Assessment"}
            </p>
          </div>
          <Button
            size="icon"
            variant="ghost"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {loading ? (
            <p className="text-sm text-muted-foreground">
              <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
              Loading submission…
            </p>
          ) : error ? (
            <div
              role="alert"
              className="rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
            >
              {error}
            </div>
          ) : submission && assessment ? (
            <>
              {/* Score summary */}
              <div className="flex items-center justify-between rounded-xl border border-border/60 bg-card p-4">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Score
                  </p>
                  <p className="text-2xl font-semibold tabular-nums">
                    {submission.score ?? "—"}
                    <span className="text-base text-muted-foreground">
                      {" / "}
                      {submission.max_score ?? "—"}
                    </span>
                  </p>
                </div>
                <PassPill passed={submission.passed} />
              </div>

              {/* Questions + answers */}
              {assessment.questions.map((q, idx) => {
                const answer = answersByQuestion.get(q.id);
                const selected = new Set(answer?.selected_choice_ids ?? []);
                return (
                  <div
                    key={q.id}
                    className="rounded-xl border border-border/60 bg-card p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-medium">
                        <span className="text-muted-foreground">
                          Q{idx + 1}.
                        </span>{" "}
                        {q.text}
                      </p>
                      <CorrectnessPill isCorrect={answer?.is_correct ?? null} />
                    </div>
                    <ul className="mt-3 space-y-1.5">
                      {q.choices.map((ch) => {
                        const picked = selected.has(ch.id);
                        return (
                          <li
                            key={ch.id}
                            className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs ${
                              ch.is_correct
                                ? "border-emerald-500/30 bg-emerald-500/10"
                                : picked
                                ? "border-rose-500/30 bg-rose-500/10"
                                : "border-border/40"
                            }`}
                          >
                            <span className="font-mono text-muted-foreground">
                              {picked ? "☑" : "☐"}
                            </span>
                            <span className="flex-1">{ch.text}</span>
                            {ch.is_correct && (
                              <span className="text-[10px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
                                Correct
                              </span>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                );
              })}

              <p className="rounded-lg border border-dashed border-border/60 bg-muted/30 p-3 text-xs text-muted-foreground">
                Objective questions are auto-graded. Pass/fail-per-question,
                reviewer notes, score override and approve-&-advance arrive with
                the assessment review engine.
              </p>
            </>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

function PassPill({ passed }: { passed: boolean | null }) {
  if (passed === null) {
    return (
      <span className="inline-flex items-center rounded-full border border-border/60 bg-muted/50 px-2.5 py-1 text-xs font-medium text-muted-foreground">
        Not scored
      </span>
    );
  }
  return passed ? (
    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300">
      <CheckCircle2 className="h-3.5 w-3.5" /> Passed
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-xs font-medium text-rose-700 dark:text-rose-300">
      <XCircle className="h-3.5 w-3.5" /> Failed
    </span>
  );
}

function CorrectnessPill({ isCorrect }: { isCorrect: boolean | null }) {
  if (isCorrect === null) return null;
  return isCorrect ? (
    <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
      Correct
    </span>
  ) : (
    <span className="shrink-0 rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-700 dark:text-rose-300">
      Incorrect
    </span>
  );
}
