import { describe, expect, test, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import {
  CandidateRowActions,
  candidateActionEnablement,
} from "@/components/hr/candidate-row-actions";

describe("candidateActionEnablement", () => {
  test("offer is only issuable when recommended_for_offer or selected", () => {
    expect(
      candidateActionEnablement("recommended_for_offer", ["selected"]).issueOffer,
    ).toBe(true);
    expect(candidateActionEnablement("selected", ["offer_sent"]).issueOffer).toBe(
      true,
    );
    expect(candidateActionEnablement("shortlisted", ["first_interview"]).issueOffer).toBe(
      false,
    );
    expect(candidateActionEnablement("cv_received", ["shortlisted"]).issueOffer).toBe(
      false,
    );
  });

  test("update-status mirrors whether transitions exist", () => {
    expect(
      candidateActionEnablement("shortlisted", ["first_interview"]).updateStatus,
    ).toBe(true);
    // Final states have no outgoing transitions → disabled.
    expect(candidateActionEnablement("joined", []).updateStatus).toBe(false);
    expect(candidateActionEnablement("rejected", []).updateStatus).toBe(false);
  });

  test("schedule + assessment disabled in final states, open360 always on", () => {
    const active = candidateActionEnablement("first_interview", ["final_interview"]);
    expect(active.scheduleInterview).toBe(true);
    expect(active.sendAssessment).toBe(true);
    expect(active.open360).toBe(true);

    for (const final of ["joined", "not_joined", "rejected", "blacklisted"]) {
      const e = candidateActionEnablement(final, []);
      expect(e.scheduleInterview).toBe(false);
      expect(e.sendAssessment).toBe(false);
      expect(e.open360).toBe(true);
    }
  });

  test("null status disables everything except open360", () => {
    const e = candidateActionEnablement(null, []);
    expect(e).toEqual({
      updateStatus: false,
      scheduleInterview: false,
      sendAssessment: false,
      issueOffer: false,
      open360: true,
    });
  });
});

function renderActions(overrides: Partial<React.ComponentProps<typeof CandidateRowActions>> = {}) {
  const handlers = {
    onUpdateStatus: vi.fn(),
    onScheduleInterview: vi.fn(),
    onSendAssessment: vi.fn(),
    onIssueOffer: vi.fn(),
    onOpen360: vi.fn(),
  };
  render(
    <CandidateRowActions
      status="recommended_for_offer"
      applicationId={42}
      allowedNext={["selected", "rejected", "blacklisted"]}
      {...handlers}
      {...overrides}
    />,
  );
  return handlers;
}

describe("CandidateRowActions", () => {
  test("Issue offer enabled at recommended_for_offer and fires its callback", () => {
    const handlers = renderActions();
    const issue = screen.getByRole("button", { name: "Issue offer" });
    expect(issue).toBeEnabled();
    fireEvent.click(issue);
    expect(handlers.onIssueOffer).toHaveBeenCalledTimes(1);
  });

  test("Issue offer disabled for a shortlisted candidate", () => {
    renderActions({ status: "shortlisted", allowedNext: ["first_interview"] });
    expect(screen.getByRole("button", { name: "Issue offer" })).toBeDisabled();
  });

  test("update-status dropdown lists exactly the allowed next statuses", () => {
    const handlers = renderActions();
    const select = screen.getByRole("combobox", {
      name: "Update status",
    }) as HTMLSelectElement;
    // placeholder + 3 allowed targets
    expect(select.querySelectorAll("option")).toHaveLength(4);
    fireEvent.change(select, { target: { value: "selected" } });
    expect(handlers.onUpdateStatus).toHaveBeenCalledWith("selected");
  });

  test("no application disables actions but keeps Open 360° usable", () => {
    const handlers = renderActions({ applicationId: null, status: null });
    expect(screen.getByRole("button", { name: "Issue offer" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Update status" })).toBeDisabled();
    const open = screen.getByRole("button", { name: "Open 360°" });
    expect(open).toBeEnabled();
    fireEvent.click(open);
    expect(handlers.onOpen360).toHaveBeenCalledTimes(1);
  });
});
