"use client";

import Link from "next/link";
import {
  ArrowRight,
  ShoppingBag,
  Sparkles,
  Truck,
  Wrench,
} from "lucide-react";

import type { Company } from "@/lib/admin/types";
import { cn } from "@/lib/utils";

interface CompaniesMegaMenuProps {
  companies: Company[];
  /** Called when a child link is clicked — used by mobile to close the drawer. */
  onNavigate?: () => void;
}

interface SectorMeta {
  key: Company["category"];
  label: string;
  description: string;
  icon: typeof Truck;
  accent: string;
}

const SECTORS: SectorMeta[] = [
  {
    key: "distribution",
    label: "Distribution",
    description: "FMCG, fashion, packaging, fresh produce, building materials.",
    icon: Truck,
    accent: "from-pug-green-500 to-pug-green-700",
  },
  {
    key: "retail",
    label: "Retail",
    description: "Hypermarkets, minimarts, grocery shops, fresh fish.",
    icon: ShoppingBag,
    accent: "from-pug-gold-500 to-pug-gold-700",
  },
  {
    key: "services",
    label: "Services",
    description: "Garages, real estate, engineering & construction.",
    icon: Wrench,
    accent: "from-pug-green-600 to-pug-gold-500",
  },
];

export function CompaniesMegaMenu({
  companies,
  onNavigate,
}: CompaniesMegaMenuProps) {
  return (
    <div
      role="menu"
      className={cn(
        "overflow-hidden rounded-2xl border border-pug-gold-500/25 shadow-2xl backdrop-blur-xl",
        "bg-background/95 dark:bg-card/90"
      )}
    >
      <div className="grid grid-cols-1 sm:grid-cols-3">
        {SECTORS.map((sector) => (
          <SectorColumn
            key={sector.key}
            sector={sector}
            companies={companies.filter((c) => c.category === sector.key)}
            onNavigate={onNavigate}
          />
        ))}
      </div>

      <FooterCta total={companies.length} onNavigate={onNavigate} />
    </div>
  );
}

function SectorColumn({
  sector,
  companies,
  onNavigate,
}: {
  sector: SectorMeta;
  companies: Company[];
  onNavigate?: () => void;
}) {
  const Icon = sector.icon;
  return (
    <div className="border-b border-border/40 p-5 last:border-b-0 sm:border-b-0 sm:border-r sm:border-border/40 sm:last:border-r-0">
      <Link
        href={`/companies?category=${sector.key}`}
        onClick={onNavigate}
        className="group/header flex items-start gap-3"
      >
        <span
          className={cn(
            "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm",
            sector.accent
          )}
          aria-hidden
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-sm font-semibold tracking-tight text-foreground group-hover/header:text-primary">
            {sector.label}
            <ArrowRight className="h-3 w-3 opacity-0 transition-all group-hover/header:translate-x-0.5 group-hover/header:opacity-100" />
          </p>
          <p className="text-[11px] text-muted-foreground">
            {companies.length} {companies.length === 1 ? "company" : "companies"}
          </p>
        </div>
      </Link>

      <p className="mt-2 text-xs text-muted-foreground">{sector.description}</p>

      <ul className="mt-4 space-y-0.5" role="none">
        {companies.length === 0 ? (
          <li className="px-2 py-1.5 text-xs text-muted-foreground">
            No companies in this sector yet.
          </li>
        ) : (
          companies.map((c) => (
            <li key={c.slug} role="none">
              <Link
                href={`/companies/${c.slug}`}
                role="menuitem"
                onClick={onNavigate}
                className="group/row flex items-start gap-2.5 rounded-md px-2 py-1.5 transition-colors hover:bg-muted/60"
              >
                <span
                  className={cn(
                    "mt-0.5 inline-block h-6 w-6 shrink-0 rounded-md bg-gradient-to-br text-[10px] font-bold leading-6 text-white shadow-sm",
                    "text-center",
                    c.accent
                  )}
                  aria-hidden
                >
                  {c.initials}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-foreground group-hover/row:text-primary">
                    {c.name}
                  </span>
                  {c.short_description && (
                    <span className="block truncate text-[11px] text-muted-foreground">
                      {c.short_description}
                    </span>
                  )}
                </span>
              </Link>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

function FooterCta({
  total,
  onNavigate,
}: {
  total: number;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href="/companies"
      onClick={onNavigate}
      className={cn(
        "group relative flex flex-col items-center justify-between gap-3 overflow-hidden px-5 py-4 text-white",
        "bg-gradient-to-r from-pug-green-700 via-pug-green-600 to-pug-gold-500",
        "sm:flex-row sm:gap-6"
      )}
    >
      <div className="relative flex items-center gap-3">
        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white/15 backdrop-blur">
          <Sparkles className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold leading-tight">
            One group, {total} companies, three sectors.
          </p>
          <p className="text-[11px] text-white/85">
            A diversified portfolio operating across the GCC.
          </p>
        </div>
      </div>

      <span className="relative inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1.5 text-sm font-medium backdrop-blur transition-colors group-hover:bg-white/25">
        View all companies
        <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}
