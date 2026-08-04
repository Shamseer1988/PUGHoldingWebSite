"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  Brain,
  Building2,
  ChevronLeft,
  ChevronRight,
  DatabaseBackup,
  ExternalLink,
  FileText,
  History,
  Image as ImageIcon,
  Inbox,
  LayoutDashboard,
  ListTree,
  Mail,
  Megaphone,
  Menu as MenuIcon,
  MessageSquareQuote,
  QrCode,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Tag,
  Users,
  Wrench,
  X,
} from "lucide-react";

import { usePermission } from "@/components/auth/permission";
import { Logo } from "@/components/site/logo";
import { useAuth } from "@/components/auth-provider";
import { cn } from "@/lib/utils";


// Permission keys — kept inline here rather than imported from
// permissions.ts (HR-side) because the website-admin perms live in
// the seed_users catalogue and aren't otherwise re-exported. If the
// keys ever drift, ``test_marketing_role_isolation.py`` on the
// backend will fail loudly and point at the right pair.
const PERM_WEBSITE_DASHBOARD = "website.dashboard.read";
const PERM_WEBSITE_CONTENT_READ = "website.content.read";
const PERM_WEBSITE_CONTENT_WRITE = "website.content.write";
const PERM_WEBSITE_SETTINGS_READ = "website.settings.read";
const PERM_WEBSITE_USERS_MANAGE = "website.users.manage";
const PERM_WEBSITE_AUDIT_READ = "website.audit.read";
const PERM_WEBSITE_MENU_READ = "website.menu.read";

const PERM_MARKETING_DASHBOARD = "marketing:dashboard:view";
const PERM_MARKETING_CAMPAIGNS_READ = "marketing:campaigns:read";
const PERM_MARKETING_CATALOGUES_READ = "marketing:catalogues:read";
const PERM_MARKETING_SHORT_URLS_READ = "marketing:short_urls:read";
const PERM_MARKETING_QR_CODES_READ = "marketing:qr_codes:read";


interface NavGroup {
  label: string;
  items: NavLink[];
}

interface NavLink {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  /** When set, this item is only rendered for users who satisfy the
   *  named gate. ``system`` covers any user with the system scope or
   *  the superuser flag. ``superuser`` is stricter — only accounts
   *  with ``is_superuser = true`` see it (used for backup / restore,
   *  which can wipe the database). */
  requiresScope?: "system" | "superuser";
  /** When set, the user must hold at least one of these permission
   *  keys for the item to render. Superusers always see everything.
   *  Marketing-only users (no website perms) get the non-marketing
   *  sections filtered out via this list. */
  requiresAnyPermission?: readonly string[];
}

