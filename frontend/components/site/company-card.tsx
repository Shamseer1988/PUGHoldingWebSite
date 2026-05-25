import Link from "next/link";
import { ArrowUpRight, Building2 } from "lucide-react";

import { CompanyLogo } from "@/components/site/company-logo";
import { GlassCard } from "@/components/site/glass-card";
import { Badge } from "@/components/ui/badge";
import type { Company } from "@/lib/admin/types";

const CATEGORY_LABELS: Record<Company["category"], string> = {
  distribution: "Distribution",
  retail: "Retail",
  services: "Services",
};

interface CompanyCardProps {
  company: Company;
  /** When true the description / services are hidden (used in compact logo grid). */
  compact?: boolean;
}

export function CompanyCard({ company, compact = false }: CompanyCardProps) {
  return (
    <Link href={`/companies/${company.slug}`} className="group block h-full">
      <GlassCard className="flex h-full flex-col p-5 transition-transform group-hover:-translate-y-1">
        <div className="flex items-start justify-between gap-3">
          <CompanyLogo
            logoUrl={company.brand_logo_url}
            initials={company.initials}
            accent={company.accent}
            name={company.name}
            size="md"
          />
          <Badge variant="muted" className="capitalize">
            {CATEGORY_LABELS[company.category]}
          </Badge>
        </div>

        <h3 className="mt-4 text-lg font-semibold leading-snug tracking-tight">
          {company.name}
        </h3>

        {!compact && company.short_description && (
          <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">
            {company.short_description}
          </p>
        )}

        {!compact && company.services.length > 0 && (
          <ul className="mt-4 flex flex-wrap gap-1.5">
            {company.services.slice(0, 3).map((service) => (
              <li key={service.id}>
                <Badge variant="soft" className="font-normal">
                  {service.name}
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

export { CATEGORY_LABELS };
