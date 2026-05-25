"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  ChevronDown,
  Menu,
  Search,
  X,
} from "lucide-react";

import { CompaniesMegaMenu } from "@/components/site/companies-mega-menu";
import { Logo } from "@/components/site/logo";
import { MobileMenu } from "@/components/site/mobile-menu";
import { ThemeToggle } from "@/components/site/theme-toggle";
import { Button } from "@/components/ui/button";
import type { Company } from "@/lib/admin/types";
import { NAV_ITEMS, PRIMARY_CTA, type NavItem } from "@/lib/site-config";
import { cn } from "@/lib/utils";

interface NavbarProps {
  companies: Company[];
  /** Backend-controlled navigation tree. Falls back to the compiled-in
   *  defaults so the navbar always has something to render. */
  items?: NavItem[];
}

/**
 * Public site header — inset rounded glass chrome, centred nav, three
 * circular icon controls + a gold "Join Us" pill on the right.
 *
 * Visuals:
 *   - Fixed at the top, but the visible bar is a max-w-7xl inset
 *     container with a `rounded-[28px]` glass surface, thin
 *     pug-gold/pug-white border, and a soft shadow.
 *   - Light: bg-background/90 backdrop-blur, pug-gold-500/20 border.
 *   - Dark : bg-pug-green-950/85 backdrop-blur, white/10 border.
 *
 * Behaviour: the existing mega-menu + dropdown + scroll-tracking
 * logic is preserved verbatim. The only structural change is the
 * three-column grid layout (logo | centered nav | right controls)
 * so the nav can sit perfectly centred while the logo + actions
 * own their own edges.
 */
export function Navbar({ companies, items }: NavbarProps) {
  const pathname = usePathname();
  const [scrolled, setScrolled] = React.useState(false);
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [searchOpen, setSearchOpen] = React.useState(false);
  const [openItemHref, setOpenItemHref] = React.useState<string | null>(null);
  const navItems = items ?? NAV_ITEMS;

  React.useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 8);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  React.useEffect(() => {
    setOpenItemHref(null);
  }, [pathname]);

  return (
    <>
      {/* Fixed wrapper — anchors the inset chrome and lets us drive
          scroll-state styling without resizing the rounded container. */}
      <header className="fixed inset-x-0 top-0 z-30">
        <div className="container mx-auto px-3 pt-2 sm:px-4 sm:pt-3">
          <div
            className={cn(
              "relative isolate mx-auto flex items-center gap-3 rounded-[20px] border px-3 py-1.5 transition-shadow duration-300 sm:rounded-[26px] sm:px-5 sm:py-2",
              // Surface: solid glass at all times so the floating
              // chrome reads cleanly over any page background.
              "bg-background/90 backdrop-blur-xl",
              "dark:bg-pug-green-950/85",
              // Border + shadow strength react to scroll position so
              // the chrome "lifts" slightly when scrolling.
              scrolled
                ? "border-pug-gold-500/25 shadow-[0_10px_40px_-18px_rgba(15,42,28,0.35)] dark:border-white/10 dark:shadow-[0_10px_40px_-18px_rgba(0,0,0,0.6)]"
                : "border-pug-gold-500/15 shadow-[0_4px_24px_-16px_rgba(15,42,28,0.25)] dark:border-white/[0.06] dark:shadow-[0_4px_24px_-16px_rgba(0,0,0,0.45)]"
            )}
          >
            {/* Three-column grid: logo | centered nav | controls.
                Grid (not flex) so the nav stays visually centred on
                the page, not centred between the logo and the controls. */}
            <div className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-3">
              <Logo />

              <div className="hidden justify-center lg:flex">
                <DesktopNav
                  pathname={pathname}
                  items={navItems}
                  companies={companies}
                  openItemHref={openItemHref}
                  onOpenChange={setOpenItemHref}
                />
              </div>

              <div className="flex items-center justify-end gap-1.5">
                <NavIconButton
                  aria-label={searchOpen ? "Close search" : "Open search"}
                  aria-expanded={searchOpen}
                  onClick={() => setSearchOpen((s) => !s)}
                  className="hidden sm:inline-flex"
                >
                  {searchOpen ? (
                    <X className="h-4 w-4" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                </NavIconButton>

                {/* ThemeToggle accepts `className` — we override the
                    base Button's size/shape to match NavIconButton. */}
                <ThemeToggle
                  className={cn(NAV_ICON_BUTTON_CLASSES, "hidden sm:inline-flex")}
                />

                <Button
                  asChild
                  size="sm"
                  className={cn(
                    // Gold gradient pill with a subtle hover lift.
                    "hidden h-10 rounded-full bg-gradient-to-r from-pug-gold-600 to-pug-gold-500 px-5 text-sm font-semibold text-pug-green-950 shadow-[0_6px_22px_-12px_rgba(166,124,58,0.55)] motion-safe:transition-all motion-safe:duration-200 motion-safe:hover:-translate-y-0.5 hover:from-pug-gold-500 hover:to-pug-gold-400 hover:text-pug-green-950 hover:shadow-[0_10px_28px_-12px_rgba(166,124,58,0.6)] focus-visible:ring-pug-gold-500 sm:inline-flex",
                    "dark:text-pug-green-950"
                  )}
                >
                  <Link href={PRIMARY_CTA.href}>
                    {PRIMARY_CTA.label}
                    <ArrowRight
                      className="h-4 w-4 motion-safe:transition-transform group-hover:translate-x-0.5"
                      aria-hidden
                    />
                  </Link>
                </Button>

                <NavIconButton
                  aria-label="Open menu"
                  aria-expanded={mobileOpen}
                  onClick={() => setMobileOpen(true)}
                  className="lg:hidden"
                >
                  <Menu className="h-5 w-5" />
                </NavIconButton>
              </div>
            </div>

            <AnimatePresence>
              {searchOpen && (
                <motion.div
                  key="search-panel"
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.18, ease: "easeOut" }}
                  className="mt-1.5 overflow-hidden rounded-full border border-border/40 bg-background/95 backdrop-blur-xl"
                >
                  <form
                    role="search"
                    className="flex h-10 items-center gap-2 pl-4 pr-1.5"
                    onSubmit={(e) => {
                      e.preventDefault();
                    }}
                  >
                    <Search
                      className="h-4 w-4 shrink-0 text-muted-foreground"
                      aria-hidden
                    />
                    <input
                      type="search"
                      placeholder="Search the site (coming soon)"
                      className="h-full w-full bg-transparent text-sm leading-none outline-none placeholder:text-muted-foreground"
                      aria-label="Search the site"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setSearchOpen(false)}
                      className="h-7 rounded-full px-3 text-xs"
                    >
                      Close
                    </Button>
                  </form>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </header>

      <MobileMenu
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        items={navItems}
        companies={companies}
      />

      {/* Spacer so page content isn't hidden under the floating chrome.
          Matches the inset header height + its top padding:
          mobile  = pt-2 (8) + py-1.5*2 (12) + 40 content + 2 border ≈ 62
          desktop = pt-3 (12) + py-2*2 (16) + 40 content + 2 border ≈ 70 */}
      <div className="h-[64px] sm:h-[72px]" aria-hidden />
    </>
  );
}


