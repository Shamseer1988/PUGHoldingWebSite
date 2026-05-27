import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, BookOpen, MapPin } from "lucide-react";

import type { Catalogue } from "@/lib/admin/marketing-types";
import { getCampaignBySlug } from "@/lib/public-offers";


export const revalidate = 60;


interface PageProps {
  params: { slug: string };
}


export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const campaign = await getCampaignBySlug(params.slug);
  if (!campaign) return { title: "Campaign not found" };
  return {
    title:
      campaign.meta_title ||
      `${campaign.title} — Paris United Group Offers`,
    description:
      campaign.meta_description ||
      campaign.description ||
      undefined,
    openGraph: {
      title: campaign.meta_title || campaign.title,
      description:
        campaign.meta_description ||
        campaign.description ||
        undefined,
      images: campaign.banner_image_url
        ? [{ url: campaign.banner_image_url }]
        : undefined,
    },
  };
}


export default async function CampaignDetailPage({ params }: PageProps) {
  const campaign = await getCampaignBySlug(params.slug);
  if (!campaign) {
    notFound();
  }

  const themed = campaign.theme_color || "#17382f";

  return (
    <main className="min-h-screen bg-background">
      {/* Banner */}
      <section
        className="relative overflow-hidden border-b border-border/60"
        style={{
          background: `linear-gradient(135deg, ${themed}f2, ${themed}cc)`,
        }}
      >
        {campaign.banner_image_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={campaign.banner_image_url}
            alt=""
            className="absolute inset-0 h-full w-full object-cover opacity-30 mix-blend-screen"
            aria-hidden
          />
        )}
        <div className="relative mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-16">
          <Link
            href="/offers"
            className="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.18em] text-white/70 hover:text-white"
          >
            <ArrowLeft className="h-3 w-3" />
            All offers
          </Link>
          <h1 className="mt-4 text-3xl font-semibold text-white sm:text-4xl">
            {campaign.title}
          </h1>
          {campaign.description && (
            <p className="mt-3 max-w-2xl text-base text-white/85">
              {campaign.description}
            </p>
          )}
          <div className="mt-5 flex flex-wrap items-center gap-2 text-xs text-white/85">
            {campaign.branch && (
              <span className="inline-flex items-center gap-1 rounded-full border border-white/20 bg-white/10 px-3 py-1">
                <MapPin className="h-3 w-3" />
                {campaign.branch}
              </span>
            )}
            {(campaign.start_date || campaign.end_date) && (
              <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1">
                {campaign.start_date || "Now"}
                {" → "}
                {campaign.end_date || "Ongoing"}
              </span>
            )}
            <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1">
              {campaign.catalogues.length} catalogue
              {campaign.catalogues.length === 1 ? "" : "s"}
            </span>
          </div>
        </div>
      </section>

      {/* Catalogue grid */}
      <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
        {campaign.catalogues.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 p-12 text-center text-sm text-muted-foreground">
            <BookOpen className="mx-auto mb-3 h-8 w-8 opacity-40" />
            No catalogues attached to this campaign yet.
          </div>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {campaign.catalogues.map((c) => (
              <CatalogueCard key={c.id} catalogue={c} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}


function CatalogueCard({ catalogue }: { catalogue: Catalogue }) {
  return (
    <Link
      href={`/offers/catalogues/${catalogue.slug}`}
      className="group block overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm transition-all hover:shadow-lg"
    >
      <div className="relative aspect-[3/4] overflow-hidden bg-muted">
        {catalogue.cover_image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={catalogue.cover_image_url}
            alt={catalogue.title}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <BookOpen className="h-10 w-10 opacity-40" />
          </div>
        )}
      </div>
      <div className="space-y-1 p-4">
        <h3 className="line-clamp-2 font-semibold leading-snug">
          {catalogue.title}
        </h3>
        {catalogue.description && (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {catalogue.description}
          </p>
        )}
        <p className="pt-1 text-[11px] text-muted-foreground">
          {catalogue.page_count} page
          {catalogue.page_count === 1 ? "" : "s"} ·
          <span className="ml-1 font-medium text-primary">Open viewer →</span>
        </p>
      </div>
    </Link>
  );
}
