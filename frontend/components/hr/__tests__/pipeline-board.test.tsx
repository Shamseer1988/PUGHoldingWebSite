import { describe, expect, test, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import {
  PipelineBoard,
  laneForStatus,
  type PipelineCard,
} from "@/components/hr/pipeline-board";

const post = vi.fn();

vi.mock("@/lib/hr/api", () => ({
  hrApi: { post: (...args: unknown[]) => post(...args) },
  HrApiError: class extends Error {},
}));

// Stub framer-motion's motion.div so drag-specific props don't reach the
// DOM; the move logic is exercised via the keyboard-accessible select.
vi.mock("framer-motion", () => {
  // Strip framer-only props so they don't reach the DOM; render a plain div.
  const FRAMER_PROPS = new Set([
    "drag",
    "dragSnapToOrigin",
    "whileDrag",
    "onDragEnd",
    "layout",
  ]);
  return {
    motion: {
      div: ({
        children,
        ...props
      }: Record<string, unknown> & { children?: React.ReactNode }) => {
        const safe = Object.fromEntries(
          Object.entries(props).filter(([k]) => !FRAMER_PROPS.has(k)),
        );
        return <div {...safe}>{children}</div>;
      },
    },
  };
});

const CARD: PipelineCard = {
  candidateId: 7,
  applicationId: 42,
  name: "Asha",
  status: "shortlisted",
  score: 80,
};

beforeEach(() => post.mockReset());

describe("laneForStatus", () => {
  test("maps lane statuses and omits side lanes", () => {
    expect(laneForStatus("cv_received")).toBe("sourced");
    expect(laneForStatus("shortlisted")).toBe("screening");
    expect(laneForStatus("first_interview")).toBe("interview");
    expect(laneForStatus("selected")).toBe("selected");
    expect(laneForStatus("offer_sent")).toBe("offer");
    expect(laneForStatus("joined")).toBe("joined");
    expect(laneForStatus("rejected")).toBeNull();
    expect(laneForStatus("waiting_list")).toBeNull();
  });
});

describe("PipelineBoard", () => {
  test("moving a card to a lane posts the lane's target status", () => {
    post.mockResolvedValue({});
    const onMoved = vi.fn();
    render(<PipelineBoard cards={[CARD]} onMoved={onMoved} />);

    // Card sits in Screening; move it to the Interview lane.
    const select = screen.getByRole("combobox", { name: "Move Asha" });
    fireEvent.change(select, { target: { value: "interview" } });

    expect(post).toHaveBeenCalledWith(
      "/hr/candidates/7/applications/42/status",
      { new_status: "first_interview" },
    );
  });

  test("renders the supplied cards with a per-card move control", () => {
    render(
      <PipelineBoard
        cards={[
          CARD,
          {
            candidateId: 9,
            applicationId: 90,
            name: "Bilal",
            status: "joined",
            score: 95,
          },
        ]}
        onMoved={vi.fn()}
      />,
    );
    expect(screen.getByText("Asha")).toBeInTheDocument();
    expect(screen.getByText("Bilal")).toBeInTheDocument();
    // One "Move…" select per card.
    expect(screen.getAllByRole("combobox")).toHaveLength(2);
  });
});
