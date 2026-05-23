/**
 * Public site layout (Phase 3 will add the sticky navbar, footer,
 * floating "Ask PUG AI" button, and mobile hamburger menu).
 */
export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="min-h-screen">{children}</div>;
}
