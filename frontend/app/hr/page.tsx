"use client";

import * as React from "react";
import Link from "next/link";
import {
  Briefcase,
  CalendarClock,
  CheckCircle2,
  Handshake,
  History,
  Megaphone,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type { DashboardSummary, FunnelStage } from "@/lib/hr/types";
import { cn } from "@/lib/utils";

const STAT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  open_jobs: Briefcase,
  total_candidates: Users,
  applications_total: Megaphone,
  applications_this_month: TrendingUp,
  ai_reviewed: Sparkles,
  highly_recommended: CheckCircle2,
  hr_review_pending: History,
  shortlisted: CheckCircle2,
  rejected: History,
  selected: CheckCircle2,
  joined: CheckCircle2,
  pending_interviews: CalendarClock,
  pending_offers: Handshake,
};

const STAT_ACCENTS: Record<string, string> = {
  open_jobs: "from-pug-green-500 to-pug-green-700",
  total_candidates: "from-pug-gold-500 to-pug-gold-700",
  applications_total: "from-pug-green-600 to-pug-gold-500",
  applications_this_month: "from-pug-gold-400 to-pug-green-500",
  ai_reviewed: "from-pug-green-500 to-pug-gold-600",
  highly_recommended: "from-pug-gold-500 to-pug-gold-700",
  hr_review_pending: "from-amber-500 to-pug-gold-500",
  shortlisted: "from-pug-green-500 to-pug-green-700",
  rejected: "from-rose-500 to-pug-gold-700",
  selected: "from-pug-green-600 to-pug-gold-500",
  joined: "from-emerald-500 to-pug-green-700",
  pending_interviews: "from-pug-gold-500 to-pug-green-600",
  pending_offers: "from-pug-green-500 to-pug-gold-700",
};

