import { FileBarChart } from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";

export default function HrReportsPage() {
  return (
    <HrShell
      title="Reports & export"
      description="Shortlist, job-wise, interview, selected, rejected, salary, skill availability reports."
    >
      <HrEmptyState
        icon={FileBarChart}
        title="HR reports + export"
        description="Phase 16 wires the full reporting surface with Excel / CSV / PDF export and the advanced search + filter panel."
      />
    </HrShell>
  );
}