// ---------------------------------------------------------------------------
// Circular icon button — used for Search, Theme, and the mobile menu.
// Style: 44x44 (40x40 on small screens), rounded-full, thin pug-gold
// border, soft gold-tint hover. Kept local so the shared Button
// variants stay clean for the rest of the app.
// ---------------------------------------------------------------------------


const NAV_ICON_BUTTON_CLASSES =
  "inline-flex h-9 w-9 items-center justify-center rounded-full border border-pug-gold-500/25 bg-transparent text-foreground/80 transition-colors hover:border-pug-gold-500/40 hover:bg-pug-gold-500/10 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pug-gold-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 dark:border-white/15 dark:hover:border-pug-gold-300/40 sm:h-10 sm:w-10";


function NavIconButton({
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" className={cn(NAV_ICON_BUTTON_CLASSES, className)} {...props}>
      {children}
    </button>
  );
}


// ---------------------------------------------------------------------------
// Desktop nav — centered list. Behaviour preserved verbatim from the
// previous implementation; styling refined.
// ---------------------------------------------------------------------------


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
    <nav aria-label="Primary">
      <ul className="flex items-center gap-0.5">
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


/**
 * Top-level nav link.
 *
 * Visual treatment:
 *   - Active: 3px gold dot 4px below the label (matches the reference
 *     image's "Home" indicator).
 *   - Hover (non-active): a soft 80% gold underline grows from centre
 *     via `scaleX 0 → 1` on `motion-safe:` only.
 *   - Dropdown items (mega + children) keep the chevron icon; plain
 *     links don't show one.
 */
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
      aria-current={active ? "page" : undefined}
      className={cn(
        "group/nav relative inline-flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "text-pug-green-900 dark:text-pug-gold-100"
          : "text-foreground/75 hover:text-foreground dark:text-foreground/80 dark:hover:text-foreground"
      )}
    >
      <span className="relative">
        {children}
        {active ? (
          <span
            aria-hidden
            className="absolute -bottom-2 left-1/2 block h-[3px] w-[3px] -translate-x-1/2 rounded-full bg-pug-gold-500 shadow-[0_0_0_2px_rgba(212,165,82,0.18)]"
          />
        ) : (
          <span
            aria-hidden
            className="pointer-events-none absolute -bottom-1.5 left-0 right-0 h-px origin-center scale-x-0 bg-gradient-to-r from-transparent via-pug-gold-500/70 to-transparent motion-safe:transition-transform motion-safe:duration-200 group-hover/nav:scale-x-100"
          />
        )}
      </span>
      {chevron && (
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 text-foreground/60 transition-transform",
            chevronOpen && "rotate-180"
          )}
          aria-hidden
        />
      )}
    </Link>
  );
}


function MegaWrapper({ children }: { children: React.ReactNode }) {
  // Positioning lives on the static outer div so Tailwind's translate
  // isn't overwritten by Framer Motion's inline transform on the
  // animated child. Width capped via inline style so it's not subject
  // to Tailwind JIT picking up arbitrary-value classes.
  return (
    <div className="pointer-events-none fixed inset-x-0 top-[62px] z-40 flex justify-center px-4 sm:top-[72px]">
      <motion.div
        initial={{ opacity: 0, y: 8, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 4, scale: 0.98 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
        className="pointer-events-auto w-full"
        style={{ maxWidth: "1024px", transformOrigin: "top center" }}
      >
        {/* Hover bridge so the menu doesn't snap shut between trigger and panel */}
        <div aria-hidden className="h-2" />
        {children}
      </motion.div>
    </div>
  );
}


function DropdownWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      transition={{ duration: 0.15 }}
      className="absolute left-1/2 top-full mt-3 w-72 -translate-x-1/2"
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
