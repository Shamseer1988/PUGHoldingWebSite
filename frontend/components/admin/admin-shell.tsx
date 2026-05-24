"use client";

import * as React from "react";

import { AdminSidebar } from "@/components/admin/sidebar";
import { AdminTopbar } from "@/components/admin/topbar";
import { AuthGuard } from "@/components/auth-guard";

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

  return (
    <AuthGuard loginPath="/admin/login">
      <div className="min-h-screen bg-muted/30 lg:pl-64">
        <AdminSidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
        <AdminTopbar
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
