import { UsersRound } from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";

export default function HrUsersPage() {
  return (
    <HrShell
      title="HR users & roles"
      description="HR Manager, HR Executive, Interviewer, and Viewer accounts."
    >
      <HrEmptyState
        icon={UsersRound}
        title="Managed centrally"
        description="HR accounts and their permissions are managed by a Super Admin under the website admin's Users &amp; roles panel. Ask your Super Admin to add, deactivate, or change the role of an HR user."
      />
    </HrShell>
  );
}
