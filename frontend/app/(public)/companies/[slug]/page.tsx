import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Building2, Mail, MapPin, Phone } from "lucide-react";

import { CompanyCard } from "@/components/site/company-card";
import { GlassCard } from "@/components/site/glass-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  CATEGORY_LABELS,
  getCompanies,
  getCompaniesByCategory,
  getCompanyBySlug,
} from "@/lib/dummy-data/companies";
import { cn } from "@/lib/utils";

export function generateStaticParams() {
  return getCompanies().map((c) => ({ slug: c.slug }));
}

interface CompanyDetailPageProps {
  params: { slug: string };
}

export function generateMetadata({ params }: CompanyDetailPageProps) {
  const company = getCompanyBySlug(params.slug);
  return { title: company ? company.name : "Company not found" };
}

export default function CompanyDetailPage({ params }: CompanyDetailPageProps) {
  const company = getCompanyBySlug(params.slug);
  if (!company) notFound();

  const related = getCompaniesByCategory(company.category)
    .filter((c) => c.slug !== company.slug)
    .slice(0, 3);

  return (
    <>
      <PageHero
        eyebrow={CATEGORY_LABELS[company.category]}
        title={company.name}
        description={company.shortDescription}
        accent={company.accent}
      >
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="muted" className="capitalize">
            {CATEGORY_LABELS[company.category]}
          </Badge>
          {company.branches && (
            <Badge variant="soft" className="inline-flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              {company.branches}
            </Badge>
          )}
        </div>
      </PageHero>

      <Section className="pt-12">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[2fr_1fr]">
          <GlassCard className="p-6 sm:p-8">
            <div className="flex items-start gap-4">
              <span
                className={cn(
                  "inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br text-lg font-bold tracking-wide text-white shadow-md",
                  company.accent
                )}
                aria-hidden
              >
                {company.initials}
              </span>
              <div>
                <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
                  About {company.name}
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {CATEGORY_LABELS[company.category]} · Paris United Group
                </p>
              </div>
            </div>

            <p className="mt-6 text-base text-foreground/90 sm:text-lg">
              {company.longDescription}
            </p>

            <h3 className="mt-8 text-base font-semibold">Products and services</h3>
            <ul className="mt-3 flex flex-wrap gap-2">
              {company.services.map((service) => (
                <li key={service}>
                  <Badge variant="soft" className="font-normal">
                    {service}
                  </Badge>
                </li>
              ))}
            </ul>

            <h3 className="mt-8 text-base font-semibold">Gallery</h3>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <span
                  key={i}
                  aria-hidden
                  className={cn(
                    "block aspect-[4/3] rounded-lg bg-gradient-to-br opacity-70",
                    company.accent
                  )}
                />
              ))}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Gallery placeholders — Phase 5 lets admin upload real images.
            </p>
          </GlassCard>

          <aside className="space-y-4">
            <GlassCard className="p-6">
              <h3 className="text-base font-semibold">Get in touch</h3>
              <ul className="mt-4 space-y-3 text-sm">
                <ContactRow
                  icon={<MapPin className="h-4 w-4" />}
                  label="Address"
                  value={company.contact?.address ?? "Doha, Qatar"}
                />
                {company.contact?.phone && (
                  <ContactRow
                    icon={<Phone className="h-4 w-4" />}
                    label="Phone"
                    value={company.contact.phone}
                    href={`tel:${company.contact.phone.replace(/\s/g, "")}`}
                  />
                )}
                {company.contact?.email && (
                  <ContactRow
                    icon={<Mail className="h-4 w-4" />}
                    label="Email"
                    value={company.contact.email}
                    href={`mailto:${company.contact.email}`}
                  />
                )}
              </ul>
              <Button asChild className="mt-5 w-full">
                <Link href="/contact">Contact our team</Link>
              </Button>
            </GlassCard>

            <GlassCard className="p-6">
              <h3 className="text-base font-semibold">Back to overview</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                See every business in the Paris United Group portfolio.
              </p>
              <Button asChild variant="outline" className="mt-5 w-full">
                <Link href="/companies">
                  <ArrowLeft className="h-4 w-4" />
                  All companies
                </Link>
              </Button>
            </GlassCard>
          </aside>
        </div>
      </Section>

      {related.length > 0 && (
        <Section
          eyebrow="Related companies"
          title={`Other ${CATEGORY_LABELS[company.category]} businesses`}
        >
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {related.map((c) => (
              <CompanyCard key={c.slug} company={c} />
            ))}
          </div>
        </Section>
      )}
    </>
  );
}

function ContactRow({
  icon,
  label,
  value,
  href,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  href?: string;
}) {
  const inner = (
    <div className="flex items-start gap-3">
      <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="break-words font-medium">{value}</p>
      </div>
    </div>
  );
  return (
    <li>
      {href ? (
        <Link href={href} className="hover:text-foreground">
          {inner}
        </Link>
      ) : (
        inner
      )}
    </li>
  );
}
