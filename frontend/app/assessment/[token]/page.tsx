"use client";

/**
 * Candidate-facing assessment page (HR Phase 2).
 *
 * Three states, one component:
 *
 *   verify    — single-input identity check (email / mobile / DOB).
 *               On success, mints a session JWT we stash in component
 *               state (deliberately NOT localStorage — a kept tab is
 *               fine, a closed one is gone, which matches the time-
 *               limited nature of the test).
 *   form      — fetches the question bundle, renders checkboxes,
 *               shows a watermark and (if set) a count-down timer.
 *   done      — final score / pass-fail ack.
 *
 * The page sits outside the ``(public)`` layout group so the
 * branded chrome is minimal (logo + footer note only) — the
 * candidate's focus should be the test, not the site nav.
 */

import * as React from "react";
import { useParams } from "next/navigation";
import Image from "next/image";
import { AlertTriangle, CheckCircle2, Loader2, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import {
  AssessmentSubmissionAck,
  PublicAssessment,
  PublicApiError,
  fetchAssessment,
  submitAssessment,
  verifyAssessment,
} from "@/lib/public-api-client";


type Stage = "verify" | "form" | "done";


// ---------------------------------------------------------------------------
// Watermark (security comfort copy — candidate name + email tiled at low
// opacity across the form area so a screenshot circulated outside of
// PUG carries the identity of who took the test).
// ---------------------------------------------------------------------------


function Watermark({ label }: { label: string }) {
  // The watermark sits in a fixed full-viewport layer, pointer-events
  // disabled so it never intercepts clicks. We tile via a CSS grid
  // rather than ::before pseudo-elements so it works without any
  // extra CSS files.
  const rows = 8;
  const cols = 4;
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
    >
      <div
        className="absolute inset-0 grid"
        style={{
          gridTemplateColumns: `repeat(${cols}, 1fr)`,
          gridTemplateRows: `repeat(${rows}, 1fr)`,
        }}
      >
        {Array.from({ length: rows * cols }, (_, i) => (
          <div
            key={i}
            className="flex items-center justify-center text-center text-muted-foreground/30"
            style={{ transform: "rotate(-22deg)" }}
          >
            <span className="text-xs font-medium uppercase tracking-wider">
              {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Stage 1 — identity verification
// ---------------------------------------------------------------------------


function VerifyForm({
  onVerified,
}: {
  onVerified: (sessionToken: string, matched: string) => void;
}) {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";

  const [value, setValue] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!value.trim()) {
      setError("Enter your email, mobile, or date of birth to begin.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await verifyAssessment(token, value.trim());
      onVerified(res.session_token, res.matched_field);
    } catch (err) {
      const apiErr = err as PublicApiError;
      setError(
        apiErr.status === 401
          ? "We couldn't match that. Please double-check and try again."
          : apiErr.message,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="relative z-10 w-full max-w-md rounded-2xl border border-border/40 bg-card/95 p-8 shadow-2xl backdrop-blur"
      noValidate
    >
      <div className="mb-6 flex items-center gap-2 text-sm text-muted-foreground">
        <ShieldCheck className="h-4 w-4" />
        <span>Confirm your identity to begin.</span>
      </div>

      <h1 className="mb-2 text-2xl font-semibold">Welcome.</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Enter <strong>any one</strong> of these to begin: your registered
        email, mobile number, or date of birth (YYYY-MM-DD or DD/MM/YYYY).
      </p>

      <div className="space-y-2">
        <Label htmlFor="identity">Email / Mobile / Date of birth</Label>
        <Input
          id="identity"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          autoComplete="off"
          autoFocus
          disabled={busy}
        />
      </div>

      {error && (
        <div
          role="alert"
          className="mt-4 flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
          <span>{error}</span>
        </div>
      )}

      <Button type="submit" className="mt-6 w-full" disabled={busy}>
        {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        Begin assessment
      </Button>
    </form>
  );
}


// ---------------------------------------------------------------------------
// Stage 2 — the test itself
// ---------------------------------------------------------------------------


type AnswerMap = Record<number, Set<number>>;


function AssessmentForm({
  sessionToken,
  onSubmitted,
}: {
  sessionToken: string;
  onSubmitted: (ack: AssessmentSubmissionAck) => void;
}) {
  const [bundle, setBundle] = React.useState<PublicAssessment | null>(null);
  const [answers, setAnswers] = React.useState<AnswerMap>({});
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  // Initial fetch.
  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await fetchAssessment(sessionToken);
        if (!cancelled) setBundle(data);
      } catch (err) {
        if (!cancelled) {
          setLoadError(
            (err as PublicApiError).message ?? "Could not load the assessment.",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  // Count-down clock — only renders when the bundle has a deadline.
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    if (!bundle?.submit_deadline) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [bundle?.submit_deadline]);

  if (loadError) {
    return (
      <div className="relative z-10 w-full max-w-md rounded-xl border border-rose-500/30 bg-card/95 p-6 text-sm text-rose-700 shadow-lg backdrop-blur dark:text-rose-200">
        <AlertTriangle className="mb-2 h-5 w-5" />
        <p>{loadError}</p>
      </div>
    );
  }
  if (!bundle) {
    return (
      <div className="relative z-10 flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading your assessment…
      </div>
    );
  }

  const watermarkLabel = `${bundle.candidate_name}${
    bundle.candidate_email ? ` · ${bundle.candidate_email}` : ""
  }`;
  const deadlineMs = bundle.submit_deadline
    ? new Date(bundle.submit_deadline).getTime()
    : null;
  const remainingSec =
    deadlineMs !== null ? Math.max(0, Math.floor((deadlineMs - now) / 1000)) : null;

  function toggle(questionId: number, choiceId: number) {
    setAnswers((prev) => {
      const next = { ...prev };
      const cur = new Set(next[questionId] ?? []);
      if (cur.has(choiceId)) cur.delete(choiceId);
      else cur.add(choiceId);
      next[questionId] = cur;
      return next;
    });
  }

  async function submit() {
    if (!bundle) return;
    const questions = bundle.questions;
    setBusy(true);
    setSubmitError(null);
    try {
      const payload = Object.entries(answers).map(([qid, cids]) => ({
        question_id: Number(qid),
        selected_choice_ids: Array.from(cids),
      }));
      // Also include questions with no answers, so the backend records
      // an empty selection (counts as "wrong" under all-or-nothing
      // scoring) — otherwise the gap is indistinguishable from "didn't
      // load the question at all".
      for (const q of questions) {
        if (!(q.id in answers)) {
          payload.push({ question_id: q.id, selected_choice_ids: [] });
        }
      }
      const ack = await submitAssessment(sessionToken, payload);
      onSubmitted(ack);
    } catch (err) {
      setSubmitError((err as PublicApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Watermark label={watermarkLabel} />
      <div className="relative z-10 w-full max-w-3xl space-y-6">
        <header className="rounded-xl border border-border/40 bg-card/95 p-5 shadow-md backdrop-blur">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold">{bundle.title}</h1>
              {bundle.instructions && (
                <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
                  {bundle.instructions}
                </p>
              )}
            </div>
            {remainingSec !== null && (
              <div
                className={cn(
                  "rounded-md border px-3 py-2 text-sm tabular-nums",
                  remainingSec < 60
                    ? "border-rose-500/50 bg-rose-500/10 text-rose-700 dark:text-rose-200"
                    : "border-border/60",
                )}
                aria-label="Time remaining"
              >
                {formatHms(remainingSec)}
              </div>
            )}
          </div>
        </header>

        {bundle.questions.map((q, idx) => (
          <section
            key={q.id}
            className="rounded-xl border border-border/40 bg-card/95 p-5 shadow-md backdrop-blur"
          >
            <h2 className="mb-3 text-base font-medium">
              <span className="text-muted-foreground">
                Q{idx + 1} · {q.points} pt{q.points === 1 ? "" : "s"}
              </span>
              <span className="ml-2 whitespace-pre-wrap">{q.text}</span>
            </h2>
            <ul className="space-y-2">
              {q.choices.map((c) => {
                const checked = (answers[q.id]?.has(c.id)) ?? false;
                return (
                  <li key={c.id}>
                    <label
                      className={cn(
                        "flex cursor-pointer items-start gap-3 rounded-md border p-3 transition",
                        checked
                          ? "border-primary/60 bg-primary/5"
                          : "border-border/50 hover:bg-muted/50",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(q.id, c.id)}
                        className="mt-1 h-4 w-4 accent-primary"
                      />
                      <span className="text-sm">{c.text}</span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}

        {submitError && (
          <div
            role="alert"
            className="relative z-10 flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
            <span>{submitError}</span>
          </div>
        )}

        <div className="flex justify-end">
          <Button onClick={submit} disabled={busy} size="lg">
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Submit answers
          </Button>
        </div>
      </div>
    </>
  );
}


function formatHms(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}


// ---------------------------------------------------------------------------
// Stage 3 — submission ack
// ---------------------------------------------------------------------------


function Done({ ack }: { ack: AssessmentSubmissionAck }) {
  const pct = ack.max_score > 0 ? Math.round((ack.score / ack.max_score) * 100) : 0;
  return (
    <div className="relative z-10 w-full max-w-md rounded-2xl border border-border/40 bg-card/95 p-8 text-center shadow-2xl backdrop-blur">
      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/15">
        <CheckCircle2 className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
      </div>
      <h1 className="mb-2 text-2xl font-semibold">Submitted</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Thanks — your responses have been recorded. The HR team will be in
        touch with the next step.
      </p>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-md border border-border/40 p-3">
          <dt className="text-xs uppercase text-muted-foreground">Score</dt>
          <dd className="text-lg font-semibold">
            {ack.score} / {ack.max_score}
          </dd>
        </div>
        <div className="rounded-md border border-border/40 p-3">
          <dt className="text-xs uppercase text-muted-foreground">Percentage</dt>
          <dd className="text-lg font-semibold">{pct}%</dd>
        </div>
      </dl>
      {ack.passed !== null && (
        <p
          className={cn(
            "mt-6 rounded-md p-3 text-sm font-medium",
            ack.passed
              ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
              : "bg-amber-500/10 text-amber-700 dark:text-amber-300",
          )}
        >
          {ack.passed
            ? "You met the passing score."
            : "You did not meet the passing score."}
        </p>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Page wrapper
// ---------------------------------------------------------------------------


export default function AssessmentPage() {
  const [stage, setStage] = React.useState<Stage>("verify");
  const [sessionToken, setSessionToken] = React.useState<string | null>(null);
  const [ack, setAck] = React.useState<AssessmentSubmissionAck | null>(null);

  return (
    <div className="relative min-h-screen bg-gradient-to-b from-background via-muted/30 to-background">
      {/* Slim branded header — logo + a thin top border. No nav, no
          menu, no link out. Anchored top-left so it never obscures the
          assessment content. */}
      <header className="relative z-20 border-b border-border/40 bg-background/90 px-5 py-3 backdrop-blur">
        <Image
          src="/images/site_logo.svg"
          alt="Paris United Group Holding"
          width={140}
          height={36}
          priority
        />
      </header>

      <main className="relative z-10 flex flex-col items-center px-4 py-12">
        {stage === "verify" && (
          <VerifyForm
            onVerified={(tok) => {
              setSessionToken(tok);
              setStage("form");
            }}
          />
        )}
        {stage === "form" && sessionToken && (
          <AssessmentForm
            sessionToken={sessionToken}
            onSubmitted={(a) => {
              setAck(a);
              setStage("done");
            }}
          />
        )}
        {stage === "done" && ack && <Done ack={ack} />}
      </main>

      <footer className="relative z-10 mt-8 border-t border-border/30 px-5 py-4 text-center text-xs text-muted-foreground">
        © Paris United Group Holding · Confidential assessment
      </footer>
    </div>
  );
}
