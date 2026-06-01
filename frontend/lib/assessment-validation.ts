/**
 * Candidate-side assessment answer model + per-type validation.
 *
 * Mirrors the backend's typed-answer contract so the public form can
 * validate required/format rules client-side and serialise each answer
 * into the `{ question_id, selected_choice_ids, value }` shape the
 * submit endpoint expects. Kept dependency-free (no Zod) and pure so it
 * unit-tests without a DOM.
 */

export const CHOICE_TYPES = ["single_choice", "multi_choice"] as const;

export interface FieldQuestion {
  id: number;
  text: string;
  type: string;
  is_required: boolean;
  config: Record<string, unknown>;
  choices: { id: number; text: string; order_index: number }[];
}

/** Per-question working state held by the form. Only the field relevant
 *  to the question's type is meaningful, but we carry all of them so
 *  switching never loses input. */
export interface FieldAnswer {
  choiceIds: number[];
  text: string;
  date: string;
  checked: boolean;
}

export function emptyAnswer(): FieldAnswer {
  return { choiceIds: [], text: "", date: "", checked: false };
}

export function isChoiceType(type: string): boolean {
  return (CHOICE_TYPES as readonly string[]).includes(type);
}

function num(config: Record<string, unknown>, key: string): number | null {
  const v = config[key];
  return typeof v === "number" ? v : null;
}

function str(config: Record<string, unknown>, key: string): string | null {
  const v = config[key];
  return typeof v === "string" ? v : null;
}

/** Whether a (required) question was left effectively blank. */
export function answerIsEmpty(q: FieldQuestion, a: FieldAnswer): boolean {
  switch (q.type) {
    case "single_choice":
    case "multi_choice":
      return a.choiceIds.length === 0;
    case "short_text":
    case "long_text":
      return a.text.trim().length === 0;
    case "date":
      return a.date.trim().length === 0;
    case "checkbox":
      return !a.checked;
    default:
      return false;
  }
}

/**
 * Returns an error message for the answer, or null when valid. Enforces
 * required + the type-specific format rules from `config`.
 */
export function validateAnswer(q: FieldQuestion, a: FieldAnswer): string | null {
  const empty = answerIsEmpty(q, a);
  if (q.is_required && empty) {
    return q.type === "checkbox"
      ? "This confirmation is required."
      : "This question is required.";
  }
  if (empty) return null; // optional + blank → fine

  if (q.type === "short_text" || q.type === "long_text") {
    const len = a.text.trim().length;
    const min = num(q.config, "min_length");
    const max = num(q.config, "max_length");
    if (min != null && len < min) return `Enter at least ${min} characters.`;
    if (max != null && len > max) return `Keep it under ${max} characters.`;
  }

  if (q.type === "date") {
    const min = str(q.config, "min_date");
    const max = str(q.config, "max_date");
    if (min && a.date < min) return `Pick a date on or after ${min}.`;
    if (max && a.date > max) return `Pick a date on or before ${max}.`;
  }

  if (q.type === "single_choice" && a.choiceIds.length > 1) {
    return "Pick only one option.";
  }

  return null;
}

/** Serialise an answer into the submit payload shape. */
export function toSubmitAnswer(
  q: FieldQuestion,
  a: FieldAnswer,
): { question_id: number; selected_choice_ids: number[]; value?: Record<string, unknown> } {
  if (isChoiceType(q.type)) {
    return { question_id: q.id, selected_choice_ids: a.choiceIds };
  }
  let value: Record<string, unknown> = {};
  if (q.type === "short_text" || q.type === "long_text") value = { text: a.text.trim() };
  else if (q.type === "date") value = { date: a.date };
  else if (q.type === "checkbox") value = { checked: a.checked };
  return { question_id: q.id, selected_choice_ids: [], value };
}

/** Validate every answer; returns a map of question_id → error for the
 *  invalid ones (empty map = the form is submittable). */
export function validateAll(
  questions: FieldQuestion[],
  answers: Record<number, FieldAnswer>,
): Record<number, string> {
  const errors: Record<number, string> = {};
  for (const q of questions) {
    const err = validateAnswer(q, answers[q.id] ?? emptyAnswer());
    if (err) errors[q.id] = err;
  }
  return errors;
}
