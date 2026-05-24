"use client";

import * as React from "react";
import Link from "next/link";
import { LogOut, ShieldCheck } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface PortalDashboardPlaceholderProps {
  /** Surface label (e.g. "Website Admin"). */
  surface: string;
  /** Description of which phase delivers the full dashboard. */
  nextPhase: string;
  /** Short list of features that will land in upcoming phases. */
  upcoming: string[];
}

export function PortalDashboardPlaceholder({
  surface,
  nextPhase,
  upcoming,
}: PortalDashboardPlaceholderProps) {
  const { user, logout } = useAuth();
  const [signingOut, setSigningOut] = React.useState(false);

  async function onLogout() {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <main className="container mx-auto max-w-4xl space-y-6 px-4 py-12">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-primary" />
            {surface}
          </span>
          <h1 className="mt-3 text-2xl font-semibold sm:text-3xl">
            Welcome, {user?.full_name ?? user?.email ?? "user"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Signed in as <span className="font-medium">{user?.email}</span>
          </p>
        </div>
        <Button
          variant="outline"
          onClick={onLogout}
          disabled={signingOut}
        >
          <LogOut className="h-4 w-4" />
          {signingOut ? "Signing out…" : "Sign out"}
        </Button>
      </header>

      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-lg">Session details</CardTitle>
          <CardDescription>
            Roles and permissions assigned to your account.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <Field
            label="Scopes"
            value={user?.scopes?.join(", ") || "—"}
          />
          <Field
            label="Roles"
            value={user?.roles?.map((r) => r.name).join(", ") || "—"}
          />
          <Field
            label="Permissions"
            value={
              user && user.permissions.length > 0
                ? `${user.permissions.length} granted`
                : "—"
            }
          />
          {user?.last_login_at && (
            <Field
              label="Last login"
              value={new Date(user.last_login_at).toLocaleString()}
            />
          )}
        </CardContent>
      </Card>

      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-lg">Phase 2 placeholder</CardTitle>
          <CardDescription>
            The full {surface} dashboard arrives in {nextPhase}.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
            {upcoming.map((item) => (
              <li
                key={item}
                className="rounded-md border border-border/60 bg-background/40 px-3 py-2"
              >
                {item}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <footer className="text-center text-xs text-muted-foreground">
        <Link href="/" className="hover:text-foreground">
          Back to public site
        </Link>
      </footer>
    </main>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border/60 bg-background/40 px-3 py-2">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 font-medium break-words">{value}</p>
    </div>
  );
}
