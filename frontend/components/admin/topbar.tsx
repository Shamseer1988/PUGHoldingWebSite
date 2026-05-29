"use client";

import * as React from "react";
import { LogOut, User } from "lucide-react";

import { AdminSidebarOpener } from "@/components/admin/sidebar";
import { useAuth } from "@/components/auth-provider";
import { ThemeToggle } from "@/components/site/theme-toggle";
import { Button } from "@/components/ui/button";

interface AdminTopbarProps {
  title: string;
  description?: string;
  onOpenSidebar: () => void;
  /** Desktop-only: toggles the icons-only sidebar collapse. The same
   *  hamburger button uses this on lg+ and ``onOpenSidebar`` on
   *  smaller viewports. */
  onToggleCollapsed?: () => void;
  actions?: React.ReactNode;
}

export function AdminTopbar({
  title,
  description,
  onOpenSidebar,
  onToggleCollapsed,
  actions,
}: AdminTopbarProps) {
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
    <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-border/60 bg-background/85 px-4 py-3 backdrop-blur sm:px-6">
      <AdminSidebarOpener
        onOpen={onOpenSidebar}
        onToggleCollapsed={onToggleCollapsed}
      />
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-base font-semibold tracking-tight sm:text-lg">
          {title}
        </h1>
        {description && (
          <p className="truncate text-xs text-muted-foreground sm:text-sm">
            {description}
          </p>
        )}
      </div>

      <div className="flex items-center gap-1.5">
        {actions}
        <ThemeToggle />
        <span
          className="hidden items-center gap-2 rounded-full border border-border/60 bg-background/60 px-2 py-1 text-xs font-medium sm:inline-flex"
          title={user?.email ?? ""}
        >
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-primary">
            <User className="h-3 w-3" />
          </span>
          <span className="hidden max-w-[10rem] truncate md:inline">
            {user?.full_name ?? user?.email}
          </span>
        </span>
        <Button
          variant="ghost"
          size="icon"
          onClick={onLogout}
          disabled={signingOut}
          aria-label="Sign out"
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
