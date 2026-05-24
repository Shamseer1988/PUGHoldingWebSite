/**
 * Static editorial content that doesn't (yet) live in the database.
 *
 * Hero slides, companies, news, leadership, and site settings are now
 * fetched from the backend via lib/public-api.ts. Stats, sectors,
 * vision/mission/values, and the history timeline remain here as
 * static config — a Phase 5 follow-up CMS module can move them too.
 */
import type { LucideIcon } from "lucide-react";
import {
  Award,
  Briefcase,
  Building2,
  HandHeart,
  Lightbulb,
  ShieldCheck,
  ShoppingBag,
  Truck,
  Users,
  Wrench,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Statistics
// ---------------------------------------------------------------------------

/**
 * Tile role inside the homepage bento stats grid.
 *
 *  - "hero"     → large dark-green tile spanning the left column on
 *                 desktop; gets the sparkline + trend pill treatment.
 *  - "accent"   → gold gradient tile, used once for visual rhythm.
 *  - "sectors"  → white tile with a 3-segment progress bar under the
 *                 number (so a value like "3" still has visual weight).
 *  - "default"  → plain white tile — the fallback when the field is
 *                 omitted or unknown.
 */
export type StatTileVariant = "default" | "hero" | "accent" | "sectors";

export interface StatItem {
  label: string;
  value: number;
  suffix?: string;
  icon: LucideIcon;
  /** Optional layout role for the bento grid. Defaults to "default". */
  tile_variant?: StatTileVariant;
  /** Optional trend percentage (e.g. 12 → "+12% YoY"). */
  trend_percent?: number;
  /** Optional override for trend label (e.g. "+4 in Q2"). */
  trend_label?: string;
  /** Optional sparkline data — 6 to 12 normalised values 0..1. */
  sparkline_points?: number[];
}

export const STATS: StatItem[] = [
  {
    label: "Group companies",
    value: 14,
    icon: Building2,
    tile_variant: "default",
  },
  {
    label: "Retail branches",
    value: 56,
    suffix: "+",
    icon: ShoppingBag,
    tile_variant: "default",
    trend_label: "+4 in Q2",
  },
  {
    label: "Employees",
    value: 2500,
    suffix: "+",
    icon: Users,
    tile_variant: "accent",
  },
  {
    label: "Business sectors",
    value: 3,
    icon: Briefcase,
    tile_variant: "sectors",
  },
  {
    label: "Customers served daily",
    value: 100000,
    suffix: "+",
    icon: HandHeart,
    tile_variant: "hero",
    trend_percent: 12,
    sparkline_points: [0.2, 0.25, 0.35, 0.4, 0.55, 0.65, 0.78, 0.9, 1.0],
  },
];

// ---------------------------------------------------------------------------
// Business sectors
// ---------------------------------------------------------------------------

export interface SectorBlock {
  id: string;
  title: string;
  description: string;
  href: string;
  icon: LucideIcon;
  accent: string;
}

export const SECTORS: SectorBlock[] = [
  {
    id: "retail",
    title: "Retail",
    description:
      "Hypermarkets, minimarts, grocery shops, and fresh fish counters serving families across Qatar and KSA.",
    href: "/companies?category=retail",
    icon: ShoppingBag,
    accent: "from-pug-gold-500 via-pug-gold-600 to-pug-gold-700",
  },
  {
    id: "distribution",
    title: "Distribution",
    description:
      "FMCG wholesale, fashion, packaging, fresh produce, and building materials moved reliably at scale.",
    href: "/companies?category=distribution",
    icon: Truck,
    accent: "from-pug-green-500 via-pug-green-600 to-pug-green-700",
  },
  {
    id: "services",
    title: "Services",
    description:
      "Garages, real estate brokerage, and engineering & construction services for individuals and businesses.",
    href: "/companies?category=services",
    icon: Wrench,
    accent: "from-pug-green-600 via-pug-green-500 to-pug-gold-500",
  },
];

// ---------------------------------------------------------------------------
// About / vision / mission / values
// ---------------------------------------------------------------------------

export const ABOUT_INTRO = {
  eyebrow: "About Paris United Group",
  title:
    "A diversified holding group focused on quality, service, and operational excellence.",
  description:
    "Paris United Group Holding operates across retail, distribution, and services. We are a long-term builder of trusted, customer-obsessed businesses that serve communities and commercial partners every day.",
};

export const VISION = {
  title: "Our vision",
  body:
    "To be the most trusted diversified group in the GCC — delighting customers, partners, and employees across every business we operate.",
};

export const MISSION = {
  title: "Our mission",
  body:
    "We bring quality products and dependable services to communities and businesses, powered by operational excellence, a customer-first culture, and a long-term mindset.",
};

export interface CoreValue {
  title: string;
  description: string;
  icon: LucideIcon;
}

export const CORE_VALUES: CoreValue[] = [
  {
    title: "Customer obsession",
    description:
      "Every decision starts with the customer experience — fast, fair, and friendly.",
    icon: HandHeart,
  },
  {
    title: "Quality",
    description:
      "We never compromise on the quality of our products, services, or relationships.",
    icon: Award,
  },
  {
    title: "Integrity",
    description:
      "We do business the right way — honest, transparent, and accountable.",
    icon: ShieldCheck,
  },
  {
    title: "Innovation",
    description:
      "Continuous improvement is part of the job, not a special project.",
    icon: Lightbulb,
  },
];

// ---------------------------------------------------------------------------
// History timeline
// ---------------------------------------------------------------------------

export interface TimelineEntry {
  year: string;
  title: string;
  description: string;
}

export const TIMELINE: TimelineEntry[] = [
  {
    year: "2008",
    title: "Group founded",
    description:
      "Paris United Group was founded with a focus on FMCG distribution in Qatar.",
  },
  {
    year: "2012",
    title: "First hypermarket",
    description:
      "Paris Hyper Market opened its first store in Doha, marking the group's move into retail.",
  },
  {
    year: "2016",
    title: "Distribution expansion",
    description:
      "Doha Fashion, Paris Packing, and Maharib Fresh Trading added scale across cosmetics, dry goods, and fresh produce.",
  },
  {
    year: "2019",
    title: "Services division launches",
    description:
      "YellowTech Garage, Greentech Real Estate, and Core Engineering established the services pillar.",
  },
  {
    year: "2022",
    title: "Regional footprint",
    description:
      "Paris Hyper Market opened its first branch outside Qatar in KSA, marking the group's regional expansion.",
  },
  {
    year: "2026",
    title: "Digital transformation",
    description:
      "Launch of the unified digital platform across the corporate website and HR ATS.",
  },
];
