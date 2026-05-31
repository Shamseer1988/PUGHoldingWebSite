import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  STATUS_TAXONOMY,
  StatusBadge,
  type StatusKind,
  statusEntry,
  statusLabel,
  statusesForKind,
} from "@/components/hr/status-badge";

const KINDS: StatusKind[] = ["application", "offer", "interview", "job"];

// The full application lifecycle the recruitment console must render
// (acceptance criterion 2). Mirrors candidate_workflow.PIPELINE_ORDER.
const REQUIRED_APPLICATION_STATUSES = [
  "cv_received",
  "ai_reviewed",
  "hr_review_pending",
  "shortlisted",
  "first_interview",
  "technical_interview",
  "final_interview",
  "waiting_list",
  "recommended_for_offer",
  "selected",
  "offer_sent",
  "joined",
  "not_joined",
  "rejected",
  "blacklisted",
];

describe("StatusBadge taxonomy", () => {
  test("exposes exactly the four documented kinds", () => {
    expect(Object.keys(STATUS_TAXONOMY).sort()).toEqual([...KINDS].sort());
  });

  test("application taxonomy covers the full lifecycle + side lanes", () => {
    expect(statusesForKind("application")).toEqual(
      REQUIRED_APPLICATION_STATUSES,
    );
  });

  test("every taxonomy entry renders a labelled, coloured pill", () => {
    for (const kind of KINDS) {
      for (const [status, entry] of Object.entries(STATUS_TAXONOMY[kind])) {
        const { container, unmount } = render(
          <StatusBadge kind={kind} status={status} />,
        );
        // Label text is present (no raw snake_case leaking through).
        expect(screen.getByText(entry.label)).toBeInTheDocument();
        // A non-empty tailwind class string is attached (coloured pill).
        const pill = container.querySelector("span");
        expect(pill?.className).toContain("rounded-full");
        expect(entry.className.length).toBeGreaterThan(0);
        expect(entry.label).not.toBe("");
        unmount();
      }
    }
  });

  test("statusLabel resolves canonical labels", () => {
    expect(statusLabel("application", "recommended_for_offer")).toBe(
      "Recommended for offer",
    );
    expect(statusLabel("offer", "sent")).toBe("Issued");
    expect(statusLabel("interview", "no_show")).toBe("No-show");
    expect(statusLabel("job", "on_hold")).toBe("On hold");
  });
});

describe("StatusBadge rendering", () => {
  test("falls back to the raw value with neutral tone for unknown status", () => {
    render(<StatusBadge kind="application" status="totally_unknown" />);
    expect(screen.getByText("totally_unknown")).toBeInTheDocument();
    expect(statusEntry("application", "totally_unknown").tone).toBe("neutral");
  });

  test("renders an em dash for empty / null status", () => {
    const { container } = render(
      <StatusBadge kind="application" status={null} />,
    );
    expect(container.textContent).toBe("—");
  });

  test("honours an explicit label override", () => {
    render(
      <StatusBadge kind="application" status="shortlisted" label="Custom" />,
    );
    expect(screen.getByText("Custom")).toBeInTheDocument();
    expect(screen.queryByText("Shortlisted")).not.toBeInTheDocument();
  });
});
