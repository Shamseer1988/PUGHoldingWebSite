/**
 * Website Admin layout placeholder.
 * Phase 2 adds /admin/login, route guards, and the sidebar shell.
 */
export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="min-h-screen bg-background">{children}</div>;
}