export default function HrDashboardPage() {
  const [data, setData] = React.useState<DashboardSummary | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    hrApi
      .get<DashboardSummary>("/hr/dashboard")
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err: HrApiError) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <HrShell
      title="HR Dashboard"
      description="Pipeline overview, pending interviews, offers, and audit activity."
    >
      {error && (
        <div
          role="alert"
          className="mb-6 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {/* KPI cards */}
      <section className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {data
          ? data.stats.map((stat) => {
              const Icon = STAT_ICONS[stat.key] ?? Sparkles;
              const accent =
                STAT_ACCENTS[stat.key] ?? "from-pug-green-500 to-pug-gold-500";
              return (
                <Card key={stat.key} className="overflow-hidden">
                  <CardContent className="p-5">
                    <div
                      className={cn(
                        "inline-flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm",
                        accent
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <p className="mt-3 text-2xl font-semibold tracking-tight">
                      {stat.value.toLocaleString()}
                    </p>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {stat.label}
                    </p>
                  </CardContent>
                </Card>
              );
            })
          : Array.from({ length: 12 }).map((_, i) => (
              <Card key={i} className="animate-pulse">
                <CardContent className="p-5">
                  <div className="h-9 w-9 rounded-lg bg-muted" />
                  <div className="mt-3 h-7 w-16 rounded bg-muted" />
                  <div className="mt-2 h-3 w-24 rounded bg-muted" />
                </CardContent>
              </Card>
            ))}
      </section>

      {/* Pipeline funnel + monthly trend */}
      <section className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pipeline funnel</CardTitle>
            <CardDescription>
              Applications by stage (CV received → joined).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PipelineFunnel stages={data?.pipeline_funnel ?? []} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Applications per month</CardTitle>
            <CardDescription>
              Inbound volume over time.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TrendChart
              data={data?.applications_per_month ?? []}
              color="hsl(145 45% 30%)"
            />
          </CardContent>
        </Card>
      </section>

      {/* Pending interviews + offers */}
      <section className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Pending interviews</CardTitle>
              <CardDescription>
                Scheduled interviews coming up.
              </CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link href="/hr/interviews">All interviews</Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {!data || data.pending_interviews.length === 0 ? (
              <HrEmptyState
                className="m-4 border-none p-6"
                icon={CalendarClock}
                title="No upcoming interviews"
                description="When HR schedules interviews they'll appear here, sorted by date."
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Candidate</TableHead>
                    <TableHead>Round</TableHead>
                    <TableHead className="w-40">When</TableHead>
                    <TableHead className="w-24">Mode</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.pending_interviews.map((iv) => (
                    <TableRow key={iv.id}>
                      <TableCell>
                        <p className="font-medium leading-tight">
                          {iv.candidate_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {iv.job_title ?? "—"}
                        </p>
                      </TableCell>
                      <TableCell>{iv.round_name}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatWhen(iv.scheduled_at)}
                      </TableCell>
                      <TableCell>
                        <Badge variant="muted" className="capitalize">
                          {iv.mode.replace("_", " ")}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Pending offers</CardTitle>
              <CardDescription>
                Offers in draft or sent state.
              </CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link href="/hr/offers">All offers</Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {!data || data.pending_offers.length === 0 ? (
              <HrEmptyState
                className="m-4 border-none p-6"
                icon={Handshake}
                title="No pending offers"
                description="Draft and sent offers will appear here until accepted, declined, or joined."
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Candidate</TableHead>
                    <TableHead>Salary</TableHead>
                    <TableHead className="w-32">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.pending_offers.map((offer) => (
                    <TableRow key={offer.id}>
                      <TableCell>
                        <p className="font-medium leading-tight">
                          {offer.candidate_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {offer.job_title ?? "—"}
                        </p>
                      </TableCell>
                      <TableCell>
                        {offer.salary_offered
                          ? `QAR ${offer.salary_offered.toLocaleString()}`
                          : "—"}
                      </TableCell>
                      <TableCell>
                        <Badge variant="warning" className="capitalize">
                          {offer.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Group-by tables */}
      <section className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Applications by job</CardTitle>
            <CardDescription>Top 10 roles by inbound volume.</CardDescription>
          </CardHeader>
          <CardContent>
            <BarList items={data?.candidates_by_job ?? []} emptyLabel="No applications yet." />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Applications by department</CardTitle>
            <CardDescription>Where candidates are landing.</CardDescription>
          </CardHeader>
          <CardContent>
            <BarList items={data?.candidates_by_department ?? []} emptyLabel="No applications yet." />
          </CardContent>
        </Card>
      </section>

      <p className="mt-6 inline-flex items-center gap-2 text-xs text-muted-foreground">
        <History className="h-3.5 w-3.5" />
        Every HR action writes an entry to the audit log under scope=hr.
      </p>
    </HrShell>
  );
}

function PipelineFunnel({ stages }: { stages: FunnelStage[] }) {
  const max = Math.max(1, ...stages.map((s) => s.count));
  return (
    <ul className="space-y-2">
      {stages.map((stage) => {
        const pct = (stage.count / max) * 100;
        return (
          <li key={stage.status}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-sm font-medium">{stage.label}</span>
              <span className="text-sm tabular-nums text-muted-foreground">
                {stage.count}
              </span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-gradient-to-r from-pug-green-600 via-pug-green-500 to-pug-gold-500 transition-all"
                style={{ width: `${pct}%` }}
                aria-hidden
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function TrendChart({
  data,
  color,
}: {
  data: { month: string; count: number }[];
  color: string;
}) {
  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
        No data yet.
      </div>
    );
  }
  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id={`hr-fill-${color}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.4} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="month"
            stroke="hsl(var(--muted-foreground))"
            tickLine={false}
            axisLine={false}
            fontSize={11}
          />
          <YAxis
            stroke="hsl(var(--muted-foreground))"
            tickLine={false}
            axisLine={false}
            fontSize={11}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Area
            type="monotone"
            dataKey="count"
            stroke={color}
            strokeWidth={2}
            fill={`url(#hr-fill-${color})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function BarList({
  items,
  emptyLabel,
}: {
  items: { name: string; count: number }[];
  emptyLabel: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyLabel}</p>;
  }
  const max = Math.max(1, ...items.map((i) => i.count));
  return (
    <ul className="space-y-3">
      {items.map((item) => {
        const pct = (item.count / max) * 100;
        return (
          <li key={item.name}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="truncate text-sm font-medium">{item.name}</span>
              <span className="text-sm tabular-nums text-muted-foreground">
                {item.count}
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-gradient-to-r from-pug-gold-500 to-pug-green-500 transition-all"
                style={{ width: `${pct}%` }}
                aria-hidden
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function formatWhen(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
