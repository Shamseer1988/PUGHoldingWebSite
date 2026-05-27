"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Briefcase,
  CalendarClock,
  ExternalLink,
  FileBarChart,
  Handshake,
  History,
  LayoutDashboard,
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
  PERM_HR_OFFERS_VIEW,
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
}

export function HrSidebar({ open, onClose }: HrSidebarProps) {
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
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border/60 bg-background transition-transform lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
        aria-label="HR portal navigation"
      >
        <header className="flex items-center justify-between border-b border-border/60 px-4 py-4">
          <div className="flex items-center gap-2">
            <Logo size="sm" />
            <span className="rounded-full bg-pug-gold-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-pug-gold-700 dark:text-pug-gold-300">
              HR
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close sidebar"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-muted lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {visibleNav.map((group) => (
            <div key={group.label} className="mb-6 last:mb-0">
              <p className="px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                {group.label}
              </p>
              <ul className="mt-2 space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active =
                    pathname === item.href ||
                    (item.href !== "/hr" && pathname?.startsWith(item.href));
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        className={cn(
                          "group flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                          active
                            ? "bg-primary/10 text-primary"
                            : "text-foreground/80 hover:bg-muted hover:text-foreground"
                        )}
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        <span className="flex-1 truncate">{item.label}</span>
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
            className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs text-muted-foreground hover:text-foreground"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Visit public site
          </Link>
        </footer>
      </aside>
    </>
  );
}

export function HrSidebarOpener({ onOpen }: { onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label="Open sidebar"
      className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-muted lg:hidden"
    >
      <MenuIcon className="h-5 w-5" />
    </button>
  );
}
