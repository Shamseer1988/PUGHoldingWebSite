import { AuthGuard } from "@/components/auth-guard";
import { PortalDashboardPlaceholder } from "@/components/portal-dashboard-placeholder";

export default function HrPage() {
  return (
    <AuthGuard loginPath="/hr/login">
      <PortalDashboardPlaceholder
        surface="HR ATS Portal"
        nextPhase="Phase 8"
        upcoming={[
          "HR dashboard with KPIs and Recharts",
          "Job opening management",
          "Candidate applications",
          "CV upload and bulk ZIP import",
          "CV parsing and data extraction",
          "Rule-based candidate scoring",
          "AI candidate review (advisory)",
          "Workflow pipeline",
          "Interview scheduling and feedback",
          "Offer tracking",
          "Advanced search and filters",
          "HR reports + Excel / CSV / PDF export",
          "HR users, roles, and permissions",
          "HR audit log",
        ]}
      />
    </AuthGuard>
  );
}
