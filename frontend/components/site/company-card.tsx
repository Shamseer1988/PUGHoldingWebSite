import Link from "next/link";
import { ArrowUpRight, Building2 } from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { Badge } from "@/components/ui/badge";
import {
  CATEGORY_LABELS,
  type Company,
} from "@/lib/dummy-data/companies";
import { cn } from "@/lib/utils";

interface CompanyCardProps {
  company: Company;
  /** When true the description / services are hidden (used in compact logo grid). */
  compact?: boolean;
}

export function CompanyCard({ company, compact = false }: CompanyCardProps) {
  return (
    <Link
      href={`/companies/${company.slug}`}
      className="group block h-full"
    >
      <GlassCard className="flex h-full flex-col p-5 transition-transform group-hover:-translate-y-1">
        <div className="flex items-start justify-between gap-3">
          <LogoTile accent={company.accent} initials={company.initials} />
          <Badge variant="muted" className="capitalize">
            {CATEGORY_LABELS[company.category]}
          </Badge>
        </div>

        <h3 className="mt-4 text-lg font-semibold leading-snug tracking-tight">
          {company.name}
        </h3>

        {!compact && (
          <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">
            {company.shortDescription}
          </p>
        )}

        {!compact && company.services.length > 0 && (
          <ul className="mt-4 flex flex-wrap gap-1.5">
            {company.services.slice(0, 3).map((service) => (
              <li key={service}>
                <Badge variant="soft" className="font-normal">
                  {service}
                </Badge>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-auto flex items-center justify-between pt-5">
          {company.branches ? (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Building2 className="h-3.5 w-3.5" />
              {company.branches}
            </span>
          ) : (
            <span />
          )}
          <span className="inline-flex items-center gap-1 text-sm font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
            View details
            <ArrowUpRight className="h-3.5 w-3.5" />
          </span>
        </div>
      </GlassCard>
    </Link>
  );
}

function LogoTile({ accent, initials }: { accent: string; initials: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br text-base font-bold tracking-wide text-white shadow-md",
        accent
      )}
      aria-hidden
    >
      {initials}
    </span>
  );
}
