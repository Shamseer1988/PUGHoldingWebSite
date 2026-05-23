/**
 * Centralised dummy data used by Phase 4 public pages.
 *
 * Phase 6 will replace each `getX()` helper with an API call to the
 * backend without changing any consumer component. The shape of the
 * data therefore mirrors the API responses we plan to expose.
 */
export type CompanyCategory = "distribution" | "retail" | "services";

export interface Company {
  slug: string;
  name: string;
  category: CompanyCategory;
  shortDescription: string;
  longDescription: string;
  services: string[];
  branches?: string;
  /** Optional gradient classes used as placeholder logo background. */
  accent: string;
  /** Initials shown on the placeholder logo card. */
  initials: string;
  contact?: {
    phone?: string;
    email?: string;
    address?: string;
    website?: string;
  };
}

export const COMPANIES: Company[] = [
  // Distribution
  {
    slug: "paris-food-international",
    name: "Paris Food International",
    category: "distribution",
    shortDescription: "FMCG wholesale, department store supply, and HORECA supply.",
    longDescription:
      "Paris Food International is the group's flagship FMCG distribution arm, supplying department stores, hypermarkets, hotels, restaurants, and catering operators across Qatar and the wider GCC. With deep brand partnerships and a temperature-controlled supply chain, it powers daily delivery to thousands of points of sale.",
    services: ["FMCG wholesale", "Department store supply", "HORECA supply"],
    accent: "from-blue-500 via-sky-500 to-cyan-400",
    initials: "PF",
    contact: {
      phone: "+974 0000 0001",
      email: "contact@parisfood.example.com",
      address: "Industrial Area, Doha",
    },
  },
  {
    slug: "doha-fashion",
    name: "Doha Fashion",
    category: "distribution",
    shortDescription: "Cosmetics and stationery distribution.",
    longDescription:
      "Doha Fashion brings global cosmetics and stationery brands to retailers across the region. From premium beauty to back-to-school supplies, the team handles brand activation, merchandising, and last-mile distribution.",
    services: ["Cosmetics", "Stationery", "Brand activation"],
    accent: "from-fuchsia-500 via-pink-500 to-rose-400",
    initials: "DF",
    contact: {
      phone: "+974 0000 0002",
      email: "contact@dohafashion.example.com",
    },
  },
  {
    slug: "paris-packing",
    name: "Paris Packing",
    category: "distribution",
    shortDescription: "Packing items, pulses, and spices distribution.",
    longDescription:
      "Paris Packing supplies wholesale and retail customers with packaged pulses, spices, and consumer-ready packing solutions. Quality control and modern packaging lines keep products fresh from origin to shelf.",
    services: ["Packing items", "Pulses", "Spices"],
    accent: "from-amber-500 via-orange-500 to-red-400",
    initials: "PP",
  },
  {
    slug: "maharib-fresh-trading",
    name: "Maharib Fresh Trading",
    category: "distribution",
    shortDescription: "Vegetable supply and fresh produce trading.",
    longDescription:
      "Maharib Fresh Trading sources vegetables and fresh produce from trusted growers and delivers to wholesale buyers, supermarkets, restaurants, and grocery chains. A cold-chain network keeps every box farm-fresh.",
    services: ["Vegetable supply", "Fresh produce", "Cold chain logistics"],
    accent: "from-emerald-500 via-green-500 to-lime-400",
    initials: "MF",
  },
  {
    slug: "yellowtech-trading",
    name: "YellowTech Trading and Contracting",
    category: "distribution",
    shortDescription: "Building materials supply and contracting.",
    longDescription:
      "YellowTech Trading and Contracting supplies building materials to projects of every scale, with a contracting division that delivers fit-outs, MEP works, and specialist installation services across Qatar.",
    services: ["Building materials supply", "Contracting", "MEP works"],
    accent: "from-yellow-500 via-amber-500 to-orange-400",
    initials: "YT",
  },

  // Retail
  {
    slug: "paris-hyper-market",
    name: "Paris Hyper Market",
    category: "retail",
    shortDescription: "Modern hypermarkets serving families across Qatar and KSA.",
    longDescription:
      "Paris Hyper Market is the group's flagship hypermarket chain. Wide aisles, fresh food, household goods, electronics, and a friendly in-store experience are the promise — backed by competitive pricing and weekly promotions.",
    services: ["Grocery", "Fresh food", "Household", "Electronics"],
    branches: "4 branches in Qatar · 1 branch in KSA",
    accent: "from-rose-500 via-red-500 to-orange-400",
    initials: "PH",
  },
  {
    slug: "paris-express",
    name: "Paris Express",
    category: "retail",
    shortDescription: "Neighbourhood minimarts for everyday essentials.",
    longDescription:
      "Paris Express minimarts bring everyday essentials closer to where customers live. Carefully curated assortments, quick checkout, and a familiar shopping experience for residents on the go.",
    services: ["Minimarts", "Daily essentials", "Convenience"],
    branches: "Above 6 branches",
    accent: "from-indigo-500 via-blue-500 to-sky-400",
    initials: "PE",
  },
  {
    slug: "al-mihrab-groceries",
    name: "Al Mihrab Groceries",
    category: "retail",
    shortDescription: "A chain of neighbourhood grocery shops with over 45 stores.",
    longDescription:
      "Al Mihrab Groceries operates a network of community grocery shops, providing fresh and packaged goods to neighbourhoods across Qatar with a focus on accessibility and consistent service.",
    services: ["Grocery", "Beverages", "Household goods"],
    branches: "Above 45 shops",
    accent: "from-violet-500 via-purple-500 to-fuchsia-400",
    initials: "AM",
  },
  {
    slug: "maharib-fish",
    name: "Maharib Fish",
    category: "retail",
    shortDescription: "Fresh fish supply to retail and wholesale customers.",
    longDescription:
      "Maharib Fish operates fresh seafood counters and supplies fish and shellfish to retailers, restaurants, and households. Sourced from trusted fisheries and delivered daily.",
    services: ["Fresh fish", "Shellfish", "Wholesale supply"],
    accent: "from-teal-500 via-cyan-500 to-sky-400",
    initials: "MF",
  },

  // Services
  {
    slug: "yellowtech-garage",
    name: "YellowTech Garage",
    category: "services",
    shortDescription: "Light vehicle garage and service centre.",
    longDescription:
      "YellowTech Garage offers full-service light vehicle maintenance: scheduled servicing, diagnostics, brakes, electricals, body work, and detailing — all with transparent pricing and certified technicians.",
    services: ["Vehicle maintenance", "Diagnostics", "Body work"],
    accent: "from-amber-400 via-yellow-500 to-orange-500",
    initials: "YG",
  },
  {
    slug: "express-diesel-turbo",
    name: "Express Diesel Turbo",
    category: "services",
    shortDescription: "Specialist diesel and hydraulic garage.",
    longDescription:
      "Express Diesel Turbo is the group's heavy-duty specialist — diesel engines, turbochargers, hydraulics, and industrial machinery serviced by experienced engineers with rapid turnaround.",
    services: ["Diesel engines", "Turbochargers", "Hydraulic systems"],
    accent: "from-slate-600 via-zinc-600 to-stone-500",
    initials: "ED",
  },
  {
    slug: "auto-plux-car-service",
    name: "Auto Plux Car Service",
    category: "services",
    shortDescription: "Quick-fix car garage for fast service jobs.",
    longDescription:
      "Auto Plux Car Service is a quick-fix garage focused on speed and convenience: oil changes, tyre fitting, battery replacement, AC top-ups, and minor repairs while you wait.",
    services: ["Quick service", "Tyres", "Batteries", "AC service"],
    accent: "from-sky-500 via-blue-500 to-indigo-400",
    initials: "AP",
  },
  {
    slug: "greentech-real-estate",
    name: "Greentech Real Estate Broker",
    category: "services",
    shortDescription: "Real estate brokerage and property advisory.",
    longDescription:
      "Greentech Real Estate Broker advises buyers, sellers, and tenants across residential and commercial property — from off-plan investments to managed leasing.",
    services: ["Property sales", "Leasing", "Investment advisory"],
    accent: "from-emerald-500 via-teal-500 to-cyan-400",
    initials: "GR",
  },
  {
    slug: "core-engineering",
    name: "Core Engineering and Construction",
    category: "services",
    shortDescription: "Construction, fit-outs, and engineering services.",
    longDescription:
      "Core Engineering and Construction delivers turnkey construction projects, commercial fit-outs, refurbishments, and specialist engineering works — combining in-house engineering talent with a trusted subcontractor network.",
    services: ["Construction", "Fit-outs", "Engineering services"],
    accent: "from-stone-500 via-amber-700 to-orange-600",
    initials: "CE",
  },
];

export function getCompanies(): Company[] {
  return COMPANIES;
}

export function getCompaniesByCategory(category: CompanyCategory): Company[] {
  return COMPANIES.filter((c) => c.category === category);
}

export function getCompanyBySlug(slug: string): Company | undefined {
  return COMPANIES.find((c) => c.slug === slug);
}

export const CATEGORY_LABELS: Record<CompanyCategory, string> = {
  distribution: "Distribution",
  retail: "Retail",
  services: "Services",
};
