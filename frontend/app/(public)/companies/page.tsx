import Link from "next/link";

import { CompanyCard } from "@/components/site/company-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import {
  CATEGORY_LABELS,
  type CompanyCategory,
  getCompanies,
} from "@/lib/dummy-data/companies";
import { cn } from "@/lib/utils";

export const metadata = { title: "Group Companies" };

const CATEGORY_OPTIONS: Array<"all" | CompanyCategory> = [
  "all",
  "distribution",
  "retail",
  "services",
];

interface CompaniesPageProps {
  searchParams?: { category?: string };
}

export default function CompaniesPage({ searchParams }: CompaniesPageProps) {
  const requested = (searchParams?.category ?? "all").toLowerCase();
  const active: "all" | CompanyCategory = (
    CATEGORY_OPTIONS as string[]
  ).includes(requested)
    ? (requested as "all" | CompanyCategory)
    : "all";

  const companies =
    active === "all"
      ? getCompanies()
      : getCompanies().filter((c) => c.category === active);

  return (
    <>
      <PageHero
        eyebrow="Our companies"
        title="Explore the Paris United Group"
        description="A diversified portfolio of distribution, retail, and services businesses operating in Qatar and the wider GCC."
        accent="from-fuchsia-600 via-violet-500 to-indigo-500"
      />

      <Section className="pt-10">
        <div className="mb-8 flex flex-wrap items-center gap-2">
          {CATEGORY_OPTIONS.map((cat) => (
            <Link
              key={cat}
              href={cat === "all" ? "/companies" : `/companies?category=${cat}`}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
                cat === active
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border/60 bg-background/60 text-muted-foreground hover:text-foreground"
              )}
              aria-current={cat === active ? "page" : undefined}
            >
              {cat === "all"
                ? `All companies (${getCompanies().length})`
                : `${CATEGORY_LABELS[cat]} (${
                    getCompanies().filter((c) => c.category === cat).length
                  })`}
            </Link>
          ))}
        </div>

        {companies.length === 0 ? (
          <p className="text-muted-foreground">
            No companies match this filter.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {companies.map((company) => (
              <CompanyCard key={company.slug} company={company} />
            ))}
          </div>
        )}
      </Section>
    </>
  );
}
