"use client";

import * as React from "react";

import { AuthGuard } from "@/components/auth-guard";
import { HrSidebar } from "@/components/hr/sidebar";
import { HrTopbar } from "@/components/hr/topbar";

interface HrShellProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}

export function HrShell({
  title,
  description,
  actions,
  children,
}: HrShellProps) {
  const [sidebarOpen, setSidebarOpen] = React.useState(false);

  return (
    <AuthGuard loginPath="/hr/login">
      <div className="min-h-screen bg-muted/30 lg:pl-64">
        <HrSidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
        <HrTopbar
          title={title}
          description={description}
          actions={actions}
          onOpenSidebar={() => setSidebarOpen(true)}
        />
        <main className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </AuthGuard>
  );
}
