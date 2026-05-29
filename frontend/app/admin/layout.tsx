import { AuthProvider } from "@/components/auth-provider";
import { QueryProvider } from "@/components/query-provider";

// Phase A-1: admin portal is per-user, per-permission, never cached.
// Forcing dynamic at the layout level keeps every nested admin route
// off the static cache regardless of any per-route exports.
export const dynamic = "force-dynamic";

/**
 * Website Admin layout.
 *
 * Wraps every /admin/* route in the AuthProvider keyed to the "admin"
 * scope so login state is shared but isolated from the HR portal.
 * The TanStack Query client (Phase B-4) sits inside the AuthProvider
 * so query hooks can gate on the session via ``useAuth().status``.
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
      <QueryProvider>
        <div className="min-h-screen bg-background">{children}</div>
      </QueryProvider>
    </AuthProvider>
  );
}
