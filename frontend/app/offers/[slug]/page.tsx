import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, BookOpen, Clock, MapPin } from "lucide-react";

import type { Catalogue } from "@/lib/admin/marketing-types";
import { resolveAssetUrl } from "@/lib/public-api";
import { getCampaignBySlug } from "@/lib/public-offers";
import { cn } from "@/lib/utils";


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
  const expired = campaign.is_expired;

  return (
    <main className="min-h-screen bg-background">
      {/* Banner */}
      <section
        className="relative overflow-hidden border-b border-border/60"
        style={{
          background: expired
            ? "linear-gradient(135deg, #3f3f46f2, #18181bcc)"
            : `linear-gradient(135deg, ${themed}f2, ${themed}cc)`,
        }}
      >
        {campaign.banner_image_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={resolveAssetUrl(campaign.banner_image_url) ?? ""}
            alt=""
            className={cn(
              "absolute inset-0 h-full w-full object-cover mix-blend-screen",
              expired ? "opacity-15 grayscale" : "opacity-30"
            )}
            aria-hidden
          />
        )}
        {/* Match the compact ``<PageHero size="compact">`` on
            ``/offers`` (``py-8 sm:py-10 lg:py-12``) so the section
            chrome reads consistently across the two Offers pages
            without affecting any other public page's hero. */}
        <div className="relative mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-10 lg:py-12">
          <Link
            href="/offers"
            className="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.18em] text-white/70 hover:text-white"
          >
            <ArrowLeft className="h-3 w-3" />
            All offers
          </Link>
          {expired && (
            <span className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-white/30 bg-white/15 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white backdrop-blur">
              <Clock className="h-3 w-3" />
              Campaign ended
            </span>
          )}
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

      {/* Expired notice strip — sits between the banner and the
          catalogue grid so it's the first thing the customer reads
          before clicking into a viewer. Keeps the call-out distinct
          from the banner's chrome so it doesn't get overlooked. */}
      {expired && (
        <div className="border-b border-amber-500/30 bg-amber-500/10">
          <div className="mx-auto flex max-w-5xl items-start gap-3 px-4 py-4 text-sm text-amber-900 dark:text-amber-200 sm:px-6">
            <Clock className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">
                This campaign has ended
                {campaign.end_date && (
                  <>
                    {" "}
                    (
                    {new Date(campaign.end_date).toLocaleDateString(undefined, {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                    )
                  </>
                )}
                .
              </p>
              <p className="mt-0.5 text-amber-800/85 dark:text-amber-200/80">
                The catalogues below are kept for reference. Prices and
                availability may have changed. Visit{" "}
                <Link href="/offers" className="font-semibold underline hover:no-underline">
                  current offers
                </Link>{" "}
                for live promotions.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Catalogue grid */}
      <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
        {campaign.catalogues.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 p-12 text-center text-sm text-muted-foreground">
            <BookOpen className="mx-auto mb-3 h-8 w-8 opacity-40" />
            No catalogues attached to this campaign yet.
          </div>
        ) : (
          <div
            className={cn(
              "grid gap-5 sm:grid-cols-2 lg:grid-cols-3",
              expired && "opacity-90"
            )}
          >
            {campaign.catalogues.map((c) => (
              <CatalogueCard key={c.id} catalogue={c} expired={expired} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}


function CatalogueCard({
  catalogue,
  expired = false,
}: {
  catalogue: Catalogue;
  expired?: boolean;
}) {
  return (
    <Link
      href={`/offers/catalogues/${catalogue.slug}`}
      aria-label={
        expired
          ? `${catalogue.title} (from an expired campaign)`
          : catalogue.title
      }
      className="group block overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm transition-all hover:shadow-lg"
    >
      <div className="relative aspect-[3/4] overflow-hidden bg-muted">
        {catalogue.cover_image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={resolveAssetUrl(catalogue.cover_image_url) ?? ""}
            alt={catalogue.title}
            loading="lazy"
            className={cn(
              "h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]",
              expired && "grayscale-[40%]"
            )}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <BookOpen className="h-10 w-10 opacity-40" />
          </div>
        )}
        {expired && (
          <span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-foreground/85 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-background">
            <Clock className="h-2.5 w-2.5" />
            Expired
          </span>
        )}
      </div>
      <div className="space-y-1 p-4">
        <h3
          className={cn(
            "line-clamp-2 font-semibold leading-snug",
            expired && "text-muted-foreground"
          )}
        >
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
          <span className="ml-1 font-medium text-primary">
            {expired ? "View archive →" : "Open viewer →"}
          </span>
        </p>
      </div>
    </Link>
  );
}
