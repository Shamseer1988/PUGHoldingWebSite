import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { FileText } from "lucide-react";

export default function PagesAdminPage() {
  return (
    <AdminShell title="Pages" description="Free-form page content (About, etc.).">
      <EmptyState
        icon={FileText}
        title="Page content management"
        description="Phase 5 covers structured CMS resources (hero slides, companies, leadership, news, settings). Free-form page blocks land in a Phase 5 follow-up."
      />
    </AdminShell>
  );
}
