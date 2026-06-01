"use client";

/**
 * HR assessment template management (Phase 2).
 *
 * Three views in one page:
 *
 *   List   — every template, filterable by job + active-only.
 *   Create — modal for the headline fields (job + title + clock).
 *   Edit   — drawer with question/choice CRUD, opens on row click.
 *
 * Question editing is intentionally choice-replace rather than
 * per-choice CRUD — once a candidate has answered, the choices lock
 * (the backend rejects with 409) and the only path forward is to
 * add a new question. The dialog surfaces this constraint to HR
 * before they hit Save.
 */

import * as React from "react";
import {
  AlertTriangle,
  ClipboardList,
  Loader2,
  Plus,
  Settings2,
  Trash2,
  X,
} from "lucide-react";

import { usePermission } from "@/components/auth/permission";
import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import {
  PERM_HR_ASSESSMENTS_MANAGE,
  PERM_HR_ASSESSMENTS_VIEW,
} from "@/lib/hr/permissions";
import type {
  Assessment,
  AssessmentSummary,
  JobOpening,
} from "@/lib/hr/types";
import { cn } from "@/lib/utils";


export default function HrAssessmentsPage() {
  const perms = usePermission();
  const canManage = perms.has(PERM_HR_ASSESSMENTS_MANAGE);
  const canView = perms.has(PERM_HR_ASSESSMENTS_VIEW);

  const [items, setItems] = React.useState<AssessmentSummary[]>([]);
  const [jobs, setJobs] = React.useState<JobOpening[]>([]);
  const [jobFilter, setJobFilter] = React.useState<string>("");
  const [activeOnly, setActiveOnly] = React.useState(true);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [showCreate, setShowCreate] = React.useState(false);
  const [editingId, setEditingId] = React.useState<number | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (jobFilter) qs.set("job_opening_id", jobFilter);
      if (activeOnly) qs.set("is_active", "true");
      const res = await hrApi.get<{ items: AssessmentSummary[] }>(
        `/hr/assessments${qs.toString() ? `?${qs}` : ""}`,
      );
      setItems(res.items);
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setLoading(false);
    }
  }, [jobFilter, activeOnly]);

  React.useEffect(() => {
    void load();
  }, [load]);

  // Jobs only need fetching once.
  React.useEffect(() => {
    void (async () => {
      try {
        const res = await hrApi.get<JobOpening[]>("/hr/jobs");
        setJobs(res);
      } catch {
        // Job fetch failures are non-fatal — the create dialog falls
        // back to a plain numeric ``job_opening_id`` input.
      }
    })();
  }, []);

  if (!canView) {
    return (
      <HrShell title="Assessments">
        <HrEmptyState
          title="No access"
          description="You don't have permission to view assessments."
        />
      </HrShell>
    );
  }

  return (
    <HrShell title="Assessments">
      <div className="space-y-4">
        <header className="flex flex-wrap items-end gap-3">
          <div className="flex-1 space-y-1">
            <h1 className="text-2xl font-semibold">Assessments</h1>
            <p className="text-sm text-muted-foreground">
              Template MCQ tests, send them to candidates from their
              drawer, and see scores roll back in.
            </p>
          </div>
          {canManage && (
            <Button type="button" onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4" />
              New template
            </Button>
          )}
        </header>

        <div className="flex flex-wrap items-end gap-3 rounded-xl border border-border/40 bg-card p-4">
          <div className="flex-1 min-w-[200px] space-y-1">
            <Label htmlFor="job-filter">Filter by job</Label>
            <Select
              id="job-filter"
              value={jobFilter}
              onChange={(e) => setJobFilter(e.target.value)}
            >
              <option value="">All jobs</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title} ({j.department})
                </option>
              ))}
            </Select>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(e) => setActiveOnly(e.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            Active only
          </label>
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

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading…
          </div>
        ) : items.length === 0 ? (
          <HrEmptyState
            title="No assessment templates yet"
            description={
              canManage
                ? "Click “New template” to create the first one."
                : "Ask an HR Admin to create a template."
            }
          />
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {items.map((it) => (
              <li
                key={it.id}
                className={cn(
                  "rounded-xl border border-border/50 bg-card p-4 transition hover:border-primary/40",
                  !it.is_active && "opacity-60",
                )}
              >
                <header className="mb-2 flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="truncate font-medium">{it.title}</h3>
                    <p className="text-xs text-muted-foreground">
                      Job #{it.job_opening_id} ·{" "}
                      {it.question_count} question
                      {it.question_count === 1 ? "" : "s"}
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setEditingId(it.id)}
                  >
                    <Settings2 className="h-3.5 w-3.5" />
                    Edit
                  </Button>
                </header>
                <dl className="grid grid-cols-3 gap-1 text-xs text-muted-foreground">
                  <div>
                    <dt>Time limit</dt>
                    <dd className="text-foreground">
                      {it.time_limit_minutes
                        ? `${it.time_limit_minutes} min`
                        : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt>Pass score</dt>
                    <dd className="text-foreground">
                      {it.passing_score ?? "—"}
                    </dd>
                  </div>
                  <div>
                    <dt>Submissions</dt>
                    <dd className="text-foreground">{it.submission_count}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
        )}
      </div>

      {showCreate && (
        <CreateDialog
          jobs={jobs}
          onClose={() => setShowCreate(false)}
          onCreated={(newId) => {
            setShowCreate(false);
            void load();
            setEditingId(newId);
          }}
        />
      )}
      {editingId !== null && (
        <EditDrawer
          id={editingId}
          canManage={canManage}
          onClose={() => {
            setEditingId(null);
            void load();
          }}
        />
      )}
    </HrShell>
  );
}


