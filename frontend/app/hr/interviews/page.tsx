"use client";

import * as React from "react";
import Link from "next/link";
import {
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  Filter,
  Loader2,
  Search,
  ThumbsDown,
  ThumbsUp,
  User as UserIcon,
} from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { InterviewActions } from "@/components/hr/interview-actions";
import { InterviewQuickUpdateDialog } from "@/components/hr/interview-quick-update-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type { InterviewListRow } from "@/lib/hr/types";
import { cn } from "@/lib/utils";


export default function HrInterviewsPage() {
  const [rows, setRows] = React.useState<InterviewListRow[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [tab, setTab] = React.useState<"all" | "upcoming" | "mine">("upcoming");
  const [statusFilter, setStatusFilter] = React.useState<string>("");
  const [query, setQuery] = React.useState("");
  // Phase 4 — clicking a candidate name opens the quick-update modal so
  // interviewers can record feedback + status without leaving this page.
  const [quickUpdateRow, setQuickUpdateRow] =
    React.useState<InterviewListRow | null>(null);

  React.useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, statusFilter]);

  async function refresh() {
    setRows(null);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (tab === "upcoming") params.set("upcoming_days", "30");
      if (statusFilter) params.set("status", statusFilter);
      const url =
        tab === "mine"
          ? "/hr/interviews/mine"
          : `/hr/interviews${params.toString() ? `?${params}` : ""}`;
      const list = await hrApi.get<InterviewListRow[]>(url);
      setRows(list);
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  const filtered = React.useMemo(() => {
    if (!rows) return [];
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) =>
      [
        r.candidate_name,
        r.job_title ?? "",
        r.interviewer_name ?? "",
        r.interviewer_email ?? "",
        r.round_name,
      ]
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }, [rows, query]);

  return (
    <HrShell
      title="Interviews"
      description="Schedule rounds, assign interviewers, and review feedback."
    >
      {/* Tabs + filters */}
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border/60 bg-background/60 p-4 backdrop-blur">
        <div className="flex items-center gap-1 rounded-md border border-border/60 p-0.5">
          {(["upcoming", "all", "mine"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setTab(value)}
              className={cn(
                "rounded px-3 py-1.5 text-xs font-medium capitalize transition-colors",
                tab === value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {value}
            </button>
          ))}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="iv-status" className="text-xs uppercase tracking-wider text-muted-foreground">
            <Filter className="mr-1 inline h-3 w-3" />
            Status
          </Label>
          <Select
            id="iv-status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-44"
          >
            <option value="">All statuses</option>
            <option value="scheduled">Scheduled</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="rescheduled">Rescheduled</option>
            <option value="no_show">No-show</option>
          </Select>
        </div>
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="iv-search" className="text-xs uppercase tracking-wider text-muted-foreground">
            Search
          </Label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="iv-search"
              placeholder="Candidate name, job title, interviewer, round…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>
        <Button type="button" variant="outline" onClick={refresh}>
          Refresh
        </Button>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {rows === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading interviews…
        </p>
      ) : filtered.length === 0 ? (
        <HrEmptyState
          icon={CalendarClock}
          title="No interviews yet"
          description={
            tab === "mine"
              ? "Once an HR user assigns you to a round, it'll appear here."
              : "Open a candidate's profile and use the Interviews panel to schedule the first round."
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Candidate</TableHead>
                <TableHead className="hidden md:table-cell">Round</TableHead>
                <TableHead className="hidden lg:table-cell">Interviewer</TableHead>
                <TableHead className="hidden md:table-cell">Mode</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden lg:table-cell">Outcome</TableHead>
                <TableHead className="w-20 text-right">Link</TableHead>
                <TableHead className="w-44 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <p className="font-medium tabular-nums">
                      {new Date(row.scheduled_at).toLocaleString()}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {row.duration_minutes} min
                    </p>
                  </TableCell>
                  <TableCell>
                    <button
                      type="button"
                      onClick={() => setQuickUpdateRow(row)}
                      className="text-left font-medium hover:text-primary"
                      aria-label={`Quick update for ${row.candidate_name}`}
                    >
                      {row.candidate_name}
                    </button>
                    {row.job_title && (
                      <p className="text-[11px] text-muted-foreground">
                        {row.job_title}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider">
                      R{row.round_number}
                    </span>{" "}
                    {row.round_name}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-xs">
                    {row.interviewer_name ? (
                      <span className="inline-flex items-center gap-1">
                        <UserIcon className="h-3 w-3 text-muted-foreground" />
                        {row.interviewer_name}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-xs text-muted-foreground">
                    {row.mode_label}
                  </TableCell>
                  <TableCell>
                    <StatusPill status={row.status} label={row.status_label} />
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    <OutcomePill
                      hasFeedback={row.has_feedback}
                      recommendation={row.latest_recommendation}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    {row.mode === "online" && row.location_or_link ? (
                      <a
                        href={row.location_or_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs font-medium text-primary"
                      >
                        Join
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <InterviewActions
                      interviewId={row.id}
                      status={row.status}
                      onChanged={refresh}
                      compact
                      scheduleMeta={{
                        scheduled_at: row.scheduled_at,
                        duration_minutes: row.duration_minutes,
                        mode: row.mode,
                        location_or_link: row.location_or_link,
                      }}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {quickUpdateRow && (
        <InterviewQuickUpdateDialog
          row={quickUpdateRow}
          onClose={() => setQuickUpdateRow(null)}
          onSaved={() => {
            setQuickUpdateRow(null);
            void refresh();
          }}
        />
      )}
    </HrShell>
  );
}


function StatusPill({
  status,
  label,
}: {
  status: string;
  label: string;
}) {
  let tone = "border-primary/30 bg-primary/10 text-primary";
  if (status === "completed")
    tone =
      "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  else if (status === "cancelled")
    tone = "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300";
  else if (status === "no_show")
    tone =
      "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300";
  else if (status === "rescheduled")
    tone =
      "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        tone
      )}
    >
      {label}
    </span>
  );
}


function OutcomePill({
  hasFeedback,
  recommendation,
}: {
  hasFeedback: boolean;
  recommendation: string | null;
}) {
  if (!hasFeedback)
    return <span className="text-xs text-muted-foreground">No feedback</span>;
  if (recommendation === "hire") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
        <ThumbsUp className="h-3 w-3" />
        Hire
      </span>
    );
  }
  if (recommendation === "no_hire") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700 dark:text-rose-300">
        <ThumbsDown className="h-3 w-3" />
        No hire
      </span>
    );
  }
  if (recommendation === "maybe") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 dark:text-amber-300">
        Maybe
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold text-foreground">
      <CheckCircle2 className="h-3 w-3" />
      Done
    </span>
  );
}
