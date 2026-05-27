import type { Metadata } from "next";

import { OffersLanding } from "@/app/(public)/offers/offers-landing";
import { getOffersIndex } from "@/lib/public-offers";


// CMS-style content — let the page revalidate every 60s rather than
// per-request, so the public CDN can hold a copy.
export const revalidate = 60;

export const metadata: Metadata = {
  title: "Offers & Catalogues — Paris United Group",
  description:
    "Browse the latest hypermarket flyers, killer offers and flash sales from Paris United Group's retail brands across Qatar.",
  openGraph: {
    title: "Offers & Catalogues — Paris United Group",
    description:
      "The latest hypermarket flyers, killer offers and flash sales — refreshed weekly.",
  },
};


interface PageProps {
  searchParams?: { branch?: string; q?: string };
}


export default async function OffersPage({ searchParams }: PageProps) {
  const branch = searchParams?.branch;
  const q = searchParams?.q;
  const index = await getOffersIndex({ branch, q });

  return <OffersLanding index={index} initialBranch={branch} initialQuery={q} />;
}
