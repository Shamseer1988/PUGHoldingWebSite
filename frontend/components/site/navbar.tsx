"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Menu, Search, X } from "lucide-react";

import { CompaniesMegaMenu } from "@/components/site/companies-mega-menu";
import { Logo } from "@/components/site/logo";
import { MobileMenu } from "@/components/site/mobile-menu";
import { ThemeToggle } from "@/components/site/theme-toggle";
import { Button } from "@/components/ui/button";
import type { Company } from "@/lib/admin/types";
import { NAV_ITEMS, type NavItem } from "@/lib/site-config";
import { cn } from "@/lib/utils";

interface NavbarProps {
  companies: Company[];
}

export function Navbar({ companies }: NavbarProps) {
  const pathname = usePathname();
  const [scrolled, setScrolled] = React.useState(false);
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [searchOpen, setSearchOpen] = React.useState(false);

  // Add a "scrolled" treatment after a few pixels of scroll.
  React.useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 8);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close the mega menu when the route changes.
  const [openItemHref, setOpenItemHref] = React.useState<string | null>(null);
  React.useEffect(() => {
    setOpenItemHref(null);
  }, [pathname]);

  return (
    <>
      <header
        className={cn(
          "fixed inset-x-0 top-0 z-30 transition-all duration-300",
          scrolled
            ? "border-b border-pug-gold-500/15 bg-background/80 shadow-[0_4px_30px_-12px_rgba(0,0,0,0.12)] backdrop-blur-xl"
            : "bg-transparent"
        )}
      >
        <div className="container mx-auto flex h-16 items-center justify-between gap-3 px-4 sm:h-[72px]">
          <Logo />

          <DesktopNav
            pathname={pathname}
            items={NAV_ITEMS}
            companies={companies}
            openItemHref={openItemHref}
            onOpenChange={setOpenItemHref}
          />

          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={searchOpen ? "Close search" : "Open search"}
              onClick={() => setSearchOpen((s) => !s)}
              className="hidden sm:inline-flex"
            >
              {searchOpen ? (
                <X className="h-4 w-4" />
              ) : (
                <Search className="h-4 w-4" />
              )}
            </Button>
            <ThemeToggle />
            <Button
              variant="ghost"
              size="icon"
              aria-label="Open menu"
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen(true)}
              className="lg:hidden"
            >
              <Menu className="h-5 w-5" />
            </Button>
          </div>
        </div>

        <AnimatePresence>
          {searchOpen && (
            <motion.div
              key="search-panel"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="border-t border-border/40 bg-background/85 backdrop-blur-xl"
            >
              <form
                role="search"
                className="container mx-auto flex items-center gap-2 px-4 py-3"
                onSubmit={(e) => {
                  e.preventDefault();
                }}
              >
                <Search className="h-4 w-4 text-muted-foreground" />
                <input
                  type="search"
                  placeholder="Search the site (coming soon)"
                  className="h-9 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                  aria-label="Search the site"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setSearchOpen(false)}
                >
                  Close
                </Button>
              </form>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      <MobileMenu
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        items={NAV_ITEMS}
        companies={companies}
      />

      {/* Spacer so page content isn't hidden under the fixed header. */}
      <div className="h-16 sm:h-[72px]" aria-hidden />
    </>
  );
}

function DesktopNav({
  items,
  pathname,
  companies,
  openItemHref,
  onOpenChange,
}: {
  items: NavItem[];
  pathname: string | null;
  companies: Company[];
  openItemHref: string | null;
  onOpenChange: (href: string | null) => void;
}) {
  return (
    <nav aria-label="Primary" className="hidden lg:block">
      <ul className="flex items-center gap-1">
        {items.map((item) => (
          <DesktopNavItem
            key={item.href}
            item={item}
            isActive={isActive(pathname, item)}
            companies={companies}
            openItemHref={openItemHref}
            onOpenChange={onOpenChange}
          />
        ))}
      </ul>
    </nav>
  );
}

