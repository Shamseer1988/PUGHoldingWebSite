"use client";

import * as React from "react";

import type { AssessmentQuestion } from "@/lib/public-api-client";
import type { FieldAnswer } from "@/lib/assessment-validation";

/**
 * Renders the right input control for a candidate assessment question
 * based on its `type` (short_text · long_text · date · checkbox ·
 * single_choice · multi_choice). Shares one FieldShell for the label,
 * required marker, help text and error.
 */

const INPUT_CLASS =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

interface Props {
  question: AssessmentQuestion;
  index: number;
  answer: FieldAnswer;
  error?: string | null;
  onChange: (next: FieldAnswer) => void;
}

export function AssessmentField({
  question,
  index,
  answer,
  error,
  onChange,
}: Props) {
  const q = question;
  const cfg = (q.config ?? {}) as Record<string, unknown>;
  const fieldId = `q-${q.id}`;
  const labelText = `${index + 1}. ${q.text}`;

  function control() {
    switch (q.type) {
      case "short_text":
        return (
          <input
            id={fieldId}
            type="text"
            className={INPUT_CLASS}
            value={answer.text}
            maxLength={asNumber(cfg.max_length) ?? undefined}
            placeholder={asString(cfg.placeholder) ?? undefined}
            onChange={(e) => onChange({ ...answer, text: e.target.value })}
          />
        );
      case "long_text":
        return (
          <textarea
            id={fieldId}
            rows={4}
            className={INPUT_CLASS}
            value={answer.text}
            maxLength={asNumber(cfg.max_length) ?? undefined}
            placeholder={asString(cfg.placeholder) ?? undefined}
            onChange={(e) => onChange({ ...answer, text: e.target.value })}
          />
        );
      case "date":
        return (
          <input
            id={fieldId}
            type="date"
            className={INPUT_CLASS}
            value={answer.date}
            min={asString(cfg.min_date) ?? undefined}
            max={asString(cfg.max_date) ?? undefined}
            onChange={(e) => onChange({ ...answer, date: e.target.value })}
          />
        );
      case "checkbox":
        return (
          <label className="flex items-center gap-2 text-sm">
            <input
              id={fieldId}
              type="checkbox"
              className="h-4 w-4 rounded border-input"
              checked={answer.checked}
              onChange={(e) => onChange({ ...answer, checked: e.target.checked })}
            />
            {asString(cfg.label) ?? "I confirm"}
          </label>
        );
      case "single_choice":
        return (
          <select
            id={fieldId}
            className={INPUT_CLASS}
            value={answer.choiceIds[0] ?? ""}
            onChange={(e) =>
              onChange({
                ...answer,
                choiceIds: e.target.value ? [Number(e.target.value)] : [],
              })
            }
          >
            <option value="">Select an option…</option>
            {q.choices.map((c) => (
              <option key={c.id} value={c.id}>
                {c.text}
              </option>
            ))}
          </select>
        );
      case "multi_choice":
        return (
          <div className="space-y-2">
            {q.choices.map((c) => {
              const picked = answer.choiceIds.includes(c.id);
              return (
                <label
                  key={c.id}
                  className="flex items-center gap-2 rounded-md border border-input px-3 py-2 text-sm"
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-input"
                    checked={picked}
                    onChange={(e) => {
                      const next = new Set(answer.choiceIds);
                      if (e.target.checked) next.add(c.id);
                      else next.delete(c.id);
                      onChange({ ...answer, choiceIds: Array.from(next) });
                    }}
                  />
                  {c.text}
                </label>
              );
            })}
          </div>
        );
      case "attachment":
        return (
          <p className="rounded-md border border-dashed border-input px-3 py-2 text-xs text-muted-foreground">
            File upload isn&apos;t available yet for this question.
          </p>
        );
      default:
        return null;
    }
  }

  // checkbox / multi_choice carry their own labels, so the shell renders
  // the question as a group label rather than a `for=` label.
  const labelAsGroup = q.type === "checkbox" || q.type === "multi_choice";

  return (
    <div className="space-y-2">
      {labelAsGroup ? (
        <p className="text-sm font-medium">
          {labelText}
          {q.is_required && <RequiredMark />}
        </p>
      ) : (
        <label htmlFor={fieldId} className="block text-sm font-medium">
          {labelText}
          {q.is_required && <RequiredMark />}
        </label>
      )}
      {q.help_text && (
        <p className="text-xs text-muted-foreground">{q.help_text}</p>
      )}
      {control()}
      {error && (
        <p role="alert" className="text-xs text-rose-600 dark:text-rose-400">
          {error}
        </p>
      )}
    </div>
  );
}

function RequiredMark() {
  return (
    <span className="ml-0.5 text-rose-600" aria-label="required">
      *
    </span>
  );
}

function asNumber(v: unknown): number | null {
  return typeof v === "number" ? v : null;
}
function asString(v: unknown): string | null {
  return typeof v === "string" ? v : null;
}
