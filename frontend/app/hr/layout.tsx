/**
 * HR ATS layout placeholder.
 * Phase 2 adds /hr/login, route guards, and the HR sidebar shell.
 */
export default function HrLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="min-h-screen bg-background">{children}</div>;
}
