import { Users } from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";

export default function HrCandidatesPage() {
  return (
    <HrShell
      title="Candidates"
      description="Browse, filter, score, and progress candidates through the pipeline."
    >
      <HrEmptyState
        icon={Users}
        title="Candidate workspace"
        description="Phase 10 wires CV upload (single + bulk ZIP) and the candidate intake. Phase 11 adds CV parsing, Phase 12 the scoring engine, Phase 13 the AI review, Phase 14 the workflow pipeline, and Phase 16 advanced search + reports."
      />
    </HrShell>
  );
}
