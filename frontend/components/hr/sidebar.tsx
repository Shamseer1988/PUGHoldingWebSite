"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bookmark,
  Briefcase,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  ExternalLink,
  FileBarChart,
  Handshake,
  History,
  LayoutDashboard,
  Mailbox,
  Menu as MenuIcon,
  Users,
  UsersRound,
  X,
} from "lucide-react";

import { usePermission } from "@/components/auth/permission";
import { Logo } from "@/components/site/logo";
import {
  ANY_CANDIDATE_VIEW,
  ANY_INTERVIEW_VIEW,
  ANY_JOB_VIEW,
  ANY_REPORT_VIEW,
  PERM_HR_AUDIT_READ,
  PERM_HR_DASHBOARD_VIEW,
  PERM_HR_INTERVIEWS_SCHEDULE,
  PERM_HR_OFFERS_VIEW,
  PERM_HR_REPORTS_VIEW_ALL,
  PERM_HR_USERS_MANAGE,
} from "@/lib/hr/permissions";
import { cn } from "@/lib/utils";

interface NavGroup {
  label: string;
  items: NavLink[];
}

interface NavLink {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  /** Permission gates — link is hidden when the user has none of them. */
  anyOf: readonly string[];
}

const NAV: NavGroup[] = [
  {
    label: "Overview",
    items: [
      {
        label: "Dashboard",
        href: "/hr",
        icon: LayoutDashboard,
        anyOf: [PERM_HR_DASHBOARD_VIEW],
      },
    ],
  },
  {
    label: "Recruitment",
    items: [
      {
        label: "Job openings",
        href: "/hr/jobs",
        icon: Briefcase,
        anyOf: ANY_JOB_VIEW,
      },
      {
        label: "Candidates",
        href: "/hr/candidates",
        icon: Users,
        anyOf: ANY_CANDIDATE_VIEW,
      },
      {
        label: "Interviews",
        href: "/hr/interviews",
        icon: CalendarClock,
        anyOf: ANY_INTERVIEW_VIEW,
      },
      {
        label: "Offers",
        href: "/hr/offers",
        icon: Handshake,
        anyOf: [PERM_HR_OFFERS_VIEW],
      },
      {
        label: "Talent pool",
        href: "/hr/talent-pool",
        icon: Bookmark,
        anyOf: ANY_CANDIDATE_VIEW,
      },
    ],
  },
  {
    label: "Insights",
    items: [
      {
        label: "Reports & export",
        href: "/hr/reports",
        icon: FileBarChart,
        anyOf: ANY_REPORT_VIEW,
      },
      {
        label: "Scheduled digests",
        href: "/hr/scheduled-reports",
        icon: Mailbox,
        // Same permission as the manual-run endpoints — Super Admin,
        // HR Admin, HR Manager, HR Executive, HR Viewer all hold this.
        anyOf: [PERM_HR_REPORTS_VIEW_ALL],
      },
    ],
  },
  {
    label: "System",
    items: [
      {
        label: "HR users & roles",
        href: "/hr/users",
        icon: UsersRound,
        anyOf: [PERM_HR_USERS_MANAGE],
      },
      {
        label: "Scorecard templates",
        href: "/hr/scorecard-templates",
        icon: ClipboardList,
        anyOf: [PERM_HR_INTERVIEWS_SCHEDULE],
      },
      {
        label: "HR audit log",
        href: "/hr/audit",
        icon: History,
        anyOf: [PERM_HR_AUDIT_READ],
      },
    ],
  },
];

interface HrSidebarProps {
  open: boolean;
  onClose: () => void;
  /** Desktop-only icons-only collapse — see admin sidebar for details. */
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
}

