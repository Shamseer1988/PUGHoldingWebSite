"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ChevronDown, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Company } from "@/lib/admin/types";
import { PRIMARY_CTA, type NavItem } from "@/lib/site-config";
import { cn } from "@/lib/utils";

interface MobileMenuProps {
  open: boolean;
  onClose: () => void;
  items: NavItem[];
  companies: Company[];
}

export function MobileMenu({ open, onClose, items, companies }: MobileMenuProps) {
  const pathname = usePathname();

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
                    companies={companies}
                  />
                ))}
              </ul>
            </nav>

            <footer className="space-y-3 border-t border-border/60 px-5 py-4">
              <Button
                asChild
                size="sm"
                className="h-11 w-full rounded-full bg-gradient-to-r from-pug-gold-600 to-pug-gold-500 text-sm font-semibold text-pug-green-950 shadow-[0_6px_22px_-12px_rgba(166,124,58,0.55)] motion-safe:transition-all motion-safe:duration-200 motion-safe:hover:-translate-y-0.5 hover:from-pug-gold-500 hover:to-pug-gold-400 hover:text-pug-green-950 hover:shadow-[0_10px_28px_-12px_rgba(166,124,58,0.6)] focus-visible:ring-pug-gold-500 dark:text-pug-green-950"
              >
                <Link href={PRIMARY_CTA.href} onClick={onClose}>
                  {PRIMARY_CTA.label}
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </Link>
              </Button>
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
  companies,
}: {
  item: NavItem;
  onClose: () => void;
  isActive: boolean;
  companies: Company[];
}) {
  const isCompaniesMega = item.mega === "companies";
  const hasChildren = (item.children?.length ?? 0) > 0 || isCompaniesMega;
  const [expanded, setExpanded] = React.useState(isActive);

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
          <motion.div
            key="children"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            {isCompaniesMega ? (
              <MobileCompaniesGroup companies={companies} onClose={onClose} />
            ) : (
              <ul className="pl-3">
                {item.children!.map((child) => (
                  <li key={child.href}>
                    <Link
                      href={child.href}
                      onClick={onClose}
                      className="block rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      <span className="block font-medium text-foreground">
                        {child.label}
                      </span>
                      {child.description && (
                        <span className="block text-xs">
                          {child.description}
                        </span>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

function MobileCompaniesGroup({
  companies,
  onClose,
}: {
  companies: Company[];
  onClose: () => void;
}) {
  const groups: Array<{ key: Company["category"]; label: string }> = [
    { key: "distribution", label: "Distribution" },
    { key: "retail", label: "Retail" },
    { key: "services", label: "Services" },
  ];

  return (
    <div className="pl-3">
      {groups.map((g) => {
        const list = companies.filter((c) => c.category === g.key);
        if (list.length === 0) return null;
        return (
          <section key={g.key} className="mb-3 last:mb-0">
            <p className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {g.label}
            </p>
            <ul>
              {list.map((c) => (
                <li key={c.slug}>
                  <Link
                    href={`/companies/${c.slug}`}
                    onClick={onClose}
                    className="flex items-center gap-2.5 rounded-md px-3 py-1.5 text-sm text-foreground hover:bg-muted"
                  >
                    <span
                      className={cn(
                        "inline-block h-5 w-5 shrink-0 rounded-md bg-gradient-to-br text-[9px] font-bold leading-5 text-white shadow-sm",
                        "text-center",
                        c.accent
                      )}
                      aria-hidden
                    >
                      {c.initials}
                    </span>
                    <span className="truncate">{c.name}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      <Link
        href="/companies"
        onClick={onClose}
        className="mx-3 mt-2 inline-flex items-center gap-1 rounded-md bg-pug-gold-500/15 px-3 py-1.5 text-xs font-medium text-pug-gold-700 dark:text-pug-gold-300"
      >
        View all companies
        <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
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
