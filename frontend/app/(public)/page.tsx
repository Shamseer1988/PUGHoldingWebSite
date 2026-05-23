import Link from "next/link";
import {
  ArrowRight,
  Building2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { BackendHealthCard } from "@/components/backend-health-card";
import { GlassCard } from "@/components/site/glass-card";
import { Section } from "@/components/site/section";
import { Button } from "@/components/ui/button";
import { env } from "@/lib/env";

const milestones = [
  {
    phase: "Phase 1",
    title: "Project foundation",
    status: "done",
    summary:
      "Next.js + TypeScript + Tailwind + shadcn/ui + Framer Motion + Lucide + Recharts; FastAPI + SQLAlchemy + Alembic; health check API.",
  },
  {
    phase: "Phase 2",
    title: "Auth and separate logins",
    status: "done",
    summary:
      "Website Admin and HR Admin login flows, role/permission tables, route guards, audit log, and seed users.",
  },
  {
    phase: "Phase 3",
    title: "Public website UI foundation",
    status: "current",
    summary:
      "Sticky transparent navbar, mobile hamburger drawer, light/dark toggle, footer, glass components, floating Ask PUG AI launcher, no-overflow safety net.",
  },
  {
    phase: "Phase 4",
    title: "Public pages (dummy content)",
    status: "next",
    summary:
      "Home, About, Group Companies (+ detail), News & Events (+ detail), Careers (+ job detail), Contact, Media.",
  },
  {
    phase: "Phase 5 – 6",
    title: "Website admin CMS",
    status: "planned",
    summary:
      "Dashboard, menus, pages, hero slides, companies, leadership, news, media, contact inbox; public pages backed by API.",
  },
  {
    phase: "Phase 7 – 16",
    title: "HR ATS portal",
    status: "planned",
    summary:
      "Job openings, CV upload + parsing, scoring engine, AI review, workflow, interviews, reports.",
  },
  {
    phase: "Phase 17 – 20",
    title: "AI assistant + production",
    status: "planned",
    summary:
      "Public Ask PUG AI, responsive polish, security hardening, AWS / Nginx / Cloudflare deployment.",
  },
];

export default function HomePage() {
  return (
    <>
      {/* Hero / shell preview */}
      <Section
        className="relative overflow-hidden pb-12 pt-12 sm:pb-16 sm:pt-16 lg:pt-20"
        containerClassName="relative"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
        >
          <div className="absolute -left-32 top-[-10%] h-72 w-72 rounded-full bg-primary/30 blur-3xl" />
          <div className="absolute right-[-10%] top-1/3 h-80 w-80 rounded-full bg-fuchsia-500/20 blur-3xl" />
          <div className="absolute bottom-[-10%] left-1/3 h-72 w-72 rounded-full bg-emerald-400/20 blur-3xl" />
        </div>

        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Phase 3 · Public website UI foundation
          </span>
          <h1 className="mt-5 text-balance text-3xl font-semibold leading-tight tracking-tight sm:text-5xl">
            {env.siteName}
          </h1>
          <p className="mt-4 text-pretty text-base text-muted-foreground sm:text-lg">
            A diversified business group across retail, wholesale
            distribution, FMCG, fashion, packaging, fresh food, building
            materials, garages, real estate, and construction. This page is
            the Phase 3 shell preview — Phase 4 fills in the real hero,
            sectors, leadership, news, and careers content.
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            <Button asChild>
              <Link href="/admin/login">
                Website admin login
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/hr/login">
                HR ATS login
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </Section>

      {/* Shell capabilities */}
      <Section
        eyebrow="Phase 3 deliverables"
        title="A polished, responsive public shell"
        description="Every public page from Phase 4 onward inherits this layout — navbar, footer, theme toggle, and the floating Ask PUG AI launcher."
        centered
      >
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <FeatureCard
            icon={<Building2 className="h-5 w-5" />}
            title="Sticky transparent navbar"
            description="Glassmorphism on scroll, dropdown menu for Group Companies, accessible mobile drawer with smooth animation."
          />
          <FeatureCard
            icon={<ShieldCheck className="h-5 w-5" />}
            title="No mobile overflow"
            description="Tested at 360 / 390 / 430 / 768 / 1024 / 1440 px. Body locks horizontal scroll and images cap at parent width."
          />
          <FeatureCard
            icon={<Sparkles className="h-5 w-5" />}
            title="Premium primitives"
            description="GlassCard, Section, ThemeToggle, AskPugAiButton — reusable building blocks for every page in later phases."
          />
        </div>
      </Section>

      {/* Backend health */}
      <Section
        eyebrow="Backend wiring"
        title="Live FastAPI health check"
        description="The public shell still talks to the backend health endpoint so you can verify both apps are running."
      >
        <BackendHealthCard />
      </Section>

      {/* Roadmap */}
      <Section eyebrow="Roadmap" title="Phased delivery">
        <ol className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {milestones.map((m) => (
            <li key={m.phase}>
              <GlassCard className="h-full p-5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {m.phase}
                  </span>
                  <StatusPill status={m.status} />
                </div>
                <h3 className="mt-2 text-lg font-semibold">{m.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  {m.summary}
                </p>
              </GlassCard>
            </li>
          ))}
        </ol>
      </Section>
    </>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <GlassCard>
      <div className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
        {icon}
      </div>
      <h3 className="mt-4 text-lg font-semibold">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </GlassCard>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    done: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
    current: "bg-sky-500/15 text-sky-600 dark:text-sky-300",
    next: "bg-amber-500/15 text-amber-600 dark:text-amber-300",
    planned: "bg-muted text-muted-foreground",
  };
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
        map[status] ?? map.planned
      }`}
    >
      {status}
    </span>
  );
}
