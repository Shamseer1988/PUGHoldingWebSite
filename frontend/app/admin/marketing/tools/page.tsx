import Link from "next/link";
import { FileArchive, Link2, Wrench } from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";

interface ToolCard {
  href: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
}

const TOOLS: ToolCard[] = [
  {
    href: "/admin/marketing/tools/pdf-compressor",
    title: "PDF Compression",
    description:
      "Shrink an oversized catalogue PDF before uploading. Choose a quality preset and download a smaller file in 5–20 seconds.",
    icon: FileArchive,
    accent: "text-pug-gold-700 dark:text-pug-gold-300 bg-pug-gold-500/15",
  },
  {
    href: "/admin/marketing/tools/url-shortener",
    title: "URL Shortener",
    description:
      "Create branded short links on parisunitedgroup.com/go/… Track clicks and disable links without rebuilding the campaign asset.",
    icon: Link2,
    accent: "text-emerald-700 dark:text-emerald-300 bg-emerald-500/15",
  },
];

export default function MarketingToolsPage() {
  return (
    <AdminShell
      title="Marketing Tools"
      description="Self-serve utilities used while preparing campaign assets — keep them close to the catalogue + campaign editors."
    >
      <ul className="grid gap-4 sm:grid-cols-2">
        {TOOLS.map((tool) => {
          const Icon = tool.icon;
          return (
            <li key={tool.href}>
              <Link
                href={tool.href}
                className="group flex h-full flex-col gap-3 rounded-2xl border border-border/60 bg-card p-5 shadow-sm transition-colors hover:border-primary/40 hover:bg-primary/[0.03]"
              >
                <div className="flex items-start gap-3">
                  <span
                    className={`inline-flex h-10 w-10 items-center justify-center rounded-full ${tool.accent}`}
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <h2 className="text-base font-semibold">{tool.title}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {tool.description}
                    </p>
                  </div>
                </div>
                <span className="mt-auto inline-flex items-center gap-1.5 self-end text-xs font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                  Open <Wrench className="h-3 w-3" />
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </AdminShell>
  );
}
