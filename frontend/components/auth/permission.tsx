"use client";

import * as React from "react";
import Link from "next/link";
import { Lock } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";


// ---------------------------------------------------------------------------
// Hook: usePermission
// ---------------------------------------------------------------------------


export interface PermissionHelpers {
  /** The current user's permission keys (empty array when logged out). */
  permissions: string[];
  /** True if the user has every key in the list (or is superuser). */
  hasAll: (keys: readonly string[]) => boolean;
  /** True if the user has at least one of the listed keys. */
  hasAny: (keys: readonly string[]) => boolean;
  /** Shortcut for ``hasAny([key])``. */
  has: (key: string) => boolean;
  /** True when user.is_superuser. */
  isSuperuser: boolean;
}

/**
 * Read the current user's permission keys and expose helpers.
 *
 * Frontend-only — the backend re-validates every API call. Use this for
 * UX gating (hide buttons, filter nav). Never trust it for security.
 */
export function usePermission(): PermissionHelpers {
  const { user } = useAuth();
  return React.useMemo<PermissionHelpers>(() => {
    const permissions = user?.permissions ?? [];
    const set = new Set(permissions);
    const isSuperuser = Boolean(user?.is_superuser);
    const has = (key: string) => isSuperuser || set.has(key);
    const hasAny = (keys: readonly string[]) =>
      isSuperuser || keys.some((k) => set.has(k));
    const hasAll = (keys: readonly string[]) =>
      isSuperuser || keys.every((k) => set.has(k));
    return { permissions, has, hasAny, hasAll, isSuperuser };
  }, [user]);
}


// ---------------------------------------------------------------------------
// Component: <RequirePermission>
// ---------------------------------------------------------------------------


interface RequirePermissionProps {
  /** Single permission key — equivalent to anyOf: [key]. */
  permission?: string;
  /** User must have ALL of these keys. */
  allOf?: readonly string[];
  /** User must have at least one of these keys. */
  anyOf?: readonly string[];
  /**
   * What to render when the user lacks the required permission. Defaults
   * to the Access Denied screen below.
   */
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Gate the children behind a permission check. Renders ``fallback``
 * (Access Denied by default) when the user doesn't have the required
 * grants. Use this on the top of HR page components.
 */
export function RequirePermission({
  permission,
  allOf,
  anyOf,
  fallback,
  children,
}: RequirePermissionProps) {
  const perms = usePermission();
  let allowed = true;
  if (permission && !perms.has(permission)) allowed = false;
  if (allOf && !perms.hasAll(allOf)) allowed = false;
  if (anyOf && !perms.hasAny(anyOf)) allowed = false;

  if (allowed) return <>{children}</>;
  return <>{fallback ?? <AccessDenied />}</>;
}


// ---------------------------------------------------------------------------
// Component: <AccessDenied>
// ---------------------------------------------------------------------------


interface AccessDeniedProps {
  /** Override the headline (defaults to a friendly generic message). */
  title?: string;
  /** Override the body copy. */
  description?: string;
  /** When set, render a "Back to ..." button pointing here. */
  backHref?: string;
  /** Label for the back button. */
  backLabel?: string;
}

/**
 * Friendly 403 card. Shown when:
 *  - A protected route component is rendered for a user without the
 *    required permission.
 *  - The API returned 403 and the page wants to surface a clean state.
 */
export function AccessDenied({
  title = "Access denied",
  description = (
    "You don't have permission to view this page. " +
    "Ask your HR Manager or the Super Admin to grant the relevant role."
  ),
  backHref = "/hr",
  backLabel = "Back to dashboard",
}: AccessDeniedProps) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <div className="max-w-md rounded-xl border border-border/60 bg-card p-6 text-center shadow-sm">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rose-500/10">
          <Lock className="h-6 w-6 text-rose-600 dark:text-rose-400" />
        </div>
        <h1 className="text-base font-semibold">{title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
        <div className="mt-5">
          <Button asChild size="sm" variant="outline">
            <Link href={backHref}>{backLabel}</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
