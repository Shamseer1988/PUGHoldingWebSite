"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { type NavItem } from "@/lib/site-config";
import { cn } from "@/lib/utils";

interface MobileMenuProps {
  open: boolean;
  onClose: () => void;
  items: NavItem[];
}

export function MobileMenu({ open, onClose, items }: MobileMenuProps) {
  const pathname = usePathname();

  // Lock body scroll while the drawer is open and close on Escape.
  React.useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  // Close the drawer whenever the route changes (link click).
  React.useEffect(() => {
    if (open) onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm lg:hidden"
            aria-hidden
          />
          <motion.aside
            key="drawer"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "tween", ease: [0.4, 0, 0.2, 1], duration: 0.3 }}
            role="dialog"
            aria-modal="true"
            aria-label="Mobile menu"
            className="fixed inset-y-0 right-0 z-50 flex w-[88vw] max-w-sm flex-col border-l border-border/60 bg-background shadow-2xl lg:hidden"
          >
            <header className="flex items-center justify-between border-b border-border/60 px-5 py-4">
              <span className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Menu
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </Button>
            </header>

            <nav
              aria-label="Mobile primary"
              className="flex-1 overflow-y-auto px-3 py-4"
            >
              <ul className="flex flex-col gap-1">
                {items.map((item) => (
                  <MobileMenuItem
                    key={item.href}
                    item={item}
                    onClose={onClose}
                    isActive={isActive(pathname, item)}
                  />
                ))}
              </ul>
            </nav>

            <footer className="border-t border-border/60 px-5 py-4">
              <p className="text-xs text-muted-foreground">
                © {new Date().getFullYear()} Paris United Group Holding
              </p>
            </footer>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function MobileMenuItem({
  item,
  onClose,
  isActive,
}: {
  item: NavItem;
  onClose: () => void;
  isActive: boolean;
}) {
  const [expanded, setExpanded] = React.useState(isActive);
  const hasChildren = (item.children?.length ?? 0) > 0;

  if (!hasChildren) {
    return (
      <li>
        <Link
          href={item.href}
          onClick={onClose}
          className={cn(
            "block rounded-lg px-3 py-2.5 text-base font-medium transition-colors",
            isActive
              ? "bg-primary/10 text-primary"
              : "text-foreground hover:bg-muted"
          )}
        >
          {item.label}
        </Link>
      </li>
    );
  }

  return (
    <li>
      <button
        type="button"
        onClick={() => setExpanded((s) => !s)}
        className={cn(
          "flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-base font-medium transition-colors",
          isActive
            ? "bg-primary/10 text-primary"
            : "text-foreground hover:bg-muted"
        )}
        aria-expanded={expanded}
      >
        {item.label}
        <ChevronDown
          className={cn(
            "h-4 w-4 transition-transform",
            expanded && "rotate-180"
          )}
        />
      </button>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.ul
            key="children"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden pl-3"
          >
            {item.children!.map((child) => (
              <li key={child.href}>
                <Link
                  href={child.href}
                  onClick={onClose}
                  className="block rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  {child.label}
                </Link>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </li>
  );
}

function isActive(pathname: string | null, item: NavItem): boolean {
  if (!pathname) return false;
  if (pathname === item.href) return true;
  if (item.children?.some((c) => pathname.startsWith(c.href.split("?")[0]))) {
    return true;
  }
  return false;
}
