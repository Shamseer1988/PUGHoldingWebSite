"use client";

import * as React from "react";

import { AdminSidebar } from "@/components/admin/sidebar";
import { AdminTopbar } from "@/components/admin/topbar";
import { AuthGuard } from "@/components/auth-guard";
import { useSidebarCollapsed } from "@/lib/use-sidebar-collapsed";
import { cn } from "@/lib/utils";

interface AdminShellProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}

export function AdminShell({
  title,
  description,
  actions,
  children,
}: AdminShellProps) {
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  // Persists desktop "icons only" collapse state across navigation.
  const { collapsed, toggle: toggleCollapsed } = useSidebarCollapsed();

  return (
    <AuthGuard loginPath="/admin/login">
      <div
        className={cn(
          "min-h-screen bg-muted/30 transition-[padding-left] duration-200",
          collapsed ? "lg:pl-16" : "lg:pl-64"
        )}
      >
        <AdminSidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          collapsed={collapsed}
          onToggleCollapsed={toggleCollapsed}
        />
        <AdminTopbar
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
