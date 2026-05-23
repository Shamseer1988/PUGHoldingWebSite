/**
 * Site-wide editorial content used by Phase 4 pages (hero, stats,
 * sectors, vision, mission, values, history timeline).
 *
 * Phase 5 will let the website admin edit each block from the CMS,
 * keeping the same shape.
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
// Hero slides
// ---------------------------------------------------------------------------

export interface HeroSlide {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
  cta?: { label: string; href: string };
  secondaryCta?: { label: string; href: string };
  /** Tailwind gradient classes used for the background. */
  gradient: string;
  order: number;
  active: boolean;
}

export const HERO_SLIDES: HeroSlide[] = [
  {
    id: "slide-1",
    eyebrow: "Paris United Group Holding",
    title: "Powering everyday life across the GCC.",
    description:
      "Retail, distribution, FMCG, fashion, packaging, fresh food, building materials, garages, real estate, and construction — all under one trusted group.",
    cta: { label: "Explore the group", href: "/companies" },
    secondaryCta: { label: "Contact us", href: "/contact" },
    gradient: "from-pug-green-800 via-pug-green-600 to-pug-gold-500",
    order: 1,
    active: true,
  },
  {
    id: "slide-2",
    eyebrow: "Retail · Distribution · Services",
    title: "Customer experience is the product.",
    description:
      "Hypermarkets, minimarts, grocery shops, garages, and real estate — designed around what families and businesses actually need every day.",
    cta: { label: "Our companies", href: "/companies" },
    secondaryCta: { label: "Latest news", href: "/news" },
    gradient: "from-pug-gold-700 via-pug-gold-500 to-pug-green-500",
    order: 2,
    active: true,
  },
  {
    id: "slide-3",
    eyebrow: "Build your career",
    title: "Talented teams, real impact.",
    description:
      "Join one of Qatar's most diversified groups. Roles open across retail operations, FMCG sales, engineering, real estate, and HR.",
    cta: { label: "View open roles", href: "/careers" },
    secondaryCta: { label: "About us", href: "/about" },
    gradient: "from-pug-green-600 via-pug-green-500 to-pug-gold-600",
    order: 3,
    active: true,
  },
];

// ---------------------------------------------------------------------------
// Statistics
// ---------------------------------------------------------------------------

export interface StatItem {
  label: string;
  value: number;
  suffix?: string;
  icon: LucideIcon;
}

export const STATS: StatItem[] = [
  { label: "Group companies", value: 14, icon: Building2 },
  { label: "Retail branches", value: 56, suffix: "+", icon: ShoppingBag },
  { label: "Employees", value: 2500, suffix: "+", icon: Users },
  { label: "Business sectors", value: 3, icon: Briefcase },
  { label: "Customers served daily", value: 100000, suffix: "+", icon: HandHeart },
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