// Every item that ISN'T under /admin/marketing/* requires at least
// one website.* permission key. Marketing-only roles carry zero
// website perms so the entire non-marketing sidebar collapses for
// them. Items that need stricter access (system scope / superuser)
// keep ``requiresScope`` on top.
const NAV: NavGroup[] = [
  {
    label: "Overview",
    items: [
      {
        label: "Dashboard",
        href: "/admin",
        icon: LayoutDashboard,
        requiresAnyPermission: [PERM_WEBSITE_DASHBOARD],
      },
    ],
  },
  {
    label: "Content",
    items: [
      {
        label: "Hero slides",
        href: "/admin/hero-slides",
        icon: BarChart3,
        requiresAnyPermission: [
          PERM_WEBSITE_CONTENT_READ,
          PERM_WEBSITE_CONTENT_WRITE,
        ],
      },
      {
        label: "Companies",
        href: "/admin/companies",
        icon: Building2,
        requiresAnyPermission: [
          PERM_WEBSITE_CONTENT_READ,
          PERM_WEBSITE_CONTENT_WRITE,
        ],
      },
      {
        label: "Leadership",
        href: "/admin/leadership",
        icon: MessageSquareQuote,
        requiresAnyPermission: [
          PERM_WEBSITE_CONTENT_READ,
          PERM_WEBSITE_CONTENT_WRITE,
        ],
      },
      {
        label: "Trusted brands",
        href: "/admin/brands",
        icon: Sparkles,
        requiresAnyPermission: [
          PERM_WEBSITE_CONTENT_READ,
          PERM_WEBSITE_CONTENT_WRITE,
        ],
      },
      {
        label: "News & events",
        href: "/admin/news",
        icon: Megaphone,
        requiresAnyPermission: [
          PERM_WEBSITE_CONTENT_READ,
          PERM_WEBSITE_CONTENT_WRITE,
        ],
      },
      {
        label: "Media gallery",
        href: "/admin/media",
        icon: ImageIcon,
        requiresAnyPermission: [
          PERM_WEBSITE_CONTENT_READ,
          PERM_WEBSITE_CONTENT_WRITE,
        ],
      },
      {
        label: "Pages",
        href: "/admin/pages",
        icon: FileText,
        requiresAnyPermission: [
          PERM_WEBSITE_CONTENT_READ,
          PERM_WEBSITE_CONTENT_WRITE,
        ],
      },
      {
        label: "Navigation menu",
        href: "/admin/menu",
        icon: ListTree,
        requiresAnyPermission: [PERM_WEBSITE_MENU_READ],
      },
    ],
  },
  {
    label: "Engagement",
    items: [
      {
        label: "Contact inbox",
        href: "/admin/inbox",
        icon: Inbox,
        requiresAnyPermission: [
          PERM_WEBSITE_CONTENT_READ,
          PERM_WEBSITE_CONTENT_WRITE,
        ],
      },
      {
        label: "Newsletter",
        href: "/admin/subscribers",
        icon: Mail,
        requiresAnyPermission: [
          PERM_WEBSITE_CONTENT_READ,
          PERM_WEBSITE_CONTENT_WRITE,
        ],
      },
    ],
  },
  {
    label: "Marketing",
    items: [
      {
        label: "Dashboard",
        href: "/admin/marketing/dashboard",
        icon: LayoutDashboard,
        requiresAnyPermission: [PERM_MARKETING_DASHBOARD],
      },
      {
        label: "Offer campaigns",
        href: "/admin/marketing/campaigns",
        icon: Tag,
        requiresAnyPermission: [PERM_MARKETING_CAMPAIGNS_READ],
      },
      {
        label: "Catalogues",
        href: "/admin/marketing/catalogues",
        icon: BookOpen,
        requiresAnyPermission: [PERM_MARKETING_CATALOGUES_READ],
      },
      {
        label: "QR Codes",
        href: "/admin/marketing/qr-codes",
        icon: QrCode,
        requiresAnyPermission: [PERM_MARKETING_QR_CODES_READ],
      },
      {
        label: "Tools",
        href: "/admin/marketing/tools",
        icon: Wrench,
        requiresAnyPermission: [PERM_MARKETING_SHORT_URLS_READ],
      },
    ],
  },
  {
    label: "System",
    items: [
      {
        label: "Site settings",
        href: "/admin/settings",
        icon: Settings,
        requiresAnyPermission: [PERM_WEBSITE_SETTINGS_READ],
      },
      {
        label: "SEO configuration",
        href: "/admin/seo",
        icon: Search,
        requiresAnyPermission: [PERM_WEBSITE_SETTINGS_READ],
      },
      {
        label: "Email configuration",
        href: "/admin/email-settings",
        icon: Send,
        requiresScope: "system",
      },
      {
        label: "AI settings",
        href: "/admin/ai-settings",
        icon: Brain,
        requiresScope: "system",
      },
      {
        label: "Approval flow",
        href: "/admin/recruitment-settings",
        icon: ShieldCheck,
        requiresScope: "superuser",
      },
      {
        label: "Users & roles",
        href: "/admin/users",
        icon: Users,
        requiresAnyPermission: [PERM_WEBSITE_USERS_MANAGE],
      },
      {
        label: "Permission matrix",
        href: "/admin/roles",
        icon: ShieldCheck,
        requiresScope: "system",
      },
      {
        label: "Database backup",
        href: "/admin/backup",
        icon: DatabaseBackup,
        requiresScope: "superuser",
      },
      {
        label: "Audit log",
        href: "/admin/audit",
        icon: History,
        requiresAnyPermission: [PERM_WEBSITE_AUDIT_READ],
      },
    ],
  },
];

