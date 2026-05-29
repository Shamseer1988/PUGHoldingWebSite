"use client";

/**
 * HR recruitment analytics page (Phase C-3).
 *
 * Distinct from the operational dashboard at ``/hr``:
 *
 *   - ``/hr`` answers "what needs my attention right now?" with
 *     12 KPI cards + pending interview / offer tables.
 *   - ``/hr/analytics`` answers "how is recruiting performing
 *     across the trailing N days?" with hiring velocity (daily
 *     line chart), funnel conversion (stacked stage bars), source
 *     ROI (per-source breakdown), and time-to-hire averages.
 *
 * Data plane: ``useRecruitmentAnalytics`` (Phase B-4 React Query
 * hook) hits ``GET /hr/analytics/recruitment?window_days=...``.
 * Window picker exposes 30 / 60 / 90 days — the backend caps at
 * 365 if a deeper view is needed later.
 */
import * as React from "react";
import {
  CalendarRange,
  Loader2,
  TrendingUp,
  Users,
  Workflow,
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

import { HrShell } from "@/components/hr/hr-shell";
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
import { useRecruitmentAnalytics } from "@/lib/hr/queries";
import type {
  FunnelStage,
  RecruitmentAnalytics,
  SourceMetric,
} from "@/lib/hr/types";
import { cn } from "@/lib/utils";


const WINDOW_OPTIONS = [30, 60, 90] as const;
type WindowDays = (typeof WINDOW_OPTIONS)[number];

const SOURCE_LABELS: Record<string, string> = {
  public_form: "Public form",
  manual_upload: "Manual upload",
  bulk_upload: "Bulk upload",
  unknown: "Unknown",
};

function sourceLabel(key: string): string {
  return SOURCE_LABELS[key] ?? key;
}

function formatPercent(numerator: number, denominator: number): string {
  if (denominator === 0) return "—";
  return `${Math.round((numerator / denominator) * 100)}%`;
}


export default function HrAnalyticsPage() {
  const [windowDays, setWindowDays] = React.useState<WindowDays>(90);
  const query = useRecruitmentAnalytics(windowDays);

  return (
    <HrShell
      title="Recruitment analytics"
      description="Velocity, conversion, and source performance for the trailing window."
      actions={<WindowPicker value={windowDays} onChange={setWindowDays} />}
    >
      {query.isPending ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading analytics…
        </p>
      ) : query.isError ? (
        <div
          role="alert"
          className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {query.error.message}
        </div>
      ) : query.data ? (
        <Body data={query.data} />
      ) : null}
    </HrShell>
  );
}


function WindowPicker({
  value,
  onChange,
}: {
  value: WindowDays;
  onChange: (v: WindowDays) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Lookback window"
      className="inline-flex rounded-full border border-border/60 bg-background/60 p-0.5"
    >
      {WINDOW_OPTIONS.map((days) => (
        <Button
          key={days}
          type="button"
          role="radio"
          aria-checked={days === value}
          variant={days === value ? "default" : "ghost"}
          size="sm"
          onClick={() => onChange(days)}
          className={cn(
            "h-7 rounded-full px-3 text-xs font-medium",
            days === value && "shadow-sm"
          )}
        >
          {days}d
        </Button>
      ))}
    </div>
  );
}


function Body({ data }: { data: RecruitmentAnalytics }) {
  const totalApplications = data.daily_applications.reduce(
    (sum, d) => sum + d.count,
    0
  );
  const dailyAvg =
    data.daily_applications.length === 0
      ? 0
      : totalApplications / data.daily_applications.length;
  const joinedCount = data.time_to_hire.sample_size;

  return (
    <div className="space-y-6">
      <KpiRow
        totalApplications={totalApplications}
        dailyAvg={dailyAvg}
        joinedCount={joinedCount}
        avgTimeToHire={data.time_to_hire.overall_avg_days}
        windowDays={data.window_days}
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <TrendingUp className="h-4 w-4 text-pug-gold-500" />
            Daily applications
          </CardTitle>
          <CardDescription>
            Applications received per day across the last {data.window_days}{" "}
            days.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DailyApplicationsChart points={data.daily_applications} />
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Workflow className="h-4 w-4 text-pug-gold-500" />
              Funnel conversion
            </CardTitle>
            <CardDescription>
              Active applications by current pipeline stage.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FunnelList stages={data.funnel_conversion} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4 text-pug-gold-500" />
              Source performance
            </CardTitle>
            <CardDescription>
              Cumulative drop-off per intake source — shortlist, offer, joined.
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <SourceTable sources={data.source_breakdown} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <CalendarRange className="h-4 w-4 text-pug-gold-500" />
            Time to hire
          </CardTitle>
          <CardDescription>
            Average days from application to ``joined``, per source. Based on
            applications that reached ``joined`` inside the window.
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <TimeToHireTable data={data.time_to_hire} />
        </CardContent>
      </Card>
    </div>
  );
}


