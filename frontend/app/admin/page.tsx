import { AuthGuard } from "@/components/auth-guard";
import { PortalDashboardPlaceholder } from "@/components/portal-dashboard-placeholder";

export default function AdminPage() {
  return (
    <AuthGuard loginPath="/admin/login">
      <PortalDashboardPlaceholder
        surface="Website Admin"
        nextPhase="Phase 5"
        upcoming={[
          "Dashboard with Recharts widgets",
          "Menu management",
          "Hero slider management",
          "Page content management",
          "Group companies management",
          "Leadership messages management",
          "News and events management",
          "Media gallery management",
          "Contact inbox",
          "Newsletter subscribers",
          "Site / theme / SEO settings",
          "Email and AI configuration",
          "Sitemap management",
          "Website audit log",
        ]}
      />
    </AuthGuard>
  );
}
