"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Clickable KPI card (acceptance criteria 5 + 6).
 *
 * Every dashboard stat is a deep link to its pre-filtered list — the
 * whole card is an anchor, so "Selected" lands on
 * ``/hr/candidates?status=selected``, "Pending offers" on
 * ``/hr/offers?status=pending_approval`` and so on. One component, used
 * for every stat card on the dashboard.
 */

export type KpiTone =
  | "neutral"
  | "info"
  | "progress"
  | "ready"
  | "success"
  | "warning"
  | "danger";

const TONE_GRADIENT: Record<KpiTone, string> = {
  neutral: "from-slate-500 to-slate-700",
  info: "from-sky-500 to-sky-700",
  progress: "from-indigo-500 to-indigo-700",
  ready: "from-violet-500 to-violet-700",
  success: "from-emerald-500 to-emerald-700",
  warning: "from-amber-500 to-amber-600",
  danger: "from-rose-500 to-rose-700",
};

interface KpiCardProps {
  label: string;
  value: number | string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  tone?: KpiTone;
  /** Optional secondary line (e.g. "+12 this week"). */
  delta?: string;
}

export function KpiCard({
  label,
  value,
  href,
  icon: Icon,
  tone = "neutral",
  delta,
}: KpiCardProps) {
  return (
    <Link
      href={href}
      className="group relative flex flex-col overflow-hidden rounded-xl border border-border/60 bg-card p-5 transition-colors hover:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="flex items-start justify-between">
        <span
          className={cn(
            "inline-flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm",
            TONE_GRADIENT[tone],
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
        <ArrowUpRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight tabular-nums">
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      {delta && (
        <p className="mt-1 text-[11px] text-muted-foreground">{delta}</p>
      )}
    </Link>
  );
}
