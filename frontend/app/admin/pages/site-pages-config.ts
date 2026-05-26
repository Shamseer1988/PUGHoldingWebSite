/**
 * Registry of every admin-editable predefined site page. Drives both
 * the card grid at the top of /admin/pages and the editor at
 * /admin/pages/site/[key].
 *
 * Keep the keys in sync with backend SITE_PAGE_KEYS — the editor 404s
 * on unknown keys so a typo here would silently hide a page from the
 * admin UI without breaking the public site.
 */
import {
  Briefcase,
  Building2,
  ImageIcon,
  Info,
  Mail,
  Newspaper,
  type LucideIcon,
} from "lucide-react";

import type { SitePageKey } from "@/lib/admin/types";


export type SectionFieldKey = "eyebrow" | "title" | "body";


export interface SectionConfig {
  /** Stable key persisted in the JSON `sections` column. */
  key: string;
  /** Heading shown above the form group. */
  label: string;
  /** Optional one-liner under the label. */
  hint?: string;
  /** Which subfields are surfaced in the editor for this section. */
  fields: SectionFieldKey[];
  /** Per-field placeholder copy that previews on the public site. */
  placeholders?: Partial<Record<SectionFieldKey, string>>;
}


export interface SitePageConfig {
  key: SitePageKey;
  label: string;
  description: string;
  /** Public-site URL this row drives. */
  route: string;
  icon: LucideIcon;
  /** Section editors to render below the hero + banner. */
  sections: SectionConfig[];
  /** Placeholder copy shown in the hero inputs (greys out — non-blocking). */
  placeholders: {
    heroEyebrow?: string;
    heroTitle?: string;
    heroDescription?: string;
  };
}


export const SITE_PAGE_REGISTRY: Record<SitePageKey, SitePageConfig> = {
  about: {
    key: "about",
    label: "About",
    description:
      "Hero, vision, mission, history intro, and the leadership section heading.",
    route: "/about",
    icon: Info,
    placeholders: {
      heroEyebrow: "About Paris United Group",
      heroTitle:
        "A diversified holding group focused on quality, service, and operational excellence.",
      heroDescription:
        "Paris United Group Holding operates across retail, distribution, and services. …",
    },
    sections: [
      {
        key: "vision",
        label: "Vision card",
        hint: "Left card under “Vision and mission”.",
        fields: ["title", "body"],
        placeholders: {
          title: "Our vision",
          body: "To be the most trusted diversified group in the GCC …",
        },
      },
      {
        key: "mission",
        label: "Mission card",
        hint: "Right card under “Vision and mission”.",
        fields: ["title", "body"],
        placeholders: {
          title: "Our mission",
          body: "We bring quality products and dependable services …",
        },
      },
      {
        key: "history_intro",
        label: "History intro paragraph",
        hint: "Lead paragraph above the timeline. The timeline milestones themselves are part of the bundle for now.",
        fields: ["body"],
        placeholders: {
          body: "We started with one focused FMCG distribution business …",
        },
      },
      {
        key: "leadership_header",
        label: "Leadership section heading",
        hint: "Eyebrow + title + intro line above the leadership cards. The cards themselves are managed under Leadership.",
        fields: ["eyebrow", "title", "body"],
        placeholders: {
          eyebrow: "Leadership",
          title: "Messages from our leadership",
          body: "The Chairman, Managing Director, and Executive Directors.",
        },
      },
    ],
  },
  companies: {
    key: "companies",
    label: "Group Companies",
    description:
      "Hero copy for the /companies listing. Individual companies are managed under Companies.",
    route: "/companies",
    icon: Building2,
    placeholders: {
      heroEyebrow: "Our companies",
      heroTitle: "Explore the Paris United Group",
      heroDescription:
        "A diversified portfolio of distribution, retail, and services businesses …",
    },
    sections: [],
  },
  careers: {
    key: "careers",
    label: "Careers",
    description:
      "Hero copy for the /careers landing page. Job openings are managed under HR → Jobs.",
    route: "/careers",
    icon: Briefcase,
    placeholders: {
      heroEyebrow: "Careers",
      heroTitle: "Build your career with Paris United Group",
      heroDescription:
        "Roles across retail operations, FMCG sales, engineering …",
    },
    sections: [],
  },
  contact: {
    key: "contact",
    label: "Contact us",
    description:
      "Hero copy for the /contact page. Contact details, social links, and the map embed are managed under Site settings.",
    route: "/contact",
    icon: Mail,
    placeholders: {
      heroEyebrow: "Contact",
      heroTitle: "Talk to Paris United Group",
      heroDescription:
        "Reach the right department fast. Use the form below or any of the quick actions on the right.",
    },
    sections: [],
  },
  news: {
    key: "news",
    label: "News & events",
    description:
      "Hero copy for the /news listing. Individual articles are managed under News.",
    route: "/news",
    icon: Newspaper,
    placeholders: {
      heroEyebrow: "News & events",
      heroTitle: "What's happening at Paris United Group",
      heroDescription:
        "Store launches, partnerships, CSR initiatives, and updates from across the group.",
    },
    sections: [],
  },
  media: {
    key: "media",
    label: "Media gallery",
    description:
      "Hero copy for the /media gallery. Photos and videos are uploaded under Media.",
    route: "/media",
    icon: ImageIcon,
    placeholders: {
      heroEyebrow: "Media",
      heroTitle: "Stores, events, team, and campaigns",
      heroDescription:
        "A glimpse of life at Paris United Group — pick a category or click a tile to view it larger.",
    },
    sections: [],
  },
};


export const SITE_PAGE_LIST: SitePageConfig[] = [
  SITE_PAGE_REGISTRY.about,
  SITE_PAGE_REGISTRY.companies,
  SITE_PAGE_REGISTRY.careers,
  SITE_PAGE_REGISTRY.contact,
  SITE_PAGE_REGISTRY.news,
  SITE_PAGE_REGISTRY.media,
];


export function isSitePageKey(value: string): value is SitePageKey {
  return value in SITE_PAGE_REGISTRY;
}
