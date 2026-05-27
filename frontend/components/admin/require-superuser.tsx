"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, ShieldAlert } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";

interface RequireSuperuserProps {
  /** What the user was trying to access — surfaces in the heading. */
  area: string;
  children: React.ReactNode;
}

/**
 * Client-side guard for pages that should only be opened by accounts
 * with ``is_superuser = true`` — currently just Database backup +
 * restore, since those actions can wipe the entire database.
 *
 * Pairs with the server-side ``require_superuser`` dependency in
 * ``app/auth/dependencies.py``; the server is what really enforces the
 * rule, this just gives a friendlier UX than a raw 403.
 */
export function RequireSuperuser({ area, children }: RequireSuperuserProps) {
  const { user, status } = useAuth();

  if (status !== "authenticated" || !user) {
    return <>{children}</>;
  }

  if (user.is_superuser) {
    return <>{children}</>;
  }

  return (
    <div className="mx-auto max-w-xl rounded-2xl border border-rose-500/30 bg-rose-500/5 p-8 text-center">
      <div className="mx-auto mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-rose-500/15 text-rose-700 dark:text-rose-300">
        <ShieldAlert className="h-6 w-6" />
      </div>
      <h2 className="text-lg font-semibold">{area} is superuser-only</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        Your account ({user.email}) does not hold the superuser flag. {area}{" "}
        can delete or replace the entire database, so it is locked to the
        small set of operator-tier accounts even within the system scope.
      </p>
      <p className="mt-3 text-xs text-muted-foreground">
        Ask a Super Admin to sign in, or have one grant your account the
        superuser flag under <em>Users &amp; roles</em>.
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
