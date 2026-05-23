export type NewsCategory = "company" | "event" | "press" | "csr";

export interface NewsItem {
  slug: string;
  title: string;
  summary: string;
  body: string;
  category: NewsCategory;
  publishedAt: string; // ISO date
  author: string;
  /** Tailwind gradient classes for the placeholder cover image. */
  cover: string;
  featured?: boolean;
  gallery?: string[]; // gradient classes used as placeholder gallery tiles
}

export const NEWS: NewsItem[] = [
  {
    slug: "paris-united-group-opens-fifth-hypermarket",
    title: "Paris United Group opens its fifth hypermarket",
    summary:
      "A new Paris Hyper Market opens its doors in Lusail, expanding the group's retail footprint across Qatar and the wider GCC.",
    body:
      "Paris United Group Holding today announced the opening of its fifth hypermarket in Lusail. The store features more than 50,000 SKUs across grocery, fresh food, household, and electronics, with a dedicated kids zone and a self-checkout area. Chairman Mr. A. Al Hassan said the new branch underlines the group's commitment to bringing high-quality retail closer to families. The opening was attended by community leaders, business partners, and over 1,200 visitors on day one.",
    category: "company",
    publishedAt: "2026-05-12",
    author: "Group Communications",
    cover: "from-rose-500 via-red-500 to-orange-400",
    featured: true,
    gallery: [
      "from-rose-400 to-orange-400",
      "from-rose-500 to-pink-500",
      "from-orange-500 to-amber-500",
    ],
  },
  {
    slug: "yellowtech-garage-launches-ev-service",
    title: "YellowTech Garage launches EV maintenance",
    summary:
      "Certified technicians, dedicated bays, and OEM-approved tools are now ready for Qatar's growing EV fleet.",
    body:
      "YellowTech Garage has invested in dedicated EV service bays, high-voltage safety equipment, and OEM-approved diagnostic tools. Customers can now schedule full EV servicing alongside the existing light vehicle service catalogue.",
    category: "company",
    publishedAt: "2026-04-28",
    author: "Group Communications",
    cover: "from-amber-500 via-yellow-500 to-orange-400",
  },
  {
    slug: "csr-back-to-school-2026",
    title: "Back to School 2026 CSR drive distributes 5,000 kits",
    summary:
      "Doha Fashion and Al Mihrab Groceries partnered with local schools to support students across Qatar.",
    body:
      "Through a coordinated CSR initiative, Doha Fashion and Al Mihrab Groceries distributed 5,000 stationery kits to public schools. Each kit includes notebooks, writing tools, and essential supplies for the new academic year.",
    category: "csr",
    publishedAt: "2026-04-15",
    author: "Group CSR",
    cover: "from-fuchsia-500 via-pink-500 to-rose-400",
  },
  {
    slug: "maharib-fresh-cold-chain-upgrade",
    title: "Maharib Fresh completes cold-chain upgrade",
    summary:
      "New refrigerated trucks and warehouse facilities extend produce shelf life by up to 25%.",
    body:
      "Maharib Fresh Trading has finished a multi-month upgrade to its cold-chain network, introducing new refrigerated trucks and an expanded chilled warehouse. The investment improves product freshness and supports the rapid growth of the food service segment.",
    category: "company",
    publishedAt: "2026-03-22",
    author: "Group Communications",
    cover: "from-emerald-500 via-green-500 to-lime-400",
  },
  {
    slug: "annual-leadership-summit-2026",
    title: "Annual leadership summit gathers all divisions",
    summary:
      "Executives across distribution, retail, and services aligned on the 2026 group strategy.",
    body:
      "Paris United Group Holding hosted its annual leadership summit, bringing together executives from every division to align on the 2026 strategy. Sessions covered customer experience, operational excellence, and sustainability priorities.",
    category: "event",
    publishedAt: "2026-02-18",
    author: "Group Communications",
    cover: "from-indigo-500 via-blue-500 to-sky-400",
    featured: true,
  },
  {
    slug: "core-engineering-wins-fitout-contract",
    title: "Core Engineering wins major fit-out contract",
    summary:
      "A multi-floor commercial fit-out reaffirms the construction arm's reputation for delivery.",
    body:
      "Core Engineering and Construction has been awarded a multi-floor commercial fit-out project in Doha. The scope includes interior partitions, MEP works, and bespoke joinery, with delivery scheduled across two phases.",
    category: "press",
    publishedAt: "2026-01-30",
    author: "Group Communications",
    cover: "from-stone-500 via-amber-700 to-orange-600",
  },
];

export function getNews(): NewsItem[] {
  return [...NEWS].sort((a, b) =>
    a.publishedAt < b.publishedAt ? 1 : -1
  );
}

export function getFeaturedNews(): NewsItem[] {
  return getNews().filter((n) => n.featured);
}

export function getLatestNews(limit = 3): NewsItem[] {
  return getNews().slice(0, limit);
}

export function getNewsBySlug(slug: string): NewsItem | undefined {
  return NEWS.find((n) => n.slug === slug);
}

export const NEWS_CATEGORY_LABELS: Record<NewsCategory, string> = {
  company: "Company",
  event: "Event",
  press: "Press",
  csr: "CSR",
};
