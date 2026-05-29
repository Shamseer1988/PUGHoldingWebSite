"use client";

import * as React from "react";

import { AuthGuard } from "@/components/auth-guard";
import { HrSidebar } from "@/components/hr/sidebar";
import { HrTopbar } from "@/components/hr/topbar";
import { useSidebarCollapsed } from "@/lib/use-sidebar-collapsed";
import { cn } from "@/lib/utils";

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
  const { collapsed, toggle: toggleCollapsed } = useSidebarCollapsed();

  return (
    <AuthGuard loginPath="/hr/login">
      <div
        className={cn(
          "min-h-screen bg-muted/30 transition-[padding-left] duration-200",
          collapsed ? "lg:pl-16" : "lg:pl-64"
        )}
      >
        <HrSidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          collapsed={collapsed}
          onToggleCollapsed={toggleCollapsed}
        />
        <HrTopbar
          title={title}
          description={description}
          actions={actions}
          onOpenSidebar={() => setSidebarOpen(true)}
          onToggleCollapsed={toggleCollapsed}
        />
        <main className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </AuthGuard>
  );
}
