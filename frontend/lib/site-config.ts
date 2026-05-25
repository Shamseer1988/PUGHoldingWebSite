/**
 * Static site configuration used across the public layout.
 *
 * Phase 3 keeps everything hard-coded so the public shell renders
 * without backend wiring. Phase 5/6 will replace this with API-backed
 * data (menus, social links, contact details, etc.) without changing
 * any component that consumes it.
 */
import type { LucideIcon } from "lucide-react";
import {
  Facebook,
  Instagram,
  Linkedin,
  Mail,
  MapPin,
  Phone,
  Youtube,
} from "lucide-react";

export type NavMega = "companies";

export interface NavChild {
  label: string;
  href: string;
  /** Optional one-line description rendered under the label in dropdowns. */
  description?: string;
}

export interface NavItem {
  label: string;
  href: string;
  children?: NavChild[];
  /** When set, render a custom mega-menu instead of the standard dropdown. */
  mega?: NavMega;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Home", href: "/" },
  {
    label: "About Us",
    href: "/about",
    children: [
      {
        label: "Our story",
        href: "/about",
        description: "Vision, mission, and core values",
      },
      {
        label: "Leadership",
        href: "/about#leadership",
        description: "Chairman, MD, and Executive Directors",
      },
      {
        label: "Our history",
        href: "/about",
        description: "Two decades of growth across the GCC",
      },
    ],
  },
  {
    label: "Group Companies",
    href: "/companies",
    mega: "companies",
  },
  { label: "News & Events", href: "/news" },
  { label: "Careers", href: "/careers" },
  { label: "Media", href: "/media" },
  { label: "Contact Us", href: "/contact" },
];

/**
 * Primary header CTA shown on the desktop navbar and at the bottom of
 * the mobile drawer. Single source of truth so a future site-settings
 * lift can replace this constant without touching the navbar.
 */
export const PRIMARY_CTA = {
  label: "Join Us",
  href: "/careers",
} as const;

export interface SocialLink {
  label: string;
  href: string;
  icon: LucideIcon;
}

export const SOCIAL_LINKS: SocialLink[] = [
  { label: "LinkedIn", href: "#", icon: Linkedin },
  { label: "Instagram", href: "#", icon: Instagram },
  { label: "Facebook", href: "#", icon: Facebook },
  { label: "YouTube", href: "#", icon: Youtube },
];

export interface ContactDetail {
  label: string;
  value: string;
  href?: string;
  icon: LucideIcon;
}

export const CONTACT_DETAILS: ContactDetail[] = [
  {
    label: "Address",
    value: "Doha, Qatar",
    icon: MapPin,
  },
  {
    label: "Phone",
    value: "+974 0000 0000",
    href: "tel:+974000000000",
    icon: Phone,
  },
  {
    label: "Email",
    value: "info@parisunitedgroup.com",
    href: "mailto:info@parisunitedgroup.com",
    icon: Mail,
  },
];

export interface FooterColumn {
  title: string;
  links: { label: string; href: string }[];
}

export const FOOTER_COLUMNS: FooterColumn[] = [
  {
    title: "Group",
    links: [
      { label: "About Us", href: "/about" },
      { label: "Leadership", href: "/about#leadership" },
      { label: "Group Companies", href: "/companies" },
      { label: "News & Events", href: "/news" },
    ],
  },
  {
    title: "Sectors",
    links: [
      { label: "Distribution", href: "/companies?category=distribution" },
      { label: "Retail", href: "/companies?category=retail" },
      { label: "Services", href: "/companies?category=services" },
    ],
  },
  {
    title: "Connect",
    links: [
      { label: "Careers", href: "/careers" },
      { label: "Media", href: "/media" },
      { label: "Contact Us", href: "/contact" },
      { label: "Newsletter", href: "/#newsletter" },
    ],
  },
];

/** Legal links rendered in the footer's bottom bar (separate from the
 *  main nav columns). Kept in one place so the footer and any future
 *  cookie-banner share the same source of truth. */
export const FOOTER_LEGAL_LINKS: { label: string; href: string }[] = [
  { label: "Privacy Policy", href: "/privacy-policy" },
  { label: "Terms & Conditions", href: "/terms-and-conditions" },
];
