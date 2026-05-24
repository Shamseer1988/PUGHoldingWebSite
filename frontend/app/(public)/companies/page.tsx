import Link from "next/link";

import { CATEGORY_LABELS, CompanyCard } from "@/components/site/company-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { getCompanies } from "@/lib/public-api";
import type { Company } from "@/lib/admin/types";
import { cn } from "@/lib/utils";

export const metadata = { title: "Group Companies" };
export const revalidate = 60;

const CATEGORY_OPTIONS: Array<"all" | Company["category"]> = [
  "all",
  "distribution",
  "retail",
  "services",
];

interface CompaniesPageProps {
  searchParams?: { category?: string };
}

export default async function CompaniesPage({ searchParams }: CompaniesPageProps) {
  const requested = (searchParams?.category ?? "all").toLowerCase();
  const active: "all" | Company["category"] = (
    CATEGORY_OPTIONS as string[]
  ).includes(requested)
    ? (requested as "all" | Company["category"])
    : "all";

  const all = await getCompanies();
  const companies = active === "all" ? all : all.filter((c) => c.category === active);

  return (
    <>
      <PageHero
        eyebrow="Our companies"
        title="Explore the Paris United Group"
        description="A diversified portfolio of distribution, retail, and services businesses operating in Qatar and the wider GCC."
        accent="from-pug-gold-500 via-pug-gold-600 to-pug-green-600"
      />

      <Section className="pt-10">
        <div className="mb-8 flex flex-wrap items-center gap-2">
          {CATEGORY_OPTIONS.map((cat) => {
            const count =
              cat === "all" ? all.length : all.filter((c) => c.category === cat).length;
            const label = cat === "all" ? "All companies" : CATEGORY_LABELS[cat];
            return (
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
                {label} ({count})
              </Link>
            );
          })}
        </div>

        {companies.length === 0 ? (
          <p className="text-muted-foreground">
            No companies match this filter yet.
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
