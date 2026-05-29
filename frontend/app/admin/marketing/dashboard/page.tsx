"use client";

import * as React from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BookOpen,
  ChevronRight,
  Clock,
  Download,
  ExternalLink,
  Eye,
  FileWarning,
  Info,
  Layers,
  Loader2,
  MonitorSmartphone,
  RefreshCw,
  Sparkles,
  Tag,
  Users,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AdminShell } from "@/components/admin/admin-shell";
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
import { adminApi, AdminApiError } from "@/lib/admin/api";
import type {
  DashboardPeriod,
  MarketingDashboard,
  ReconcileCountersResult,
} from "@/lib/admin/marketing-types";
import { cn } from "@/lib/utils";


const PERIODS: Array<{ key: DashboardPeriod; label: string }> = [
  { key: "7d", label: "Last 7 days" },
  { key: "30d", label: "Last 30 days" },
  { key: "90d", label: "Last 90 days" },
  { key: "all", label: "All time" },
];


// Brand-aligned palette for the device donut + bar charts.
const COLORS = {
  brandGreen: "hsl(145 45% 30%)",
  brandGreenLight: "hsl(145 45% 55%)",
  brandGold: "hsl(36 45% 55%)",
  brandGoldDark: "hsl(36 45% 38%)",
  muted: "hsl(220 9% 46%)",
};


const DEVICE_COLORS: Record<string, string> = {
  desktop: COLORS.brandGreen,
  mobile: COLORS.brandGold,
  tablet: COLORS.brandGreenLight,
  unknown: COLORS.muted,
};


