import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CatalogueViewer } from "@/app/(public)/offers/catalogues/[slug]/catalogue-viewer";
import { getCatalogueBySlug } from "@/lib/public-offers";


export const revalidate = 60;


interface PageProps {
  params: { slug: string };
}


export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const catalogue = await getCatalogueBySlug(params.slug);
  if (!catalogue) return { title: "Catalogue not found" };
  return {
    title:
      catalogue.meta_title ||
      `${catalogue.title} — Paris United Group Offers`,
    description:
      catalogue.meta_description ||
      catalogue.description ||
      undefined,
    openGraph: {
      title: catalogue.meta_title || catalogue.title,
      description:
        catalogue.meta_description ||
        catalogue.description ||
        undefined,
      images: catalogue.cover_image_url
        ? [{ url: catalogue.cover_image_url }]
        : undefined,
    },
  };
}


export default async function CataloguePage({ params }: PageProps) {
  const catalogue = await getCatalogueBySlug(params.slug);
  if (!catalogue) notFound();
  return <CatalogueViewer catalogue={catalogue} />;
}
