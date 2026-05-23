import Link from "next/link";
import { ArrowRight, Building2, ShieldCheck, Sparkles } from "lucide-react";

import { BackendHealthCard } from "@/components/backend-health-card";
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
    status: "current",
    summary:
      "Website Admin and HR Admin login flows, role/permission tables, route guards, audit log, and seed users.",
  },
  {
    phase: "Phase 3 – 4",
    title: "Public website UI",
    status: "planned",
    summary:
      "Premium glassmorphism layout, hero, sectors, leadership, careers, contact, media.",
  },
  {
    phase: "Phase 5 – 6",
    title: "Website admin CMS",
    status: "planned",
    summary:
      "Dashboard, menus, pages, hero slides, companies, leadership, news, media, contact inbox.",
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
    <main className="relative min-h-screen overflow-hidden">
      <BackgroundDecor />

      <section className="container mx-auto flex flex-col gap-12 px-4 py-16 sm:py-20 lg:py-24">
        <header className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Phase 1 · Project foundation
          </div>
          <h1 className="mt-5 text-3xl font-semibold leading-tight tracking-tight sm:text-5xl">
            {env.siteName}
          </h1>
          <p className="mt-4 text-base text-muted-foreground sm:text-lg">
            A diversified business group across retail, wholesale
            distribution, FMCG, fashion, packaging, fresh food, building
            materials, garages, real estate, and construction. This is the
            Phase 1 foundation – the corporate website and HR ATS portal
            will be built on top of this stack in the upcoming phases.
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
        </header>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <FeatureCard
            icon={<Building2 className="h-5 w-5" />}
            title="Modular monorepo"
            description="Backend (FastAPI) and frontend (Next.js App Router) live side by side with shared docs."
          />
          <FeatureCard
            icon={<ShieldCheck className="h-5 w-5" />}
            title="Production-ready scaffolding"
            description="PostgreSQL + SQLAlchemy + Alembic, typed config, CORS, health checks, and clean folder layout."
          />
          <FeatureCard
            icon={<Sparkles className="h-5 w-5" />}
            title="Premium UI toolkit"
            description="Tailwind, shadcn/ui primitives, Framer Motion, Lucide icons, and Recharts pre-wired."
          />
        </div>

        <BackendHealthCard />

        <section>
          <h2 className="text-xl font-semibold sm:text-2xl">Roadmap</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Phases unlock sequentially. Each phase ships isolated, reviewable
            increments.
          </p>
          <ol className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
            {milestones.map((m) => (
              <li key={m.phase} className="glass-card p-5">
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
              </li>
            ))}
          </ol>
        </section>

        <footer className="text-sm text-muted-foreground">
          © {new Date().getFullYear()} {env.siteName}. All rights reserved.
        </footer>
      </section>
    </main>
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
    <div className="glass-card p-6">
      <div className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
        {icon}
      </div>
      <h3 className="mt-4 text-lg font-semibold">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
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

function BackgroundDecor() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
    >
      <div className="absolute -left-32 top-[-10%] h-72 w-72 rounded-full bg-primary/30 blur-3xl" />
      <div className="absolute right-[-10%] top-1/3 h-80 w-80 rounded-full bg-fuchsia-500/20 blur-3xl" />
      <div className="absolute bottom-[-10%] left-1/3 h-72 w-72 rounded-full bg-emerald-400/20 blur-3xl" />
    </div>
  );
}