export function HrSidebar({
  open,
  onClose,
  collapsed = false,
  onToggleCollapsed,
}: HrSidebarProps) {
  const pathname = usePathname();
  const perms = usePermission();

  // Filter NAV groups + items based on the current user's permissions.
  // A group with zero allowed items is hidden entirely.
  const visibleNav = React.useMemo<NavGroup[]>(() => {
    return NAV.map((group) => ({
      ...group,
      items: group.items.filter((item) => perms.hasAny(item.anyOf)),
    })).filter((group) => group.items.length > 0);
  }, [perms]);

  React.useEffect(() => {
    if (open) onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <>
      {open && (
        <div
          onClick={onClose}
          aria-hidden
          className="fixed inset-0 z-30 bg-background/60 backdrop-blur-sm lg:hidden"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-border/60 bg-background transition-[width,transform] duration-200 lg:translate-x-0",
          "w-64",
          collapsed && "lg:w-16",
          open ? "translate-x-0" : "-translate-x-full"
        )}
        aria-label="HR portal navigation"
      >
        <header
          className={cn(
            "flex items-center border-b border-border/60 px-4 py-4",
            collapsed
              ? "justify-between lg:justify-center lg:px-2"
              : "justify-between"
          )}
        >
          <div
            className={cn("flex items-center gap-2", collapsed && "lg:hidden")}
          >
            <Logo size="sm" />
            <span className="rounded-full bg-pug-gold-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-pug-gold-700 dark:text-pug-gold-300">
              HR
            </span>
          </div>
          {/* Desktop collapse toggle */}
          {onToggleCollapsed && (
            <button
              type="button"
              onClick={onToggleCollapsed}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="hidden h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground lg:inline-flex"
            >
              {collapsed ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <ChevronLeft className="h-4 w-4" />
              )}
            </button>
          )}
          {/* Mobile close */}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close sidebar"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-muted lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <nav
          className={cn(
            "flex-1 overflow-y-auto py-4",
            collapsed ? "px-2 lg:px-2" : "px-3"
          )}
        >
          {visibleNav.map((group) => (
            <div
              key={group.label}
              className={cn("mb-6 last:mb-0", collapsed && "lg:mb-2")}
            >
              <p
                className={cn(
                  "px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground",
                  collapsed && "lg:hidden"
                )}
              >
                {group.label}
              </p>
              <ul
                className={cn(
                  "space-y-0.5",
                  collapsed ? "mt-1 lg:mt-0" : "mt-2"
                )}
              >
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active =
                    pathname === item.href ||
                    (item.href !== "/hr" && pathname?.startsWith(item.href));
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        title={collapsed ? item.label : undefined}
                        className={cn(
                          "group flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                          active
                            ? "bg-primary/10 text-primary"
                            : "text-foreground/80 hover:bg-muted hover:text-foreground",
                          collapsed && "lg:justify-center lg:px-2"
                        )}
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        <span
                          className={cn(
                            "flex-1 truncate",
                            collapsed && "lg:hidden"
                          )}
                        >
                          {item.label}
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <footer className="border-t border-border/60 p-3">
          <Link
            href="/"
            target="_blank"
            title={collapsed ? "Visit public site" : undefined}
            className={cn(
              "inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs text-muted-foreground hover:text-foreground",
              collapsed && "lg:w-full lg:justify-center lg:px-2"
            )}
          >
            <ExternalLink className="h-3.5 w-3.5" />
            <span className={cn(collapsed && "lg:hidden")}>
              Visit public site
            </span>
          </Link>
        </footer>
      </aside>
    </>
  );
}

/**
 * Topbar hamburger — see AdminSidebarOpener for the rationale on the
 * dual-mode click handler.
 */
export function HrSidebarOpener({
  onOpen,
  onToggleCollapsed,
}: {
  onOpen: () => void;
  onToggleCollapsed?: () => void;
}) {
  function handleClick() {
    if (
      onToggleCollapsed &&
      typeof window !== "undefined" &&
      window.innerWidth >= 1024
    ) {
      onToggleCollapsed();
    } else {
      onOpen();
    }
  }
  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label="Toggle sidebar"
      title="Toggle sidebar"
      className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-muted"
    >
      <MenuIcon className="h-5 w-5" />
    </button>
  );
}
