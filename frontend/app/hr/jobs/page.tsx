import { Briefcase } from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";

export default function HrJobsPage() {
  return (
    <HrShell
      title="Job openings"
      description="Manage active and closed job postings."
    >
      <HrEmptyState
        icon={Briefcase}
        title="Job opening management"
        description="Phase 9 wires the full Job Opening master here — create, edit, close/reopen, and surface jobs on the public careers page. Backend tables and seed data are already in place from Phase 7."
      />
    </HrShell>
  );
}
