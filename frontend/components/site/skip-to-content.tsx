import Link from "next/link";

/**
 * Accessibility helper – keyboard users can press Tab on page load and
 * jump straight to the main content past the navbar.
 */
export function SkipToContent({ targetId = "main-content" }: { targetId?: string }) {
  return (
    <Link
      href={`#${targetId}`}
      className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:text-primary-foreground focus:shadow-md"
    >
      Skip to main content
    </Link>
  );
}
