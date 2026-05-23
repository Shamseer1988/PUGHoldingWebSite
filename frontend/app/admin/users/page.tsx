import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Users } from "lucide-react";

export default function UsersAdminPage() {
  return (
    <AdminShell title="Users & roles" description="Manage website admin users and their permissions.">
      <EmptyState
        icon={Users}
        title="User management"
        description="Seed users (Super Admin, Website Admin, HR Manager, HR Executive, Interviewer) are created via the backend seed script. Full user / role / permission UI lands in a Phase 5 follow-up."
      />
    </AdminShell>
  );
}
