import { CalendarClock } from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";

export default function HrInterviewsPage() {
  return (
    <HrShell
      title="Interviews"
      description="Schedule rounds, assign interviewers, and collect feedback."
    >
      <HrEmptyState
        icon={CalendarClock}
        title="Interview management"
        description="Phase 15 wires the full interview scheduler, interviewer access, feedback forms, and per-round status tracking. Backend tables (hr_interviews, hr_interview_feedback) are already in place from Phase 7 — the dashboard above lists pending interviews."
      />
    </HrShell>
  );
}