// ---------------------------------------------------------------------------
// Create dialog — minimal headline fields, then jump straight into edit
// ---------------------------------------------------------------------------


function CreateDialog({
  jobs,
  onClose,
  onCreated,
}: {
  jobs: JobOpening[];
  onClose: () => void;
  onCreated: (newId: number) => void;
}) {
  const [jobId, setJobId] = React.useState<string>(jobs[0]?.id?.toString() ?? "");
  const [title, setTitle] = React.useState("");
  const [instructions, setInstructions] = React.useState("");
  const [timeLimit, setTimeLimit] = React.useState<string>("");
  const [passingScore, setPassingScore] = React.useState<string>("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function save() {
    if (!jobId || !title.trim()) {
      setError("Pick a job and give the template a title.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        job_opening_id: Number(jobId),
        title: title.trim(),
        is_active: true,
      };
      if (instructions.trim()) body.instructions = instructions.trim();
      if (timeLimit) body.time_limit_minutes = Number(timeLimit);
      if (passingScore !== "") body.passing_score = Number(passingScore);
      const created = await hrApi.post<Assessment>("/hr/assessments", body);
      onCreated(created.id);
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="New assessment template" onClose={onClose}>
      <div className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor="c-job">Job opening</Label>
          <Select
            id="c-job"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
          >
            <option value="">Pick a job…</option>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.title} ({j.department})
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="c-title">Title</Label>
          <Input
            id="c-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="c-instr">Instructions (optional)</Label>
          <Textarea
            id="c-instr"
            rows={4}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label htmlFor="c-time">Time limit (min)</Label>
            <Input
              id="c-time"
              type="number"
              min={1}
              max={600}
              value={timeLimit}
              onChange={(e) => setTimeLimit(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="c-pass">Passing score</Label>
            <Input
              id="c-pass"
              type="number"
              min={0}
              value={passingScore}
              onChange={(e) => setPassingScore(e.target.value)}
            />
          </div>
        </div>
        {error && (
          <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
            <span>{error}</span>
          </div>
        )}
        <Button type="button" className="w-full" disabled={busy} onClick={save}>
          {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Create & continue
        </Button>
      </div>
    </Modal>
  );
}


// ---------------------------------------------------------------------------
// Edit drawer — title/clock + question CRUD
// ---------------------------------------------------------------------------


function EditDrawer({
  id,
  canManage,
  onClose,
}: {
  id: number;
  canManage: boolean;
  onClose: () => void;
}) {
  const [tpl, setTpl] = React.useState<Assessment | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await hrApi.get<Assessment>(`/hr/assessments/${id}`);
      setTpl(data);
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function patchHeadline(payload: Partial<Assessment>) {
    try {
      await hrApi.patch(`/hr/assessments/${id}`, payload);
      await load();
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  async function deleteTemplate() {
    if (!confirm("Delete this template?")) return;
    try {
      await hrApi.delete(`/hr/assessments/${id}`);
      onClose();
    } catch (err) {
      alert((err as HrApiError).message);
    }
  }

  async function deleteQuestion(qid: number) {
    if (!confirm("Delete this question?")) return;
    try {
      await hrApi.delete(`/hr/assessments/${id}/questions/${qid}`);
      await load();
    } catch (err) {
      alert((err as HrApiError).message);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex"
    >
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="flex w-full max-w-2xl flex-col bg-background shadow-2xl">
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">Edit template</h2>
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
        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading…
            </div>
          ) : !tpl ? (
            <p className="text-sm text-muted-foreground">
              {error ?? "Template not found."}
            </p>
          ) : (
            <div className="space-y-6">
              {error && (
                <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">
                  <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
                  <span>{error}</span>
                </div>
              )}

              <HeadlineEditor
                tpl={tpl}
                canManage={canManage}
                onSave={patchHeadline}
                onDelete={deleteTemplate}
              />

              <QuestionsList
                tpl={tpl}
                canManage={canManage}
                onAdded={load}
                onUpdated={load}
                onDeleted={deleteQuestion}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


function HeadlineEditor({
  tpl,
  canManage,
  onSave,
  onDelete,
}: {
  tpl: Assessment;
  canManage: boolean;
  onSave: (p: Partial<Assessment>) => void;
  onDelete: () => void;
}) {
  const [title, setTitle] = React.useState(tpl.title);
  const [instructions, setInstructions] = React.useState(tpl.instructions ?? "");
  const [timeLimit, setTimeLimit] = React.useState<string>(
    tpl.time_limit_minutes?.toString() ?? "",
  );
  const [passingScore, setPassingScore] = React.useState<string>(
    tpl.passing_score?.toString() ?? "",
  );
  const [isActive, setIsActive] = React.useState(tpl.is_active);

  React.useEffect(() => {
    setTitle(tpl.title);
    setInstructions(tpl.instructions ?? "");
    setTimeLimit(tpl.time_limit_minutes?.toString() ?? "");
    setPassingScore(tpl.passing_score?.toString() ?? "");
    setIsActive(tpl.is_active);
  }, [tpl]);

  function save() {
    onSave({
      title,
      instructions: instructions || null,
      time_limit_minutes: timeLimit ? Number(timeLimit) : null,
      passing_score: passingScore !== "" ? Number(passingScore) : null,
      is_active: isActive,
    });
  }

  return (
    <section className="space-y-3 rounded-xl border border-border/40 bg-card p-4">
      <h3 className="text-sm font-semibold">Headline</h3>
      <div className="space-y-2">
        <Label htmlFor="e-title">Title</Label>
        <Input
          id="e-title"
          value={title}
          disabled={!canManage}
          onChange={(e) => setTitle(e.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="e-instr">Instructions</Label>
        <Textarea
          id="e-instr"
          rows={3}
          value={instructions}
          disabled={!canManage}
          onChange={(e) => setInstructions(e.target.value)}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="e-time">Time limit (min)</Label>
          <Input
            id="e-time"
            type="number"
            min={1}
            max={600}
            value={timeLimit}
            disabled={!canManage}
            onChange={(e) => setTimeLimit(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="e-pass">Passing score</Label>
          <Input
            id="e-pass"
            type="number"
            min={0}
            value={passingScore}
            disabled={!canManage}
            onChange={(e) => setPassingScore(e.target.value)}
          />
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={isActive}
          disabled={!canManage}
          onChange={(e) => setIsActive(e.target.checked)}
          className="h-4 w-4 accent-primary"
        />
        Template is active (can be sent)
      </label>
      {canManage && (
        <div className="flex justify-between">
          <Button type="button" variant="ghost" onClick={onDelete}>
            <Trash2 className="h-3.5 w-3.5" />
            Delete template
          </Button>
          <Button type="button" onClick={save}>
            Save headline
          </Button>
        </div>
      )}
    </section>
  );
}


function QuestionsList({
  tpl,
  canManage,
  onAdded,
  onUpdated,
  onDeleted,
}: {
  tpl: Assessment;
  canManage: boolean;
  onAdded: () => void;
  onUpdated: () => void;
  onDeleted: (qid: number) => void;
}) {
  const [showAdd, setShowAdd] = React.useState(false);
  const [editingQ, setEditingQ] = React.useState<number | null>(null);

  return (
    <section className="space-y-3 rounded-xl border border-border/40 bg-card p-4">
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          Questions ({tpl.questions.length}, {tpl.total_points} pts total)
        </h3>
        {canManage && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setShowAdd(true)}
          >
            <Plus className="h-3.5 w-3.5" />
            Add question
          </Button>
        )}
      </header>

      {tpl.questions.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No questions yet. Add at least two — each with two or more
          choices and at least one correct answer.
        </p>
      ) : (
        <ul className="space-y-3">
          {tpl.questions.map((q, idx) => (
            <li
              key={q.id}
              className="rounded-md border border-border/50 p-3"
            >
              <header className="mb-2 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">
                    Q{idx + 1} · {q.points} pt{q.points === 1 ? "" : "s"} ·{" "}
                    {QUESTION_TYPE_LABEL[q.type] ?? q.type}
                  </p>
                  <p className="text-sm">{q.text}</p>
                </div>
                {canManage && (
                  <div className="flex gap-1">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditingQ(q.id)}
                    >
                      Edit
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => onDeleted(q.id)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                )}
              </header>
              <ul className="space-y-1 text-sm">
                {q.choices.map((c) => (
                  <li key={c.id} className="flex items-center gap-2">
                    <span
                      className={cn(
                        "inline-block h-2 w-2 rounded-full",
                        c.is_correct ? "bg-emerald-500" : "bg-muted-foreground/30",
                      )}
                      aria-hidden
                    />
                    <span
                      className={cn(
                        c.is_correct && "font-medium text-emerald-700 dark:text-emerald-300",
                      )}
                    >
                      {c.text}
                    </span>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}

      {showAdd && (
        <QuestionEditor
          mode="add"
          assessmentId={tpl.id}
          onClose={() => setShowAdd(false)}
          onSaved={() => {
            setShowAdd(false);
            onAdded();
          }}
        />
      )}
      {editingQ !== null && (
        <QuestionEditor
          mode="edit"
          assessmentId={tpl.id}
          question={tpl.questions.find((q) => q.id === editingQ)}
          onClose={() => setEditingQ(null)}
          onSaved={() => {
            setEditingQ(null);
            onUpdated();
          }}
        />
      )}
    </section>
  );
}


// ---------------------------------------------------------------------------
// Question editor (add + edit)
// ---------------------------------------------------------------------------


const QUESTION_TYPE_LABEL: Record<string, string> = {
  short_text: "Short text",
  long_text: "Paragraph",
  date: "Date",
  checkbox: "Checkbox",
  single_choice: "Dropdown",
  multi_choice: "Multiple choice",
  attachment: "Attachment",
};

function numStr(v: unknown): string {
  return typeof v === "number" ? String(v) : "";
}
function strVal(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function QuestionEditor({
  mode,
  assessmentId,
  question,
  onClose,
  onSaved,
}: {
  mode: "add" | "edit";
  assessmentId: number;
  question?: Assessment["questions"][number];
  onClose: () => void;
  onSaved: () => void;
}) {
  const cfg = (question?.config ?? {}) as Record<string, unknown>;
  const [text, setText] = React.useState(question?.text ?? "");
  const [type, setType] = React.useState<string>(question?.type ?? "multi_choice");
  const [helpText, setHelpText] = React.useState(question?.help_text ?? "");
  const [isRequired, setIsRequired] = React.useState(
    question?.is_required ?? true,
  );
  const [points, setPoints] = React.useState<string>(
    question?.points?.toString() ?? "1",
  );
  // Type-specific config fields (only the relevant ones are sent).
  const [minLen, setMinLen] = React.useState(numStr(cfg.min_length));
  const [maxLen, setMaxLen] = React.useState(numStr(cfg.max_length));
  const [placeholder, setPlaceholder] = React.useState(strVal(cfg.placeholder));
  const [minDate, setMinDate] = React.useState(strVal(cfg.min_date));
  const [maxDate, setMaxDate] = React.useState(strVal(cfg.max_date));
  const [checkboxLabel, setCheckboxLabel] = React.useState(strVal(cfg.label));
  const [choices, setChoices] = React.useState<
    Array<{ text: string; is_correct: boolean }>
  >(
    question?.choices.map((c) => ({ text: c.text, is_correct: c.is_correct })) ?? [
      { text: "", is_correct: false },
      { text: "", is_correct: false },
    ],
  );
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const isChoice = type === "single_choice" || type === "multi_choice";

  function addChoice() {
    setChoices((prev) => [...prev, { text: "", is_correct: false }]);
  }
  function removeChoice(i: number) {
    setChoices((prev) => prev.filter((_, idx) => idx !== i));
  }
  function update(i: number, patch: Partial<{ text: string; is_correct: boolean }>) {
    setChoices((prev) => prev.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  }

  function buildConfig(): Record<string, unknown> {
    const c: Record<string, unknown> = {};
    if (type === "short_text" || type === "long_text") {
      if (minLen) c.min_length = Number(minLen);
      if (maxLen) c.max_length = Number(maxLen);
      if (placeholder.trim()) c.placeholder = placeholder.trim();
    } else if (type === "date") {
      if (minDate) c.min_date = minDate;
      if (maxDate) c.max_date = maxDate;
    } else if (type === "checkbox") {
      if (checkboxLabel.trim()) c.label = checkboxLabel.trim();
    }
    return c;
  }

  async function save() {
    if (!text.trim()) {
      setError("Question text required.");
      return;
    }
    let cleaned: Array<{ text: string; is_correct: boolean }> = [];
    if (isChoice) {
      cleaned = choices
        .map((c) => ({ text: c.text.trim(), is_correct: c.is_correct }))
        .filter((c) => c.text);
      if (cleaned.length < 2) {
        setError("At least two choices required.");
        return;
      }
      if (!cleaned.some((c) => c.is_correct)) {
        setError("Mark at least one choice as correct.");
        return;
      }
    }

    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        text: text.trim(),
        type,
        help_text: helpText.trim() || null,
        is_required: isRequired,
        config: buildConfig(),
        points: Number(points) || 1,
      };
      if (isChoice) body.choices = cleaned;
      if (mode === "add") {
        await hrApi.post(`/hr/assessments/${assessmentId}/questions`, body);
      } else if (question) {
        await hrApi.patch(
          `/hr/assessments/${assessmentId}/questions/${question.id}`,
          body,
        );
      }
      onSaved();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={mode === "add" ? "Add question" : "Edit question"}
      onClose={onClose}
    >
      <div className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor="q-type">Question type</Label>
          <Select
            id="q-type"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            <option value="short_text">Short text</option>
            <option value="long_text">Paragraph (long text)</option>
            <option value="date">Date</option>
            <option value="checkbox">Checkbox (acknowledgement)</option>
            <option value="single_choice">Dropdown (single choice)</option>
            <option value="multi_choice">Multiple choice</option>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="q-text">Question</Label>
          <Textarea
            id="q-text"
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="q-help">Help text (optional)</Label>
          <Input
            id="q-help"
            value={helpText}
            onChange={(e) => setHelpText(e.target.value)}
            placeholder="Shown under the question"
          />
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isRequired}
              onChange={(e) => setIsRequired(e.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            Required
          </label>
          <div className="space-y-1">
            <Label htmlFor="q-points">Points</Label>
            <Input
              id="q-points"
              type="number"
              min={1}
              max={100}
              value={points}
              onChange={(e) => setPoints(e.target.value)}
              className="w-24"
            />
          </div>
        </div>

        {/* Type-specific config */}
        {(type === "short_text" || type === "long_text") && (
          <div className="grid grid-cols-2 gap-2 rounded-md border border-border/60 p-3">
            <div className="space-y-1">
              <Label htmlFor="q-minlen">Min length</Label>
              <Input
                id="q-minlen"
                type="number"
                min={0}
                value={minLen}
                onChange={(e) => setMinLen(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="q-maxlen">Max length</Label>
              <Input
                id="q-maxlen"
                type="number"
                min={0}
                value={maxLen}
                onChange={(e) => setMaxLen(e.target.value)}
              />
            </div>
            <div className="col-span-2 space-y-1">
              <Label htmlFor="q-ph">Placeholder</Label>
              <Input
                id="q-ph"
                value={placeholder}
                onChange={(e) => setPlaceholder(e.target.value)}
              />
            </div>
          </div>
        )}
        {type === "date" && (
          <div className="grid grid-cols-2 gap-2 rounded-md border border-border/60 p-3">
            <div className="space-y-1">
              <Label htmlFor="q-mind">Earliest date</Label>
              <Input
                id="q-mind"
                type="date"
                value={minDate}
                onChange={(e) => setMinDate(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="q-maxd">Latest date</Label>
              <Input
                id="q-maxd"
                type="date"
                value={maxDate}
                onChange={(e) => setMaxDate(e.target.value)}
              />
            </div>
          </div>
        )}
        {type === "checkbox" && (
          <div className="space-y-1 rounded-md border border-border/60 p-3">
            <Label htmlFor="q-cblabel">Checkbox label</Label>
            <Input
              id="q-cblabel"
              value={checkboxLabel}
              onChange={(e) => setCheckboxLabel(e.target.value)}
              placeholder="e.g. I confirm the details are accurate"
            />
          </div>
        )}
        {isChoice && (
        <div className="space-y-2">
          <Label>
            {type === "single_choice"
              ? "Options (tick the correct one)"
              : "Choices (tick the correct ones)"}
          </Label>
          {choices.map((c, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={c.is_correct}
                onChange={(e) => update(i, { is_correct: e.target.checked })}
                className="h-4 w-4 accent-primary"
                aria-label={`Choice ${i + 1} correct`}
              />
              <Input
                value={c.text}
                onChange={(e) => update(i, { text: e.target.value })}
                placeholder={`Choice ${i + 1}`}
              />
              {choices.length > 2 && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => removeChoice(i)}
                  aria-label="Remove"
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              )}
            </div>
          ))}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={addChoice}
          >
            <Plus className="h-3 w-3" />
            Add choice
          </Button>
        </div>
        )}
        {mode === "edit" && isChoice && (
          <p className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-300">
            <ClipboardList className="-mt-0.5 mr-1 inline h-3 w-3" />
            Once any candidate has answered, choices lock — adding a
            new question is the only path forward.
          </p>
        )}
        {error && (
          <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/10 p-2 text-sm text-rose-700 dark:text-rose-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
            <span>{error}</span>
          </div>
        )}
        <Button type="button" className="w-full" disabled={busy} onClick={save}>
          {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save question
        </Button>
      </div>
    </Modal>
  );
}


// ---------------------------------------------------------------------------
// Modal shell
// ---------------------------------------------------------------------------


function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
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
          <h3 className="text-base font-semibold">{title}</h3>
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
        {children}
      </div>
    </div>
  );
}
