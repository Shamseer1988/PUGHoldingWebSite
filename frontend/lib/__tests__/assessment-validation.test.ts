import { describe, expect, test } from "vitest";

import {
  answerIsEmpty,
  emptyAnswer,
  toSubmitAnswer,
  validateAll,
  validateAnswer,
  type FieldQuestion,
} from "@/lib/assessment-validation";

function q(overrides: Partial<FieldQuestion>): FieldQuestion {
  return {
    id: 1,
    text: "Q",
    type: "short_text",
    is_required: true,
    config: {},
    choices: [],
    ...overrides,
  };
}

describe("answerIsEmpty", () => {
  test("per type", () => {
    expect(answerIsEmpty(q({ type: "short_text" }), emptyAnswer())).toBe(true);
    expect(
      answerIsEmpty(q({ type: "short_text" }), { ...emptyAnswer(), text: "x" }),
    ).toBe(false);
    expect(answerIsEmpty(q({ type: "date" }), emptyAnswer())).toBe(true);
    expect(answerIsEmpty(q({ type: "checkbox" }), emptyAnswer())).toBe(true);
    expect(
      answerIsEmpty(q({ type: "checkbox" }), { ...emptyAnswer(), checked: true }),
    ).toBe(false);
    expect(answerIsEmpty(q({ type: "multi_choice" }), emptyAnswer())).toBe(true);
    expect(
      answerIsEmpty(q({ type: "multi_choice" }), {
        ...emptyAnswer(),
        choiceIds: [7],
      }),
    ).toBe(false);
  });
});

describe("validateAnswer", () => {
  test("required blank is rejected; optional blank passes", () => {
    expect(validateAnswer(q({ is_required: true }), emptyAnswer())).toMatch(
      /required/i,
    );
    expect(validateAnswer(q({ is_required: false }), emptyAnswer())).toBeNull();
  });

  test("text honours min/max length", () => {
    const question = q({ type: "short_text", config: { max_length: 3 } });
    expect(
      validateAnswer(question, { ...emptyAnswer(), text: "toolong" }),
    ).toMatch(/under 3/);
    expect(validateAnswer(question, { ...emptyAnswer(), text: "ok" })).toBeNull();
  });

  test("date honours min/max bounds", () => {
    const question = q({
      type: "date",
      config: { min_date: "2026-01-01", max_date: "2026-12-31" },
    });
    expect(
      validateAnswer(question, { ...emptyAnswer(), date: "2025-06-01" }),
    ).toMatch(/on or after/);
    expect(
      validateAnswer(question, { ...emptyAnswer(), date: "2026-06-01" }),
    ).toBeNull();
  });
});

describe("validateAll blocks submit on a required gap", () => {
  test("returns an error map keyed by question id", () => {
    const questions = [
      q({ id: 1, type: "short_text", is_required: true }),
      q({ id: 2, type: "checkbox", is_required: false }),
    ];
    const errors = validateAll(questions, {});
    expect(errors[1]).toBeDefined();
    expect(errors[2]).toBeUndefined();
    expect(Object.keys(errors)).toHaveLength(1);
  });
});

describe("toSubmitAnswer", () => {
  test("choice types serialise selected_choice_ids", () => {
    const out = toSubmitAnswer(q({ id: 5, type: "multi_choice" }), {
      ...emptyAnswer(),
      choiceIds: [9, 10],
    });
    expect(out).toEqual({ question_id: 5, selected_choice_ids: [9, 10] });
  });

  test("typed answers serialise value", () => {
    expect(
      toSubmitAnswer(q({ id: 6, type: "short_text" }), {
        ...emptyAnswer(),
        text: "  Asha  ",
      }),
    ).toEqual({ question_id: 6, selected_choice_ids: [], value: { text: "Asha" } });
    expect(
      toSubmitAnswer(q({ id: 7, type: "date" }), {
        ...emptyAnswer(),
        date: "2026-06-01",
      }),
    ).toEqual({
      question_id: 7,
      selected_choice_ids: [],
      value: { date: "2026-06-01" },
    });
    expect(
      toSubmitAnswer(q({ id: 8, type: "checkbox" }), {
        ...emptyAnswer(),
        checked: true,
      }),
    ).toEqual({ question_id: 8, selected_choice_ids: [], value: { checked: true } });
  });
});