function DesktopNavItem({
  item,
  isActive,
  companies,
  openItemHref,
  onOpenChange,
}: {
  item: NavItem;
  isActive: boolean;
  companies: Company[];
  openItemHref: string | null;
  onOpenChange: (href: string | null) => void;
}) {
  const hasMega = item.mega === "companies";
  const hasDropdown = (item.children?.length ?? 0) > 0;
  const hasFlyout = hasMega || hasDropdown;

  const closeTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const isOpen = openItemHref === item.href;

  function open() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    onOpenChange(item.href);
  }
  function scheduleClose() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => onOpenChange(null), 140);
  }

  if (!hasFlyout) {
    return (
      <li>
        <NavLink href={item.href} active={isActive}>
          {item.label}
        </NavLink>
      </li>
    );
  }

  return (
    <li
      className="relative"
      onMouseEnter={open}
      onMouseLeave={scheduleClose}
      onFocus={open}
      onBlur={scheduleClose}
    >
      <NavLink
        href={item.href}
        active={isActive}
        chevron
        chevronOpen={isOpen}
        ariaExpanded={isOpen}
      >
        {item.label}
      </NavLink>

      <AnimatePresence>
        {isOpen && hasMega && (
          <MegaWrapper key="mega-companies">
            <CompaniesMegaMenu companies={companies} />
          </MegaWrapper>
        )}
        {isOpen && hasDropdown && !hasMega && (
          <DropdownWrapper key="dropdown">
            <ul role="menu" className="space-y-0.5">
              {item.children!.map((child) => (
                <li key={child.href} role="none">
                  <Link
                    href={child.href}
                    role="menuitem"
                    className="group/row flex items-start gap-3 rounded-md px-3 py-2.5 transition-colors hover:bg-muted/60"
                  >
                    <span className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-pug-gold-500 transition-transform group-hover/row:scale-150" />
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-foreground group-hover/row:text-primary">
                        {child.label}
                      </span>
                      {child.description && (
                        <span className="block text-xs text-muted-foreground">
                          {child.description}
                        </span>
                      )}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </DropdownWrapper>
        )}
      </AnimatePresence>
    </li>
  );
}

function NavLink({
  href,
  active,
  chevron,
  chevronOpen,
  ariaExpanded,
  children,
}: {
  href: string;
  active: boolean;
  chevron?: boolean;
  chevronOpen?: boolean;
  ariaExpanded?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-haspopup={chevron ? "menu" : undefined}
      aria-expanded={ariaExpanded}
      className={cn(
        "relative inline-flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium transition-colors",
        active ? "text-primary" : "text-foreground/80 hover:text-foreground"
      )}
    >
      <span className="relative">
        {children}
        {active && (
          <span
            aria-hidden
            className="absolute -bottom-1 left-1/2 h-[2px] w-6 -translate-x-1/2 rounded-full bg-gradient-to-r from-pug-gold-500 to-pug-green-500"
          />
        )}
      </span>
      {chevron && (
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 transition-transform",
            chevronOpen && "rotate-180"
          )}
        />
      )}
    </Link>
  );
}

function MegaWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 4, scale: 0.98 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className="fixed left-1/2 top-[60px] z-40 w-[min(96vw,1100px)] -translate-x-1/2 sm:top-[76px]"
    >
      {/* Hover bridge so the menu doesn't snap shut between trigger and panel */}
      <div aria-hidden className="h-2" />
      {children}
    </motion.div>
  );
}

function DropdownWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      transition={{ duration: 0.15 }}
      className="absolute left-1/2 top-full mt-2 w-72 -translate-x-1/2"
    >
      <div className="rounded-xl border border-pug-gold-500/20 bg-background/95 p-2 shadow-2xl backdrop-blur-xl">
        {children}
      </div>
    </motion.div>
  );
}

function isActive(pathname: string | null, item: NavItem): boolean {
  if (!pathname) return false;
  if (pathname === item.href) return true;
  if (item.href !== "/" && pathname.startsWith(item.href)) return true;
  if (item.children?.some((c) => pathname.startsWith(c.href.split("?")[0]))) {
    return true;
  }
  return false;
}
