"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Loader2, UserCheck, UserX, Users } from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { KpiCard } from "@/components/hr/kpi-card";
import { MarkJoinedDialog } from "@/components/hr/mark-joined-dialog";
import { MarkNotJoinedDialog } from "@/components/hr/mark-not-joined-dialog";
import { OfferDetailDrawer } from "@/components/hr/offer-detail-drawer";
import { OnboardingTable } from "@/components/hr/onboarding-table";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type { Offer } from "@/lib/hr/types";

const ONBOARDING_STATUSES = ["accepted", "joined", "not_joined"];

type FilterKey = "all" | "awaiting" | "joined" | "not_joined";
const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "awaiting", label: "Awaiting join" },
  { key: "joined", label: "Joined" },
  { key: "not_joined", label: "Not joined" },
];

export default function HrOnboardingPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const filter = (searchParams.get("filter") as FilterKey) || "all";
  const window30d = searchParams.get("window") === "30d";

  const [offers, setOffers] = React.useState<Offer[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [joinTarget, setJoinTarget] = React.useState<Offer | null>(null);
  const [notJoinTarget, setNotJoinTarget] = React.useState<Offer | null>(null);
  const [openId, setOpenId] = React.useState<number | null>(null);

  const refresh = React.useCallback(async () => {
    setOffers(null);
    setError(null);
    try {
      const all = await hrApi.get<Offer[]>("/hr/offers?limit=500");
      setOffers(all.filter((o) => ONBOARDING_STATUSES.includes(o.status)));
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const base = offers ?? [];

  // KPI strip metrics computed over all onboarding offers.
  const awaitingCount = base.filter((o) => o.status === "accepted").length;
  const joinedThisMonth = base.filter(
    (o) => o.joining_status === "joined" && o.joined_at && isThisMonth(o.joined_at),
  ).length;
  const noShowRate = noShowRate90d(base);

  // Visible rows after the active filter (+ optional 30-day window).
  const visible = React.useMemo(() => {
    let rows = base;
    if (filter === "awaiting") rows = rows.filter((o) => o.status === "accepted");
    else if (filter === "joined") rows = rows.filter((o) => o.status === "joined");
    else if (filter === "not_joined")
      rows = rows.filter((o) => o.status === "not_joined");
    if (window30d) {
      rows = rows.filter(
        (o) => o.status === "accepted" && withinDays(o.joining_date, 30),
      );
    }
    return rows;
  }, [base, filter, window30d]);

  function setFilter(key: FilterKey) {
    const params = new URLSearchParams(searchParams.toString());
    if (key === "all") params.delete("filter");
    else params.set("filter", key);
    params.delete("window");
    router.replace(params.toString() ? `${pathname}?${params}` : pathname, {
      scroll: false,
    });
  }

  return (
    <HrShell
      title="Onboarding"
      description="Accepted offers through to joining — mark joiners and capture no-shows."
    >
      {/* KPI strip */}
      <section className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard
          label="Accepted · awaiting join"
          value={awaitingCount}
          href="/hr/onboarding?filter=awaiting"
          icon={Users}
          tone="warning"
        />
        <KpiCard
          label="Joined this month"
          value={joinedThisMonth}
          href="/hr/onboarding?filter=joined"
          icon={UserCheck}
          tone="success"
        />
        <KpiCard
          label="No-show rate (90d)"
          value={noShowRate === null ? "—" : `${noShowRate}%`}
          href="/hr/onboarding?filter=not_joined"
          icon={UserX}
          tone="danger"
        />
      </section>

      {/* Filter chips */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        {FILTERS.map((f) => {
          const active = filter === f.key && !(f.key === "all" && window30d);
          return (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              aria-pressed={active}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                active
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border/60 bg-background/60 text-muted-foreground hover:text-foreground"
              }`}
            >
              {f.label}
            </button>
          );
        })}
        {window30d && (
          <span className="rounded-full border border-primary/40 bg-primary/10 px-2.5 py-1 text-xs text-primary">
            Joining within 30 days
          </span>
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="mb-3 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {offers === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
          Loading onboarding…
        </p>
      ) : visible.length === 0 ? (
        <HrEmptyState
          icon={UserCheck}
          title="Nothing here right now"
          description="Once a candidate accepts an offer they appear here until they join (or are marked a no-show)."
        />
      ) : (
        <OnboardingTable
          offers={visible}
          onMarkJoined={setJoinTarget}
          onMarkNotJoined={setNotJoinTarget}
          onOpen={(o) => setOpenId(o.id)}
        />
      )}

      {joinTarget && (
        <MarkJoinedDialog
          offerId={joinTarget.id}
          candidateName={joinTarget.candidate_name}
          joiningDate={joinTarget.joining_date}
          onClose={() => setJoinTarget(null)}
          onDone={() => {
            setJoinTarget(null);
            void refresh();
          }}
        />
      )}

      {notJoinTarget && (
        <MarkNotJoinedDialog
          offerId={notJoinTarget.id}
          candidateName={notJoinTarget.candidate_name}
          onClose={() => setNotJoinTarget(null)}
          onDone={() => {
            setNotJoinTarget(null);
            void refresh();
          }}
        />
      )}

      {openId !== null && (
        <OfferDetailDrawer
          offerId={openId}
          onClose={() => setOpenId(null)}
          onChanged={() => void refresh()}
        />
      )}
    </HrShell>
  );
}

function isThisMonth(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()
  );
}

function withinDays(date: string | null, days: number): boolean {
  if (!date) return false;
  const target = new Date(`${date}T00:00:00`);
  if (Number.isNaN(target.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = (target.getTime() - today.getTime()) / 86_400_000;
  return diff >= -1 && diff <= days;
}

/** No-show rate over offers that reached a terminal joining decision in
 *  the last 90 days (using updated_at as the decision proxy). */
function noShowRate90d(offers: Offer[]): number | null {
  const cutoff = Date.now() - 90 * 86_400_000;
  let joined = 0;
  let notJoined = 0;
  for (const o of offers) {
    const decidedAt = new Date(o.updated_at).getTime();
    if (Number.isNaN(decidedAt) || decidedAt < cutoff) continue;
    if (o.status === "joined") joined += 1;
    else if (o.status === "not_joined") notJoined += 1;
  }
  const total = joined + notJoined;
  if (total === 0) return null;
  return Math.round((notJoined / total) * 100);
}
