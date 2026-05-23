import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Image as ImageIcon } from "lucide-react";

export default function MediaAdminPage() {
  return (
    <AdminShell title="Media gallery" description="Photo and video gallery management.">
      <EmptyState
        icon={ImageIcon}
        title="Media gallery management"
        description="Phase 5 ships the CMS foundation; file upload, gallery management, and image optimisation arrive in a Phase 5 follow-up before Phase 6 wires the public site."
      />
    </AdminShell>
  );
}
