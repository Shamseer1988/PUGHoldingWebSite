import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { Section } from "@/components/site/section";
import { PageHero } from "@/components/site/page-hero";
import { GlassCard } from "@/components/site/glass-card";
import { getPageBySlug, getPages } from "@/lib/public-api";

// Phase A-1: CMS page (already has generateStaticParams) — refresh every 5 min.
export const revalidate = 300;

interface PageProps {
  params: { slug: string };
}

export async function generateStaticParams() {
  const pages = await getPages();
  return pages.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const page = await getPageBySlug(params.slug);
  if (!page) {
    return { title: "Page not found" };
  }
  return {
    title: page.seo_title ?? page.title,
    description: page.seo_description ?? page.summary ?? undefined,
    keywords: page.seo_keywords ?? undefined,
  };
}

export default async function CMSPagePage({ params }: PageProps) {
  const page = await getPageBySlug(params.slug);
  if (!page) notFound();

  return (
    <>
      <PageHero
        eyebrow={page.eyebrow ?? undefined}
        title={page.title}
        description={page.summary ?? undefined}
        accent="from-pug-green-700 via-pug-green-500 to-pug-gold-500"
        imageUrl={page.banner_image_url}
        mobileImageUrl={page.banner_mobile_url}
      />

      {page.body && (
        <Section className="pt-10">
          <GlassCard className="p-6 sm:p-10">
            <article className="prose prose-slate dark:prose-invert max-w-none whitespace-pre-wrap">
              {page.body}
            </article>
          </GlassCard>
        </Section>
      )}
    </>
  );
}
