import { AuthProvider } from "@/components/auth-provider";

/**
 * HR ATS layout.
 *
 * Wraps every /hr/* route in the AuthProvider keyed to the "hr" scope.
 */
export default function HrLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider scope="hr" loginRedirect="/hr" logoutRedirect="/hr/login">
      <div className="min-h-screen bg-background">{children}</div>
    </AuthProvider>
  );
}
