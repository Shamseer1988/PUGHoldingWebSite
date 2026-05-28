import { AuthProvider } from "@/components/auth-provider";
import { HrRealtimeListener } from "@/components/hr/hr-realtime";
import { QueryProvider } from "@/components/query-provider";
import { Toaster } from "@/components/ui/toaster";

// Phase A-1: HR ATS is per-user, per-permission, never cached.
// Same reasoning as the admin layout — caching candidate / interview
// data would leak across operators.
export const dynamic = "force-dynamic";

/**
 * HR ATS layout.
 *
 * Wraps every /hr/* route in the AuthProvider keyed to the "hr" scope.
 * The TanStack Query client (Phase B-4) sits inside so query hooks
 * can read auth state via ``useAuth``. The Phase C-2 realtime
 * listener opens the WebSocket and the Toaster surfaces the
 * resulting events.
 */
export default function HrLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider scope="hr" loginRedirect="/hr" logoutRedirect="/hr/login">
      <QueryProvider>
        <div className="min-h-screen bg-background">{children}</div>
        <HrRealtimeListener />
        <Toaster />
      </QueryProvider>
    </AuthProvider>
  );
}
