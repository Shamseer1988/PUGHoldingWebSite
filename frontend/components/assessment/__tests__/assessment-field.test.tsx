import { describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { AssessmentField } from "@/components/assessment/assessment-field";
import { emptyAnswer } from "@/lib/assessment-validation";
import type { AssessmentQuestion } from "@/lib/public-api-client";

function makeQuestion(overrides: Partial<AssessmentQuestion>): AssessmentQuestion {
  return {
    id: 1,
    text: "A question",
    type: "short_text",
    help_text: null,
    is_required: true,
    config: {},
    order_index: 0,
    points: 1,
    choices: [],
    ...overrides,
  };
}

function renderField(q: AssessmentQuestion) {
  const onChange = vi.fn();
  render(
    <AssessmentField
      question={q}
      index={0}
      answer={emptyAnswer()}
      onChange={onChange}
    />,
  );
  return onChange;
}

describe("AssessmentField renders the right control per type", () => {
  test("short_text → text input", () => {
    renderField(makeQuestion({ type: "short_text" }));
    const input = screen.getByRole("textbox");
    expect(input.tagName).toBe("INPUT");
  });

  test("long_text → textarea", () => {
    renderField(makeQuestion({ type: "long_text" }));
    expect(screen.getByRole("textbox").tagName).toBe("TEXTAREA");
  });

  test("date → date input", () => {
    renderField(makeQuestion({ type: "date", text: "When?" }));
    const input = screen.getByLabelText(/When\?/) as HTMLInputElement;
    expect(input.type).toBe("date");
  });

  test("checkbox → single checkbox", () => {
    renderField(makeQuestion({ type: "checkbox", config: { label: "I agree" } }));
    expect(screen.getByRole("checkbox")).toBeInTheDocument();
    expect(screen.getByText("I agree")).toBeInTheDocument();
  });

  test("single_choice → dropdown with options", () => {
    renderField(
      makeQuestion({
        type: "single_choice",
        choices: [
          { id: 11, text: "One", order_index: 0 },
          { id: 12, text: "Two", order_index: 1 },
        ],
      }),
    );
    const select = screen.getByRole("combobox");
    // placeholder + 2 options
    expect(select.querySelectorAll("option")).toHaveLength(3);
  });

  test("multi_choice → one checkbox per choice", () => {
    renderField(
      makeQuestion({
        type: "multi_choice",
        choices: [
          { id: 21, text: "A", order_index: 0 },
          { id: 22, text: "B", order_index: 1 },
          { id: 23, text: "C", order_index: 2 },
        ],
      }),
    );
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  });
});

describe("AssessmentField interaction", () => {
  test("typing emits a text answer; required marker + error show", () => {
    const onChange = vi.fn();
    render(
      <AssessmentField
        question={makeQuestion({ type: "short_text", is_required: true })}
        index={0}
        answer={emptyAnswer()}
        error="This question is required."
        onChange={onChange}
      />,
    );
    expect(screen.getByLabelText("required")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/required/i);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Asha" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ text: "Asha" }),
    );
  });
});
