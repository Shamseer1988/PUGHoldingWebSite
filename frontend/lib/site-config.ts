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

export interface NavItem {
  label: string;
  href: string;
  children?: NavItem[];
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Home", href: "/" },
  { label: "About Us", href: "/about" },
  {
    label: "Group Companies",
    href: "/companies",
    children: [
      { label: "All Companies", href: "/companies" },
      { label: "Distribution", href: "/companies?category=distribution" },
      { label: "Retail", href: "/companies?category=retail" },
      { label: "Services", href: "/companies?category=services" },
    ],
  },
  { label: "News & Events", href: "/news" },
  { label: "Careers", href: "/careers" },
  { label: "Media", href: "/media" },
  { label: "Contact Us", href: "/contact" },
];

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
