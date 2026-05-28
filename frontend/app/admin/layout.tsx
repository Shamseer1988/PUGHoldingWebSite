import { AuthProvider } from "@/components/auth-provider";

// Phase A-1: admin portal is per-user, per-permission, never cached.
// Forcing dynamic at the layout level keeps every nested admin route
// off the static cache regardless of any per-route exports.
export const dynamic = "force-dynamic";

/**
 * Website Admin layout.
 *
 * Wraps every /admin/* route in the AuthProvider keyed to the "admin"
 * scope so login state is shared but isolated from the HR portal.
 */
export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider
      scope="admin"
      loginRedirect="/admin"
      logoutRedirect="/admin/login"
    >
      <div className="min-h-screen bg-background">{children}</div>
    </AuthProvider>
  );
}
