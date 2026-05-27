"use client";

import * as React from "react";
import {
  CheckCircle2,
  Clock,
  Handshake,
  Loader2,
  PauseCircle,
  Send,
  Sparkles,
  TrendingUp,
  UserX,
  XCircle,
} from "lucide-react";

import { usePermission } from "@/components/auth/permission";
import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { OfferDetailDrawer } from "@/components/hr/offer-detail-drawer";
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
import { PERM_HR_OFFERS_CREATE } from "@/lib/hr/permissions";
import type { Offer, OfferStats } from "@/lib/hr/types";
import { cn } from "@/lib/utils";


const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  pending_approval: "Pending approval",
  approved: "Approved",
  sent: "Issued",
  accepted: "Accepted",
  declined: "Declined",
  withdrawn: "Withdrawn",
  joined: "Joined",
  not_joined: "Not joined",
};


export default function HrOffersPage() {
  const perms = usePermission();
  const [items, setItems] = React.useState<Offer[] | null>(null);
  const [stats, setStats] = React.useState<OfferStats | null>(null);
  const [statusFilter, setStatusFilter] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [openId, setOpenId] = React.useState<number | null>(null);

  React.useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function refresh() {
    setItems(null);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      const [list, summary] = await Promise.all([
        hrApi.get<Offer[]>(
          `/hr/offers${params.toString() ? `?${params}` : ""}`
        ),
        hrApi.get<OfferStats>("/hr/offers/stats"),
      ]);
      setItems(list);
      setStats(summary);
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  const filtered = React.useMemo(() => {
    if (!items) return [];
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((o) =>
      [
        o.candidate_name ?? "",
        o.job_title ?? "",
        o.department ?? "",
        o.offer_letter_number ?? "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(q),
    );
  }, [items, query]);

  return (
    <HrShell
      title="Offers"
      description="Full lifecycle — draft, approval, issue, candidate response, joining."
    >
      {/* Dashboard cards */}
      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Pending approval"
          value={stats?.pending_approval ?? 0}
          icon={Clock}
          tone="warning"
          onClick={() => setStatusFilter("pending_approval")}
        />
        <StatCard
          label="Approved"
          value={stats?.approved ?? 0}
          icon={Sparkles}
          tone="info"
          onClick={() => setStatusFilter("approved")}
        />
        <StatCard
          label="Issued"
          value={stats?.sent ?? 0}
          icon={Send}
          tone="info"
          onClick={() => setStatusFilter("sent")}
        />
        <StatCard
          label="Accepted"
          value={stats?.accepted ?? 0}
          icon={CheckCircle2}
          tone="success"
          onClick={() => setStatusFilter("accepted")}
        />
        <StatCard
          label="Joined"
          value={stats?.joined ?? 0}
          icon={TrendingUp}
          tone="success"
          onClick={() => setStatusFilter("joined")}
        />
        <StatCard
          label="Not joined"
          value={stats?.not_joined ?? 0}
          icon={UserX}
          tone="danger"
          onClick={() => setStatusFilter("not_joined")}
        />
        <StatCard
          label="Declined"
          value={stats?.declined ?? 0}
          icon={XCircle}
          tone="danger"
          onClick={() => setStatusFilter("declined")}
        />
        <StatCard
          label="Withdrawn"
          value={stats?.withdrawn ?? 0}
          icon={PauseCircle}
          tone="neutral"
          onClick={() => setStatusFilter("withdrawn")}
        />
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border/60 bg-card p-3">
        <div className="space-y-1">
          <Label
            htmlFor="of-status"
            className="text-xs uppercase tracking-wider text-muted-foreground"
          >
            Status
          </Label>
          <Select
            id="of-status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-44"
          >
            <option value="">All statuses</option>
            {Object.entries(STATUS_LABEL).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex-1 space-y-1">
          <Label
            htmlFor="of-q"
            className="text-xs uppercase tracking-wider text-muted-foreground"
          >
            Search
          </Label>
          <Input
            id="of-q"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Candidate, job, department, offer letter no."
          />
        </div>
        <Button variant="outline" size="sm" onClick={() => void refresh()}>
          Refresh
        </Button>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-3 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {items === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
          Loading offers…
        </p>
      ) : filtered.length === 0 ? (
        <HrEmptyState
          icon={Handshake}
          title="No offers match the current filter"
          description={
            perms.has(PERM_HR_OFFERS_CREATE)
              ? "Create an offer from the candidate's detail page — only candidates with status 'Recommended for offer' or 'Selected' are eligible."
              : "Offers will appear here once HR drafts them."
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Candidate</TableHead>
                <TableHead>Job</TableHead>
                <TableHead className="hidden md:table-cell">Salary</TableHead>
                <TableHead className="hidden md:table-cell">Joining</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden lg:table-cell">Letter no.</TableHead>
                <TableHead className="hidden lg:table-cell">Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((o) => (
                <TableRow
                  key={o.id}
                  className="cursor-pointer"
                  onClick={() => setOpenId(o.id)}
                >
                  <TableCell>
                    <p className="font-medium">{o.candidate_name ?? "—"}</p>
                    {o.candidate_email && (
                      <p className="text-[11px] text-muted-foreground">
                        {o.candidate_email}
                      </p>
                    )}
                  </TableCell>
                  <TableCell>
                    {o.job_title ?? "—"}
                    {o.department && (
                      <p className="text-[11px] text-muted-foreground">
                        {o.department}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell tabular-nums">
                    {o.salary_offered != null
                      ? o.salary_offered.toLocaleString()
                      : "—"}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {o.joining_date ?? "—"}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={o.status} />
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-xs">
                    {o.offer_letter_number ?? "—"}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-xs text-muted-foreground">
                    {new Date(o.updated_at).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {openId !== null && (
        <OfferDetailDrawer
          offerId={openId}
          onClose={() => setOpenId(null)}
          onChanged={() => {
            void refresh();
          }}
        />
      )}
    </HrShell>
  );
}


// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------


type Tone = "neutral" | "success" | "warning" | "info" | "danger";


function StatCard({
  label,
  value,
  icon: Icon,
  tone,
  onClick,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  tone: Tone;
  onClick?: () => void;
}) {
  const toneClass = {
    neutral: "text-muted-foreground",
    success: "text-emerald-600 dark:text-emerald-400",
    warning: "text-amber-600 dark:text-amber-400",
    info: "text-primary",
    danger: "text-rose-600 dark:text-rose-400",
  }[tone];
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-3 rounded-xl border border-border/60 bg-card p-4 text-left transition hover:border-primary/60"
    >
      <Icon className={cn("h-5 w-5", toneClass)} />
      <div className="min-w-0 flex-1">
        <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        <p className="text-xl font-semibold tabular-nums">{value}</p>
      </div>
    </button>
  );
}


function StatusBadge({ status }: { status: string }) {
  const tone =
    {
      draft: "border-border/60 bg-muted/50 text-muted-foreground",
      pending_approval:
        "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
      approved: "border-primary/30 bg-primary/10 text-primary",
      sent: "border-indigo-500/30 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300",
      accepted:
        "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
      declined:
        "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
      withdrawn: "border-border/60 bg-muted/50 text-muted-foreground",
      joined:
        "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
      not_joined:
        "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
    }[status] ?? "border-border/60 bg-muted/50 text-muted-foreground";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        tone,
      )}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
