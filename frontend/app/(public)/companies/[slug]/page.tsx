import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Building2, Mail, MapPin, Phone, Play } from "lucide-react";

import { CATEGORY_LABELS, CompanyCard } from "@/components/site/company-card";
import { CompanyLogo } from "@/components/site/company-logo";
import { GlassCard } from "@/components/site/glass-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  getCompanies,
  getCompanyBySlug,
  getMediaGallery,
  resolveAssetUrl,
} from "@/lib/public-api";

// Phase A-1: detail page (already has generateStaticParams) — refresh every 5 min.
export const revalidate = 300;

export async function generateStaticParams() {
  const companies = await getCompanies();
  return companies.map((c) => ({ slug: c.slug }));
}

interface CompanyDetailPageProps {
  params: { slug: string };
}

export async function generateMetadata({ params }: CompanyDetailPageProps) {
  const company = await getCompanyBySlug(params.slug);
  return {
    title: company ? company.name : "Company not found",
    description: company?.short_description ?? undefined,
  };
}

export default async function CompanyDetailPage({ params }: CompanyDetailPageProps) {
  const company = await getCompanyBySlug(params.slug);
  if (!company) notFound();

  // Per-company gallery: pull every CMS media asset tagged with this
  // company's slug. Admin tags them under /admin/media. When nothing
  // is tagged the section hides itself instead of showing placeholders.
  const [all, gallery] = await Promise.all([
    getCompanies({ category: company.category }),
    getMediaGallery({ tag: company.slug, limit: 12 }),
  ]);
  const related = all.filter((c) => c.slug !== company.slug).slice(0, 3);

  return (
    <>
      <PageHero
        eyebrow={CATEGORY_LABELS[company.category]}
        title={company.name}
        description={company.short_description ?? undefined}
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
              <CompanyLogo
                logoUrl={company.brand_logo_url}
                initials={company.initials}
                accent={company.accent}
                name={company.name}
                size="lg"
              />
              <div>
                <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
                  About {company.name}
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {CATEGORY_LABELS[company.category]} · Paris United Group
                </p>
              </div>
            </div>

            {company.long_description && (
              <p className="mt-6 text-base text-foreground/90 sm:text-lg">
                {company.long_description}
              </p>
            )}

            {company.services.length > 0 && (
              <>
                <h3 className="mt-8 text-base font-semibold">
                  Products and services
                </h3>
                <ul className="mt-3 flex flex-wrap gap-2">
                  {company.services.map((service) => (
                    <li key={service.id}>
                      <Badge variant="soft" className="font-normal">
                        {service.name}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </>
            )}

            {gallery.length > 0 ? (
              <>
                <h3 className="mt-8 text-base font-semibold">Gallery</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Images and videos uploaded under <em>Admin → Media gallery</em>
                  {" "}and tagged with{" "}
                  <code className="rounded bg-muted px-1">
                    {company.slug}
                  </code>
                  .
                </p>
                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {gallery.map((asset) => {
                    const url = resolveAssetUrl(asset.url) ?? asset.url;
                    const alt =
                      asset.alt_text ??
                      asset.title ??
                      `${company.name} media`;
                    return (
                      <div
                        key={asset.id}
                        className="group relative aspect-[4/3] overflow-hidden rounded-lg border border-border/60 bg-muted"
                      >
                        {asset.kind === "video" ? (
                          <>
                            <video
                              src={url}
                              muted
                              playsInline
                              preload="metadata"
                              className="h-full w-full object-cover"
                            />
                            <span
                              aria-hidden
                              className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/30 text-white opacity-90"
                            >
                              <Play className="h-6 w-6" />
                            </span>
                          </>
                        ) : (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={url}
                            alt={alt}
                            loading="lazy"
                            decoding="async"
                            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                          />
                        )}
                        {asset.title && (
                          <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2 text-xs font-medium text-white">
                            {asset.title}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            ) : null}
          </GlassCard>

          <aside className="space-y-4">
            <GlassCard className="p-6">
              <h3 className="text-base font-semibold">Get in touch</h3>
              <ul className="mt-4 space-y-3 text-sm">
                <ContactRow
                  icon={<MapPin className="h-4 w-4" />}
                  label="Address"
                  value={company.address ?? "Doha, Qatar"}
                />
                {company.phone && (
                  <ContactRow
                    icon={<Phone className="h-4 w-4" />}
                    label="Phone"
                    value={company.phone}
                    href={`tel:${company.phone.replace(/\s/g, "")}`}
                  />
                )}
                {company.email && (
                  <ContactRow
                    icon={<Mail className="h-4 w-4" />}
                    label="Email"
                    value={company.email}
                    href={`mailto:${company.email}`}
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
