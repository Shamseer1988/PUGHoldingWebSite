"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Brain,
  Building2,
  ExternalLink,
  FileText,
  History,
  Image as ImageIcon,
  Inbox,
  LayoutDashboard,
  Mail,
  Megaphone,
  Menu as MenuIcon,
  MessageSquareQuote,
  Settings,
  Users,
  X,
} from "lucide-react";

import { Logo } from "@/components/site/logo";
import { cn } from "@/lib/utils";

interface NavGroup {
  label: string;
  items: NavLink[];
}

interface NavLink {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

const NAV: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { label: "Dashboard", href: "/admin", icon: LayoutDashboard },
    ],
  },
  {
    label: "Content",
    items: [
      { label: "Hero slides", href: "/admin/hero-slides", icon: BarChart3 },
      { label: "Companies", href: "/admin/companies", icon: Building2 },
      { label: "Leadership", href: "/admin/leadership", icon: MessageSquareQuote },
      { label: "News & events", href: "/admin/news", icon: Megaphone },
      { label: "Media gallery", href: "/admin/media", icon: ImageIcon },
      { label: "Pages", href: "/admin/pages", icon: FileText },
    ],
  },
  {
    label: "Engagement",
    items: [
      { label: "Contact inbox", href: "/admin/inbox", icon: Inbox },
      { label: "Newsletter", href: "/admin/subscribers", icon: Mail },
    ],
  },
  {
    label: "System",
    items: [
      { label: "Site settings", href: "/admin/settings", icon: Settings },
      { label: "AI settings", href: "/admin/ai-settings", icon: Brain },
      { label: "Users & roles", href: "/admin/users", icon: Users },
      { label: "Audit log", href: "/admin/audit", icon: History },
    ],
  },
];

interface AdminSidebarProps {
  open: boolean;
  onClose: () => void;
}

export function AdminSidebar({ open, onClose }: AdminSidebarProps) {
  const pathname = usePathname();

  // Close mobile drawer on route change
  React.useEffect(() => {
    if (open) onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <>
      {/* Mobile backdrop */}
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
        aria-label="Website admin navigation"
      >
        <header className="flex items-center justify-between border-b border-border/60 px-4 py-4">
          <Logo size="sm" />
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
          {NAV.map((group) => (
            <div key={group.label} className="mb-6 last:mb-0">
              <p className="px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                {group.label}
              </p>
              <ul className="mt-2 space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active =
                    pathname === item.href ||
                    (item.href !== "/admin" && pathname?.startsWith(item.href));
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
                        {item.badge && (
                          <span className="rounded-full bg-pug-gold-500/20 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-pug-gold-700 dark:text-pug-gold-300">
                            {item.badge}
                          </span>
                        )}
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

export function AdminSidebarOpener({ onOpen }: { onOpen: () => void }) {
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
