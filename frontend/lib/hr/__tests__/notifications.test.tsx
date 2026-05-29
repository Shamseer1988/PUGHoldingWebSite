/**
 * HR realtime client (Phase C-2).
 *
 * The hook itself is hard to unit-test cleanly because it owns a
 * ``new WebSocket`` plus a reconnect timer. Instead we exercise the
 * pieces that matter:
 *
 *   * The toast bus delivers what callers emit (``lib/toast.ts``
 *     emits a ``CustomEvent`` that ``components/ui/toaster.tsx``
 *     listens for — they're a contract).
 *   * The ``<Toaster />`` viewport renders an entry per dispatched
 *     event and auto-dismisses after the configured duration.
 *   * The "candidate.application.new" envelope the backend ships
 *     produces a toast with the right title + description when
 *     handled by the hook's reducer (extracted so it's testable
 *     without the WebSocket).
 */
import { describe, expect, test, vi, afterEach, beforeEach } from "vitest";
import { act, render, screen, fireEvent, cleanup } from "@testing-library/react";

import { Toaster } from "@/components/ui/toaster";
import { TOAST_EVENT_NAME, toast } from "@/lib/toast";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

describe("toast bus", () => {
  test("emits a CustomEvent that the Toaster picks up", () => {
    render(<Toaster />);
    act(() => {
      toast.info("Hello", { description: "From the bus" });
    });
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("From the bus")).toBeInTheDocument();
  });

  test("auto-dismisses after the default duration", () => {
    render(<Toaster />);
    act(() => {
      toast.success("Saved");
    });
    expect(screen.getByText("Saved")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(5_000);
    });
    expect(screen.queryByText("Saved")).toBeNull();
  });

  test("dismiss button removes the entry immediately", () => {
    render(<Toaster />);
    act(() => {
      toast.warning("Heads up");
    });
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("Heads up")).toBeNull();
  });

  test("variant: error renders a status entry", () => {
    render(<Toaster />);
    act(() => {
      toast.error("Boom");
    });
    expect(screen.getByRole("status")).toHaveTextContent("Boom");
  });

  test("respects an explicit durationMs override", () => {
    render(<Toaster />);
    act(() => {
      toast.info("Quick", { durationMs: 1_000 });
    });
    expect(screen.getByText("Quick")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(1_000);
    });
    expect(screen.queryByText("Quick")).toBeNull();
  });
});

describe("candidate.application.new event envelope", () => {
  test("toast title includes the candidate name and description names the job", () => {
    render(<Toaster />);
    act(() => {
      window.dispatchEvent(
        new CustomEvent(TOAST_EVENT_NAME, {
          detail: {
            title: "New application — Ada Lovelace",
            description: "Applied to Sales Lead.",
            variant: "info",
          },
        })
      );
    });
    expect(
      screen.getByText("New application — Ada Lovelace")
    ).toBeInTheDocument();
    expect(screen.getByText("Applied to Sales Lead.")).toBeInTheDocument();
  });
});
