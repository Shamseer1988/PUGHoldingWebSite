"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { ChevronDown, Menu, Search, X } from "lucide-react";

import { Logo } from "@/components/site/logo";
import { MobileMenu } from "@/components/site/mobile-menu";
import { ThemeToggle } from "@/components/site/theme-toggle";
import { Button } from "@/components/ui/button";
import { NAV_ITEMS, type NavItem } from "@/lib/site-config";
import { cn } from "@/lib/utils";

export function Navbar() {
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

  return (
    <>
      <header
        className={cn(
          "fixed inset-x-0 top-0 z-30 transition-all duration-300",
          scrolled
            ? "border-b border-border/60 bg-background/70 backdrop-blur-xl"
            : "bg-transparent"
        )}
      >
        <div className="container mx-auto flex h-16 items-center justify-between gap-3 px-4 sm:h-[72px]">
          <Logo />

          <DesktopNav pathname={pathname} items={NAV_ITEMS} />

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

        {/* Search panel (Phase 3: UI only; wires to backend in Phase 6) */}
        {searchOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="border-t border-border/60 bg-background/85 backdrop-blur-xl"
          >
            <form
              role="search"
              className="container mx-auto flex items-center gap-2 px-4 py-3"
              onSubmit={(e) => {
                e.preventDefault();
                // Phase 6 wires this to a real search API.
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
      </header>

      <MobileMenu
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        items={NAV_ITEMS}
      />

      {/* Spacer so page content isn't hidden under the fixed header. */}
      <div className="h-16 sm:h-[72px]" aria-hidden />
    </>
  );
}

function DesktopNav({
  items,
  pathname,
}: {
  items: NavItem[];
  pathname: string | null;
}) {
  return (
    <nav aria-label="Primary" className="hidden lg:block">
      <ul className="flex items-center gap-1">
        {items.map((item) => (
          <DesktopNavItem
            key={item.href}
            item={item}
            isActive={isActive(pathname, item)}
          />
        ))}
      </ul>
    </nav>
  );
}

function DesktopNavItem({ item, isActive }: { item: NavItem; isActive: boolean }) {
  const hasChildren = (item.children?.length ?? 0) > 0;
  const [hovered, setHovered] = React.useState(false);
  const closeTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  function open() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setHovered(true);
  }
  function scheduleClose() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setHovered(false), 120);
  }

  if (!hasChildren) {
    return (
      <li>
        <Link
          href={item.href}
          className={cn(
            "rounded-md px-3 py-2 text-sm font-medium transition-colors",
            isActive
              ? "text-primary"
              : "text-foreground/80 hover:text-foreground"
          )}
        >
          {item.label}
        </Link>
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
      <Link
        href={item.href}
        className={cn(
          "inline-flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "text-primary"
            : "text-foreground/80 hover:text-foreground"
        )}
        aria-haspopup="menu"
        aria-expanded={hovered}
      >
        {item.label}
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 transition-transform",
            hovered && "rotate-180"
          )}
        />
      </Link>

      {hovered && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.15 }}
          className="absolute left-1/2 top-full mt-2 w-60 -translate-x-1/2"
        >
          <ul
            role="menu"
            className="rounded-xl border border-border/60 bg-background/95 p-2 shadow-xl backdrop-blur-xl"
          >
            {item.children!.map((child) => (
              <li key={child.href} role="none">
                <Link
                  href={child.href}
                  role="menuitem"
                  className="block rounded-md px-3 py-2 text-sm text-foreground/90 hover:bg-muted hover:text-foreground"
                >
                  {child.label}
                </Link>
              </li>
            ))}
          </ul>
        </motion.div>
      )}
    </li>
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
