"use client";

import * as React from "react";
import Link from "next/link";
import {
  Building2,
  History,
  Inbox,
  LayoutDashboard,
  Mail,
  Megaphone,
  MessageSquareQuote,
  Sparkles,
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
import type { DashboardSummary } from "@/lib/admin/types";
import { cn } from "@/lib/utils";

const STAT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  companies: Building2,
  news: Megaphone,
  leadership: MessageSquareQuote,
  hero_slides: Sparkles,
  contact_unread: Inbox,
  subscribers: Mail,
};

const STAT_ACCENTS: Record<string, string> = {
  companies: "from-pug-green-500 to-pug-green-700",
  news: "from-pug-gold-500 to-pug-gold-700",
  leadership: "from-pug-green-600 to-pug-gold-500",
  hero_slides: "from-pug-gold-400 to-pug-green-500",
  contact_unread: "from-rose-500 to-pug-gold-500",
  subscribers: "from-pug-green-500 to-pug-gold-600",
};

export default function AdminDashboardPage() {
  const [data, setData] = React.useState<DashboardSummary | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    adminApi
      .get<DashboardSummary>("/admin/cms/dashboard")
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err: AdminApiError) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AdminShell
      title="Dashboard"
      description="Overview of website content, engagement, and audit activity."
    >
      {error && (
        <div
          role="alert"
          className="mb-6 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {/* Stat cards */}
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        {data
          ? data.stats.map((stat) => {
              const Icon = STAT_ICONS[stat.key] ?? LayoutDashboard;
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
          : Array.from({ length: 6 }).map((_, i) => (
              <Card key={i} className="animate-pulse">
                <CardContent className="p-5">
                  <div className="h-9 w-9 rounded-lg bg-muted" />
                  <div className="mt-3 h-7 w-16 rounded bg-muted" />
                  <div className="mt-2 h-3 w-24 rounded bg-muted" />
                </CardContent>
              </Card>
            ))}
      </section>

      {/* Charts */}
      <section className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Contact messages per month</CardTitle>
            <CardDescription>Inbound submissions over time.</CardDescription>
          </CardHeader>
          <CardContent>
            <TrendChart
              data={data?.contact_messages_per_month ?? []}
              color="hsl(36 45% 55%)"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">News published per month</CardTitle>
            <CardDescription>Editorial output cadence.</CardDescription>
          </CardHeader>
          <CardContent>
            <TrendChart
              data={data?.news_per_month ?? []}
              color="hsl(145 45% 30%)"
            />
          </CardContent>
        </Card>
      </section>

      {/* Tables */}
      <section className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Latest contact messages</CardTitle>
              <CardDescription>Recent inbox activity.</CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link href="/admin/inbox">Open inbox</Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>From</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead className="w-24">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.latest_contact_messages ?? []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-muted-foreground">
                      No messages yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  (data?.latest_contact_messages ?? []).map((msg) => (
                    <TableRow key={msg.id}>
                      <TableCell>
                        <p className="font-medium leading-tight">{msg.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {msg.email}
                        </p>
                      </TableCell>
                      <TableCell className="max-w-[16rem] truncate">
                        {msg.subject ?? "—"}
                      </TableCell>
                      <TableCell>
                        {msg.is_replied ? (
                          <span className="text-xs text-emerald-700 dark:text-emerald-300">
                            Replied
                          </span>
                        ) : msg.is_read ? (
                          <span className="text-xs text-muted-foreground">
                            Read
                          </span>
                        ) : (
                          <span className="text-xs font-semibold text-primary">
                            New
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Latest news</CardTitle>
              <CardDescription>Most recently published.</CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link href="/admin/news">Open news</Link>
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="w-32">Published</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.latest_news ?? []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-muted-foreground">
                      No news yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  (data?.latest_news ?? []).map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">
                        {item.title}
                      </TableCell>
                      <TableCell className="capitalize text-muted-foreground">
                        {item.category}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(item.published_at).toLocaleDateString()}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </section>

      <p className="mt-6 inline-flex items-center gap-2 text-xs text-muted-foreground">
        <History className="h-3.5 w-3.5" />
        Every CMS create / update / delete writes an entry to the audit log.
      </p>
    </AdminShell>
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
            <linearGradient id={`fill-${color}`} x1="0" y1="0" x2="0" y2="1">
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
            fill={`url(#fill-${color})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