export default function MarketingDashboardPage() {
  const [period, setPeriod] = React.useState<DashboardPeriod>("30d");
  const [data, setData] = React.useState<MarketingDashboard | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [reconciling, setReconciling] = React.useState(false);
  const [reconcileMessage, setReconcileMessage] = React.useState<string | null>(
    null
  );

  const load = React.useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const res = await adminApi.get<MarketingDashboard>(
          `/admin/marketing/dashboard?period=${period}`
        );
        if (signal?.aborted) return;
        setData(res);
      } catch (err) {
        if (signal?.aborted) return;
        setError((err as AdminApiError).message);
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [period]
  );

  React.useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function reconcile() {
    setReconciling(true);
    setReconcileMessage(null);
    try {
      const res = await adminApi.post<ReconcileCountersResult>(
        "/admin/marketing/catalogues/reconcile-counters"
      );
      if (res.catalogues_updated === 0) {
        setReconcileMessage(
          `Already in sync — inspected ${res.catalogues_inspected} catalogue(s), nothing to fix.`
        );
      } else {
        setReconcileMessage(
          `Resynced ${res.catalogues_updated} catalogue(s). View total: ${res.total_view_count_before} → ${res.total_view_count_after}.`
        );
      }
      void load();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setReconciling(false);
    }
  }

  const deviceData = React.useMemo(() => {
    if (!data) return [];
    return Object.entries(data.by_device)
      .map(([device, count]) => ({
        device,
        count,
        color: DEVICE_COLORS[device] ?? COLORS.muted,
      }))
      .sort((a, b) => b.count - a.count);
  }, [data]);

  const totalDeviceViews = deviceData.reduce((sum, d) => sum + d.count, 0);

  return (
    <AdminShell
      title="Marketing dashboard"
      description="Engagement, downloads and processing health for every published catalogue."
      actions={
        <div className="flex items-center gap-2">
          <div className="hidden gap-1 rounded-lg border border-border/60 bg-background/60 p-0.5 sm:flex">
            {PERIODS.map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => setPeriod(p.key)}
                className={cn(
                  "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  period === p.key
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void load()}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            <span className="hidden sm:inline">Refresh</span>
          </Button>
        </div>
      }
    >
      {error && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {/* Mobile period selector */}
      <div className="mb-4 flex gap-1 overflow-x-auto rounded-lg border border-border/60 bg-background/60 p-0.5 sm:hidden">
        {PERIODS.map((p) => (
          <button
            key={p.key}
            type="button"
            onClick={() => setPeriod(p.key)}
            className={cn(
              "whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              period === p.key
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground"
            )}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* KPI grid */}
      <section className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
        <Kpi
          label="Total views"
          sublabel={data?.period_label ?? "Loading…"}
          value={data?.kpis.total_views_period}
          icon={Eye}
          tone="green"
          loading={!data}
          footer={
            data
              ? `${data.kpis.total_views_all_time.toLocaleString()} all-time`
              : undefined
          }
        />
        <Kpi
          label="Unique sessions"
          sublabel={data?.period_label ?? ""}
          value={data?.kpis.unique_sessions_period}
          icon={Users}
          tone="gold"
          loading={!data}
        />
        <Kpi
          label="Avg. session length"
          sublabel="In-viewer dwell time"
          value={
            data
              ? formatDuration(data.kpis.avg_session_duration_sec)
              : undefined
          }
          rawValue
          icon={Clock}
          tone="green"
          loading={!data}
        />
        <Kpi
          label="PDF downloads"
          sublabel="All time"
          value={data?.kpis.total_downloads_all_time}
          icon={Download}
          tone="gold"
          loading={!data}
        />
        <Kpi
          label="Active campaigns"
          sublabel={
            data
              ? `${data.kpis.campaigns_total} total`
              : ""
          }
          value={data?.kpis.campaigns_active}
          icon={Tag}
          tone="green"
          loading={!data}
        />
        <Kpi
          label="Ready catalogues"
          sublabel={
            data
              ? `${data.kpis.catalogues_total} total · ${data.kpis.total_pages.toLocaleString()} pages`
              : ""
          }
          value={data?.kpis.catalogues_ready}
          icon={BookOpen}
          tone="green"
          loading={!data}
        />
        <Kpi
          label="Processing"
          sublabel="Render in progress"
          value={data?.kpis.catalogues_processing}
          icon={Layers}
          tone="muted"
          loading={!data}
        />
        <Kpi
          label="Failed renders"
          sublabel="Need re-process"
          value={data?.kpis.catalogues_failed}
          icon={FileWarning}
          tone={
            (data?.kpis.catalogues_failed ?? 0) > 0 ? "rose" : "muted"
          }
          loading={!data}
        />
      </section>

      {/* Charts row */}
      <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-start justify-between gap-2">
              <div>
                <CardTitle className="text-base">Views over time</CardTitle>
                <CardDescription>
                  Daily catalogue opens — the engagement pulse. One event
                  = one viewer arriving at a catalogue page.
                </CardDescription>
              </div>
              <span className="rounded-full border border-border/60 bg-background/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                {data?.period_label ?? ""}
              </span>
            </div>
          </CardHeader>
          <CardContent className="px-2">
            {data ? (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart
                  data={data.views_over_time}
                  margin={{ top: 5, right: 10, left: -10, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="viewsFill" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="0%"
                        stopColor={COLORS.brandGreen}
                        stopOpacity={0.45}
                      />
                      <stop
                        offset="95%"
                        stopColor={COLORS.brandGreen}
                        stopOpacity={0.02}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="hsl(220 9% 88%)"
                  />
                  <XAxis
                    dataKey="date"
                    tickFormatter={shortDate}
                    fontSize={11}
                    stroke="hsl(220 9% 60%)"
                  />
                  <YAxis
                    fontSize={11}
                    stroke="hsl(220 9% 60%)"
                    allowDecimals={false}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="views"
                    stroke={COLORS.brandGreen}
                    strokeWidth={2}
                    fill="url(#viewsFill)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <ChartSkeleton />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Device mix</CardTitle>
            <CardDescription>
              Where viewers are opening the catalogue.
            </CardDescription>
          </CardHeader>
          <CardContent className="px-2">
            {data && totalDeviceViews > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={deviceData}
                      dataKey="count"
                      nameKey="device"
                      innerRadius={48}
                      outerRadius={75}
                      strokeWidth={1}
                    >
                      {deviceData.map((entry) => (
                        <Cell key={entry.device} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip content={<DeviceTooltip total={totalDeviceViews} />} />
                  </PieChart>
                </ResponsiveContainer>
                <ul className="mt-1 space-y-1 px-2">
                  {deviceData.map((d) => (
                    <li
                      key={d.device}
                      className="flex items-center justify-between gap-2 text-[11px]"
                    >
                      <span className="flex items-center gap-1.5">
                        <span
                          className="inline-block h-2.5 w-2.5 rounded-sm"
                          style={{ backgroundColor: d.color }}
                        />
                        <span className="capitalize text-muted-foreground">
                          {d.device}
                        </span>
                      </span>
                      <span className="font-mono">
                        {d.count.toLocaleString()}
                        <span className="ml-1 text-muted-foreground/70">
                          ({Math.round((d.count / totalDeviceViews) * 100)}%)
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            ) : data ? (
              <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
                <MonitorSmartphone className="mr-2 h-4 w-4" />
                No views in this period.
              </div>
            ) : (
              <ChartSkeleton h={200} />
            )}
          </CardContent>
        </Card>
      </section>

      {/* Top catalogues + Top campaigns */}
      <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Top catalogues</CardTitle>
              <CardDescription>By views in this period.</CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link href="/admin/marketing/catalogues">
                All catalogues
                <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {data ? (
              data.top_catalogues.length === 0 ? (
                <EmptyRow label="No catalogue activity in this period." />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Title</TableHead>
                      <TableHead className="hidden md:table-cell">
                        Campaign
                      </TableHead>
                      <TableHead className="w-20 text-right">Views</TableHead>
                      <TableHead className="w-20 text-right">DLs</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.top_catalogues.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell className="font-medium">
                          <Link
                            href={`/offers/catalogues/${c.slug}`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 hover:text-primary"
                          >
                            <span className="truncate">{c.title}</span>
                            <ExternalLink className="h-3 w-3 text-muted-foreground" />
                          </Link>
                          <p className="font-mono text-[10px] text-muted-foreground">
                            {c.slug}
                          </p>
                        </TableCell>
                        <TableCell className="hidden text-xs text-muted-foreground md:table-cell">
                          {c.campaign_title ?? "—"}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {c.views.toLocaleString()}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm text-muted-foreground">
                          {c.downloads.toLocaleString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )
            ) : (
              <RowSkeleton />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Top campaigns</CardTitle>
              <CardDescription>
                Aggregated views across each campaign&apos;s catalogues.
              </CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link href="/admin/marketing/campaigns">
                All campaigns
                <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="px-2">
            {data ? (
              data.top_campaigns.length === 0 ? (
                <EmptyRow label="No campaign activity in this period." />
              ) : (
                <ResponsiveContainer width="100%" height={Math.max(180, data.top_campaigns.length * 38)}>
                  <BarChart
                    data={data.top_campaigns}
                    layout="vertical"
                    margin={{ top: 5, right: 24, left: 10, bottom: 5 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="hsl(220 9% 88%)"
                      horizontal={false}
                    />
                    <XAxis
                      type="number"
                      fontSize={11}
                      stroke="hsl(220 9% 60%)"
                      allowDecimals={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="title"
                      fontSize={11}
                      stroke="hsl(220 9% 60%)"
                      width={140}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar
                      dataKey="views"
                      fill={COLORS.brandGold}
                      radius={[0, 4, 4, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              )
            ) : (
              <ChartSkeleton />
            )}
          </CardContent>
        </Card>
      </section>

      {/* Recent activity + explainer */}
      <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Recent activity</CardTitle>
            <CardDescription>
              The newest catalogue opens, freshest first.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {data ? (
              data.recent_views.length === 0 ? (
                <EmptyRow label="No views yet." />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>When</TableHead>
                      <TableHead>Catalogue</TableHead>
                      <TableHead className="hidden md:table-cell w-20">
                        Device
                      </TableHead>
                      <TableHead className="w-24 text-right">
                        Duration
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.recent_views.map((r, i) => (
                      <TableRow key={`${r.catalogue_id}-${r.viewed_at}-${i}`}>
                        <TableCell className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">
                          {new Date(r.viewed_at).toLocaleString()}
                        </TableCell>
                        <TableCell className="text-sm">
                          <Link
                            href={`/offers/catalogues/${r.catalogue_slug}`}
                            target="_blank"
                            rel="noreferrer"
                            className="font-medium hover:text-primary"
                          >
                            {r.catalogue_title}
                          </Link>
                        </TableCell>
                        <TableCell className="hidden text-xs capitalize text-muted-foreground md:table-cell">
                          {r.device ?? "—"}
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs text-muted-foreground">
                          {r.duration_seconds != null
                            ? formatDuration(r.duration_seconds)
                            : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )
            ) : (
              <RowSkeleton rows={6} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Info className="h-4 w-4" />
              How counts are calculated
            </CardTitle>
            <CardDescription>
              Why the catalogue list and a catalogue&apos;s detail can show
              different numbers.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Explainer
              icon={Eye}
              title={`Table column "Views"`}
              body={
                <>
                  Reads <code className="rounded bg-muted px-1 text-[11px]">catalogue.view_count</code>{" "}
                  — a denormalised integer on the catalogue row that is bumped{" "}
                  <code className="rounded bg-muted px-1 text-[11px]">+1</code>{" "}
                  each time the public <code className="rounded bg-muted px-1 text-[11px]">/view</code>{" "}
                  beacon fires.
                </>
              }
            />
            <Explainer
              icon={Activity}
              title={`Detail "Total views"`}
              body={
                <>
                  Comes from{" "}
                  <code className="rounded bg-muted px-1 text-[11px]">
                    COUNT(catalogue_view_events)
                  </code>{" "}
                  — the row-level event log. The viewer fires the beacon{" "}
                  <strong>twice</strong> per session (on open + on close)
                  so each visit normally adds 2 events.
                </>
              }
            />
            <Explainer
              icon={AlertTriangle}
              title="Why they can drift"
              body={
                <>
                  Both numbers are written inside the same transaction, so
                  in normal traffic they match. They drift when events are
                  loaded out-of-band — test fixtures, manual SQL, a
                  hot-fix migration. The dashboard above uses the events
                  table because it&apos;s the authoritative source.
                </>
              }
            />
            <div className="rounded-lg border border-border/60 bg-muted/40 p-3">
              <p className="text-xs text-muted-foreground">
                Resync the table&apos;s <code>view_count</code> from the
                events table. Safe to run any time.
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={reconcile}
                disabled={reconciling}
                className="mt-2"
              >
                {reconciling ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" />
                )}
                Reconcile counters
              </Button>
              {reconcileMessage && (
                <p className="mt-2 text-[11px] text-emerald-700 dark:text-emerald-300">
                  <Sparkles className="mr-1 inline h-3 w-3" />
                  {reconcileMessage}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </section>

      {data && (
        <p className="mt-6 text-right text-[11px] text-muted-foreground">
          Generated {new Date(data.generated_at).toLocaleString()}
        </p>
      )}
    </AdminShell>
  );
}


// ---------------------------------------------------------------------------
// Small UI primitives
// ---------------------------------------------------------------------------


function Kpi({
  label,
  sublabel,
  value,
  icon: Icon,
  tone,
  loading,
  footer,
  rawValue,
}: {
  label: string;
  sublabel?: string;
  value: number | string | undefined;
  icon: React.ComponentType<{ className?: string }>;
  tone: "green" | "gold" | "rose" | "muted";
  loading?: boolean;
  footer?: string;
  rawValue?: boolean;
}) {
  const accent = {
    green: "from-pug-green-500 to-pug-green-700",
    gold: "from-pug-gold-500 to-pug-gold-700",
    rose: "from-rose-500 to-rose-700",
    muted: "from-zinc-500 to-zinc-700",
  }[tone];
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div
            className={cn(
              "inline-flex h-8 w-8 items-center justify-center rounded-md bg-gradient-to-br text-white shadow-sm",
              accent
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
        </div>
        <p className="mt-3 text-2xl font-semibold tracking-tight">
          {loading ? (
            <span className="inline-block h-7 w-12 animate-pulse rounded bg-muted" />
          ) : value === undefined || value === null ? (
            "—"
          ) : rawValue ? (
            value
          ) : (
            Number(value).toLocaleString()
          )}
        </p>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        {sublabel && (
          <p className="text-[10px] text-muted-foreground/80">{sublabel}</p>
        )}
        {footer && (
          <p className="mt-2 border-t border-border/40 pt-2 text-[10px] text-muted-foreground">
            {footer}
          </p>
        )}
      </CardContent>
    </Card>
  );
}


function Explainer({
  icon: Icon,
  title,
  body,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: React.ReactNode;
}) {
  return (
    <div className="flex gap-2">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0 leading-snug">
        <p className="text-[12px] font-semibold">{title}</p>
        <p className="text-[11px] text-muted-foreground">{body}</p>
      </div>
    </div>
  );
}


// Recharts tooltip — themed to match the rest of the admin.
function ChartTooltip(props: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number; payload?: { date?: string } }>;
  label?: string | number;
}) {
  const { active, payload, label } = props;
  if (!active || !payload || payload.length === 0) return null;
  const value = payload[0].value ?? 0;
  return (
    <div className="rounded-lg border border-border/70 bg-background/95 px-2 py-1.5 text-xs shadow-md backdrop-blur">
      {label && (
        <p className="font-mono text-[10px] text-muted-foreground">
          {typeof label === "string" ? shortDate(label) : label}
        </p>
      )}
      <p className="font-medium">{Number(value).toLocaleString()} view{value === 1 ? "" : "s"}</p>
    </div>
  );
}


function DeviceTooltip(props: {
  active?: boolean;
  payload?: Array<{ payload?: { device?: string; count?: number } }>;
  total: number;
}) {
  const { active, payload, total } = props;
  if (!active || !payload || payload.length === 0) return null;
  const entry = payload[0].payload;
  if (!entry) return null;
  const pct = Math.round(((entry.count ?? 0) / Math.max(1, total)) * 100);
  return (
    <div className="rounded-lg border border-border/70 bg-background/95 px-2 py-1.5 text-xs shadow-md backdrop-blur">
      <p className="capitalize">{entry.device}</p>
      <p className="font-mono text-[11px] text-muted-foreground">
        {entry.count?.toLocaleString()} · {pct}%
      </p>
    </div>
  );
}


function ChartSkeleton({ h = 240 }: { h?: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-md bg-muted/30"
      style={{ height: h }}
    >
      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
    </div>
  );
}


function RowSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <ul className="divide-y divide-border/60">
      {Array.from({ length: rows }).map((_, i) => (
        <li key={i} className="flex items-center gap-3 px-4 py-3">
          <div className="h-3 flex-1 animate-pulse rounded bg-muted" />
          <div className="h-3 w-12 animate-pulse rounded bg-muted" />
        </li>
      ))}
    </ul>
  );
}


function EmptyRow({ label }: { label: string }) {
  return (
    <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
      <BarChart3 className="mr-2 h-4 w-4" />
      {label}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function shortDate(input: string | number): string {
  const d = typeof input === "string" ? new Date(input) : new Date(input);
  if (Number.isNaN(d.getTime())) return String(input);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}


function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return s ? `${m}m ${s}s` : `${m}m`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return remM ? `${h}h ${remM}m` : `${h}h`;
}
