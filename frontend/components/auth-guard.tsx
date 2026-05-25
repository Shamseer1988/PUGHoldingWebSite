"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth-provider";

interface AuthGuardProps {
  /** Where unauthenticated users should be sent. */
  loginPath: string;
  children: React.ReactNode;
}

export function AuthGuard({ loginPath, children }: AuthGuardProps) {
  const { status } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(loginPath);
    }
  }, [status, loginPath, router]);

  if (status !== "authenticated") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        <span className="sr-only">Checking session…</span>
      </div>
    );
  }

  return <>{children}</>;
}