interface AdminSidebarProps {
  open: boolean;
  onClose: () => void;
  /** Desktop-only: when true, the sidebar shrinks to icon-only and
   *  labels + group headings hide on lg+. Mobile drawer keeps full
   *  labels regardless. */
  collapsed?: boolean;
  /** Callback for the in-sidebar chevron that flips collapsed. */
  onToggleCollapsed?: () => void;
}

export function AdminSidebar({
  open,
  onClose,
  collapsed = false,
  onToggleCollapsed,
}: AdminSidebarProps) {
  const pathname = usePathname();
  const { user } = useAuth();
  const perms = usePermission();
  // System scope is granted by the explicit "system" scope or by the
  // superuser flag (which the backend also treats as system access).
  const hasSystem = Boolean(
    user?.is_superuser || user?.scopes?.includes("system")
  );
  const isSuperuser = Boolean(user?.is_superuser);

  // Close mobile drawer on route change
  React.useEffect(() => {
    if (open) onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // Hide nav items the current user can't actually open, then drop any
  // group that ends up empty.
  const canOpen = (item: NavLink): boolean => {
    // Scope gate first (cheapest + the strictest deny).
    if (item.requiresScope === "system" && !hasSystem) return false;
    if (item.requiresScope === "superuser" && !isSuperuser) return false;
    // Then permission gate. ``superuser`` short-circuits inside
    // ``usePermission().hasAny`` so the operator's view is unchanged.
    if (
      item.requiresAnyPermission &&
      !perms.hasAny(item.requiresAnyPermission)
    ) {
      return false;
    }
    return true;
  };
  const visibleGroups = NAV.map((group) => ({
    ...group,
    items: group.items.filter(canOpen),
  })).filter((group) => group.items.length > 0);

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
          "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-border/60 bg-background transition-[width,transform] duration-200 lg:translate-x-0",
          // Mobile drawer is always full width; on lg+ width depends on collapsed.
          "w-64",
          collapsed && "lg:w-16",
          open ? "translate-x-0" : "-translate-x-full"
        )}
        aria-label="Website admin navigation"
      >
        <header
          className={cn(
            "flex items-center border-b border-border/60 px-4 py-4",
            collapsed
              ? "justify-between lg:justify-center lg:px-2"
              : "justify-between"
          )}
        >
          <div className={cn(collapsed && "lg:hidden")}>
            <Logo size="sm" />
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
          {visibleGroups.map((group) => (
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
                className={cn("space-y-0.5", collapsed ? "mt-1 lg:mt-0" : "mt-2")}
              >
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active =
                    pathname === item.href ||
                    (item.href !== "/admin" && pathname?.startsWith(item.href));
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
                        {item.badge && (
                          <span
                            className={cn(
                              "rounded-full bg-pug-gold-500/20 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-pug-gold-700 dark:text-pug-gold-300",
                              collapsed && "lg:hidden"
                            )}
                          >
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
 * Topbar hamburger. Visible on every breakpoint:
 *  - On mobile (<lg): toggles the off-canvas drawer via ``onOpen``.
 *  - On lg+ desktop: toggles the icons-only collapse via
 *    ``onToggleCollapsed``.
 *
 * The two callbacks are independent so the shell can drive each
 * state separately. The button picks at click time based on the
 * Tailwind ``lg`` breakpoint (1024 px) so it always does the right
 * thing for the current viewport.
 */
export function AdminSidebarOpener({
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
