import { AuthProvider } from "@/components/auth-provider";

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
