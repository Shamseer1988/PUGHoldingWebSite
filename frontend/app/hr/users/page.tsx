import { UsersRound } from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";

export default function HrUsersPage() {
  return (
    <HrShell
      title="HR users & roles"
      description="Manage HR Super Admin, HR Manager, HR Executive, Interviewer, and Viewer accounts."
    >
      <HrEmptyState
        icon={UsersRound}
        title="HR user management"
        description="Seed users (HR Manager, HR Executive, Interviewer) are already created via `python -m app.scripts.seed_users`. Full role and permission UI lands in a Phase 16 follow-up alongside the website-admin users UI."
      />
    </HrShell>
  );
}