function KpiRow({
  totalApplications,
  dailyAvg,
  joinedCount,
  avgTimeToHire,
  windowDays,
}: {
  totalApplications: number;
  dailyAvg: number;
  joinedCount: number;
  avgTimeToHire: number | null;
  windowDays: number;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Kpi
        label="Total applications"
        value={totalApplications.toLocaleString()}
        sub={`Last ${windowDays} days`}
      />
      <Kpi
        label="Daily average"
        value={dailyAvg.toFixed(1)}
        sub="Applications / day"
      />
      <Kpi
        label="Joined"
        value={joinedCount.toLocaleString()}
        sub={`${formatPercent(joinedCount, totalApplications)} of total`}
      />
      <Kpi
        label="Avg time-to-hire"
        value={
          avgTimeToHire === null
            ? "—"
            : `${avgTimeToHire.toFixed(1)}d`
        }
        sub="Application → joined"
      />
    </div>
  );
}


function Kpi({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          {label}
        </p>
        <p className="mt-2 text-3xl font-semibold leading-none tracking-tight">
          {value}
        </p>
        {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}


function DailyApplicationsChart({
  points,
}: {
  points: RecruitmentAnalytics["daily_applications"];
}) {
  // Recharts wants string-keyed objects; the payload already matches.
  // The x-axis shows MM-DD to keep the ticks readable across 30-90 days.
  const formatted = React.useMemo(
    () =>
      points.map((p) => ({
        ...p,
        tick: p.date.slice(5), // MM-DD
      })),
    [points]
  );
  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={formatted} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="dailyAppsGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#cfa646" stopOpacity={0.5} />
            <stop offset="100%" stopColor="#cfa646" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border/50" />
        <XAxis
          dataKey="tick"
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 11 }}
          interval="preserveStartEnd"
          minTickGap={24}
        />
        <YAxis
          allowDecimals={false}
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 11 }}
          width={32}
        />
        <Tooltip
          contentStyle={{
            background: "hsl(var(--background))",
            border: "1px solid hsl(var(--border))",
            borderRadius: 8,
            fontSize: 12,
          }}
          labelFormatter={(_, items) =>
            items[0]?.payload?.date ?? ""
          }
          formatter={(value: number) => [
            `${value} application${value === 1 ? "" : "s"}`,
            "",
          ]}
        />
        <Area
          type="monotone"
          dataKey="count"
          stroke="#cfa646"
          strokeWidth={2}
          fill="url(#dailyAppsGradient)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}


function FunnelList({ stages }: { stages: FunnelStage[] }) {
  const max = stages.reduce((m, s) => Math.max(m, s.count), 0);
  return (
    <ul className="space-y-2">
      {stages.map((stage) => {
        const pct = max === 0 ? 0 : Math.round((stage.count / max) * 100);
        return (
          <li
            key={stage.status}
            className="grid grid-cols-[minmax(0,1fr)_60px] items-center gap-3 text-sm"
          >
            <div>
              <p className="text-xs font-medium text-foreground">
                {stage.label}
              </p>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-pug-gold-500 to-pug-gold-300"
                  style={{ width: `${Math.max(pct, stage.count > 0 ? 4 : 0)}%` }}
                />
              </div>
            </div>
            <span className="text-right text-sm tabular-nums">
              {stage.count}
            </span>
          </li>
        );
      })}
    </ul>
  );
}


function SourceTable({ sources }: { sources: SourceMetric[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Source</TableHead>
          <TableHead className="text-right">Total</TableHead>
          <TableHead className="text-right">Shortlist</TableHead>
          <TableHead className="text-right">Offer</TableHead>
          <TableHead className="text-right">Joined</TableHead>
          <TableHead className="text-right">Hire rate</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sources.map((s) => (
          <TableRow key={s.source}>
            <TableCell className="font-medium">{sourceLabel(s.source)}</TableCell>
            <TableCell className="text-right tabular-nums">{s.total}</TableCell>
            <TableCell className="text-right tabular-nums">
              {s.shortlisted}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {s.offers_issued}
            </TableCell>
            <TableCell className="text-right tabular-nums">{s.joined}</TableCell>
            <TableCell className="text-right tabular-nums text-muted-foreground">
              {formatPercent(s.joined, s.total)}
            </TableCell>
          </TableRow>
        ))}
        {sources.length === 0 && (
          <TableRow>
            <TableCell
              colSpan={6}
              className="text-center text-sm text-muted-foreground"
            >
              No applications in the selected window.
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}


function TimeToHireTable({
  data,
}: {
  data: RecruitmentAnalytics["time_to_hire"];
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Source</TableHead>
          <TableHead className="text-right">Sample size</TableHead>
          <TableHead className="text-right">Avg days</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.by_source.map((entry) => (
          <TableRow key={entry.source}>
            <TableCell className="font-medium">
              {sourceLabel(entry.source)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {entry.sample_size}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {entry.avg_days === null ? "—" : `${entry.avg_days.toFixed(1)}d`}
            </TableCell>
          </TableRow>
        ))}
        <TableRow className="border-t-2">
          <TableCell className="font-semibold">All sources</TableCell>
          <TableCell className="text-right font-semibold tabular-nums">
            {data.sample_size}
          </TableCell>
          <TableCell className="text-right font-semibold tabular-nums">
            {data.overall_avg_days === null
              ? "—"
              : `${data.overall_avg_days.toFixed(1)}d`}
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  );
}
