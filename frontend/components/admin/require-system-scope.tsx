"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, ShieldAlert } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";

interface RequireSystemScopeProps {
  /** What the user was trying to access — surfaces in the heading. */
  area: string;
  children: React.ReactNode;
}

/**
 * Client-side guard for system-only admin pages (AI settings, Users &
 * roles). When the signed-in user doesn't hold the `system` scope (or
 * the `is_superuser` flag) we render an explainer card instead of
 * letting the page fire backend requests that come back 403 with the
 * cryptic ``This area requires 'system' access`` message.
 *
 * The server still enforces the rule — this is purely UX.
 */
export function RequireSystemScope({
  area,
  children,
}: RequireSystemScopeProps) {
  const { user, status } = useAuth();

  if (status !== "authenticated" || !user) {
    // The outer AuthGuard already handles unauthenticated → login;
    // suppress the lock UI until we know who the user is.
    return <>{children}</>;
  }

  const hasSystem =
    user.is_superuser || user.scopes?.includes("system");
  if (hasSystem) {
    return <>{children}</>;
  }

  return (
    <div className="mx-auto max-w-xl rounded-2xl border border-amber-500/30 bg-amber-500/5 p-8 text-center">
      <div className="mx-auto mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-300">
        <ShieldAlert className="h-6 w-6" />
      </div>
      <h2 className="text-lg font-semibold">{area} is system-only</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        Your account ({user.email}) signs in with{" "}
        <span className="font-mono text-foreground/80">
          {user.scopes?.join(", ") || "no"}
        </span>{" "}
        scope. {area} can only be opened by a Super Admin so a misconfigured
        setting can&rsquo;t silently affect both the website and HR portals.
      </p>
      <p className="mt-3 text-xs text-muted-foreground">
        Ask a Super Admin to sign in (the default seed account is{" "}
        <code className="rounded bg-muted px-1">superadmin@pug.example.com</code>),
        or have one promote your role under <em>Users &amp; roles</em>.
      </p>
      <div className="mt-5">
        <Button asChild size="sm" variant="outline">
          <Link href="/admin">
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to dashboard
          </Link>
        </Button>
      </div>
    </div>
  );
}
