"use client";

/**
 * Client-side route guard for /admin/* pages.
 *
 * Sidebar gating only hides menu items — a user who types a URL
 * directly still hits the page. This component runs on every admin
 * render, inspects the pathname, and:
 *
 *   * lets the login page through unconditionally;
 *   * lets superusers through (they see everything by definition);
 *   * routes marketing-only users to their dashboard if they land
 *     on a non-marketing URL;
 *   * does the inverse if a website-only user lands on a marketing
 *     URL they can't access.
 *
 * The backend re-validates every API call (after the perm + scope
 * fix in this commit) so this is UX gating, not a security
 * boundary — but it keeps Marketing users from staring at empty,
 * 403-spamming CMS pages.
 */

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";

import { AccessDenied } from "@/components/auth/permission";
import { useAuth } from "@/components/auth-provider";


// Any /admin/* path that needs a website.* perm. Marketing-only
// users (no website perm) bounce to /admin/marketing/dashboard
// instead of being dumped on a 403 page.
const MARKETING_PREFIX = "/admin/marketing/";
const LOGIN_PATH = "/admin/login";


// Mirror of the perm keys gated in ``admin/sidebar.tsx`` — kept
// inline so the guard is self-contained.
const WEBSITE_PERMS = [
  "website.dashboard.read",
  "website.content.read",
  "website.content.write",
  "website.settings.read",
  "website.menu.read",
  "website.users.manage",
  "website.audit.read",
];

const MARKETING_PERMS = [
  "marketing:dashboard:view",
  "marketing:campaigns:read",
  "marketing:campaigns:manage",
  "marketing:catalogues:read",
  "marketing:catalogues:manage",
  "marketing:short_urls:read",
  "marketing:short_urls:manage",
];


export function AdminRouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const { user, status } = useAuth();

  // Loading / not-logged-in: the AuthProvider handles the redirect.
  // Login page itself: always pass through.
  if (status !== "authenticated" || !user || pathname === LOGIN_PATH) {
    return <>{children}</>;
  }

  // Superusers see everything.
  if (user.is_superuser) {
    return <>{children}</>;
  }

  const permSet = new Set(user.permissions ?? []);
  const hasWebsiteAccess = WEBSITE_PERMS.some((p) => permSet.has(p));
  const hasMarketingAccess = MARKETING_PERMS.some((p) => permSet.has(p));
  const isMarketingPath = pathname.startsWith(MARKETING_PREFIX);

  // Marketing-only user on a non-marketing URL — bounce them to their
  // home so they get a useful page instead of an empty 403.
  if (!hasWebsiteAccess && hasMarketingAccess && !isMarketingPath) {
    if (typeof window !== "undefined") {
      router.replace("/admin/marketing/dashboard");
    }
    return (
      <AccessDenied
        title="Marketing console"
        description="Redirecting you to the Marketing dashboard…"
        backHref="/admin/marketing/dashboard"
        backLabel="Open Marketing dashboard"
      />
    );
  }

  // Website-only user on a marketing-only URL — same idea in reverse.
  if (hasWebsiteAccess && !hasMarketingAccess && isMarketingPath) {
    return (
      <AccessDenied
        title="Marketing module"
        description={
          "Your account doesn't include the marketing role. Ask a Super " +
          "Admin to grant Marketing Manager or Marketing Viewer if you " +
          "need access."
        }
        backHref="/admin"
        backLabel="Back to admin dashboard"
      />
    );
  }

  return <>{children}</>;
}
