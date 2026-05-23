"use client";

import Link from "next/link";
import { ArrowRight, Building2, ShoppingBag, Truck, Wrench } from "lucide-react";

import { MandalaMark } from "@/components/site/logo";
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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_minmax(0,220px)]">
        {SECTORS.map((sector) => (
          <SectorColumn
            key={sector.key}
            sector={sector}
            companies={companies.filter((c) => c.category === sector.key)}
            onNavigate={onNavigate}
          />
        ))}
        <FeaturedColumn total={companies.length} onNavigate={onNavigate} />
      </div>
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
    <div className="border-b border-border/40 p-5 last:border-b-0 md:border-b-0 md:border-r md:border-border/40">
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

function FeaturedColumn({
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
        "group relative flex flex-col justify-between overflow-hidden p-5 text-white",
        "bg-gradient-to-br from-pug-green-700 via-pug-green-600 to-pug-gold-500"
      )}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-6 -top-6 opacity-30 transition-opacity group-hover:opacity-50"
      >
        <div className="h-32 w-32">
          <MandalaMark size={128} className="h-32 w-32" />
        </div>
      </div>

      <div className="relative">
        <span className="inline-flex items-center rounded-full border border-white/30 bg-white/10 px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.18em] backdrop-blur">
          <Building2 className="mr-1 h-3 w-3" />
          Explore
        </span>
        <h3 className="mt-3 text-balance text-lg font-semibold leading-tight">
          One group, {total} companies, three sectors.
        </h3>
        <p className="mt-2 text-xs text-white/85">
          A diversified portfolio operating across the GCC.
        </p>
      </div>

      <span className="relative mt-6 inline-flex items-center gap-1.5 text-sm font-medium">
        View all companies
        <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}
