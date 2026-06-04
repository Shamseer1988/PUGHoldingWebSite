"use client";

import * as React from "react";
import Link from "next/link";
import {
  Briefcase,
  CheckCircle2,
  ExternalLink,
  Handshake,
  Loader2,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import { usePermission } from "@/components/auth/permission";
import { HrShell } from "@/components/hr/hr-shell";
import { JobApprovalActions } from "@/components/hr/job-approval-actions";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import { useHrDataSync } from "@/lib/hr/data-sync";
import {
  PERM_HR_JOBS_APPROVE,
  PERM_HR_OFFERS_APPROVE,
} from "@/lib/hr/permissions";
import type { JobOpening, Offer } from "@/lib/hr/types";


/**
 * Inline approve / reject for a single pending offer. Mirrors the
 * remarks-on-reject flow of {@link JobApprovalActions} so jobs and offers
 * feel the same in the queue.
 */
function OfferApprovalRow({
  offer,
  onDone,
}: {
  offer: Offer;
  onDone: () => void;
}) {
  const [busy, setBusy] = React.useState<"approve" | "reject" | null>(null);
  const [showReject, setShowReject] = React.useState(false);
  const [reason, setReason] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  async function act(action: "approve" | "reject") {
    setBusy(action);
    setError(null);
    try {
      const body = action === "reject" ? { remarks: reason.trim() } : undefined;
      await hrApi.post(`/hr/offers/${offer.id}/${action}`, body);
      onDone();
    } catch (err) {
      setError((err as HrApiError).message);
      setBusy(null);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          onClick={() => act("approve")}
          disabled={busy !== null}
        >
          {busy === "approve" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <CheckCircle2 className="h-3.5 w-3.5" />
          )}
          <span className="ml-1">Approve &amp; issue</span>
        </Button>
        {showReject ? (
          <Button
            type="button"
            size="sm"
            variant="destructive"
            onClick={() => act("reject")}
            disabled={busy !== null || reason.trim().length < 4}
          >
            {busy === "reject" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <XCircle className="h-3.5 w-3.5" />
            )}
            <span className="ml-1">Confirm reject</span>
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="destructive"
            onClick={() => setShowReject(true)}
            disabled={busy !== null}
          >
            <XCircle className="h-3.5 w-3.5" />
            <span className="ml-1">Reject</span>
          </Button>
        )}
      </div>
      {showReject ? (
        <div className="space-y-1.5 rounded-md border border-amber-200 bg-amber-50 p-3">
          <label className="text-xs font-medium text-amber-900">
            Rejection reason (required, ≥ 4 chars)
          </label>
          <Textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            className="text-sm"
            placeholder="Why is this offer being sent back to draft?"
          />
        </div>
      ) : null}
      {error ? <p className="text-xs text-rose-700">{error}</p> : null}
    </div>
  );
}


/**
 * Approvals queue — one page listing the job openings and offers that are
 * sitting in ``pending_approval`` and waiting on this user (an approver).
 * Approve / reject / request-revision happen inline; the list refetches on
 * every HR realtime pulse so two approvers never collide.
 */
export default function HrApprovalsPage() {
  const perms = usePermission();
  const canJobs = perms.has(PERM_HR_JOBS_APPROVE);
  const canOffers = perms.has(PERM_HR_OFFERS_APPROVE);

  const [jobs, setJobs] = React.useState<JobOpening[] | null>(null);
  const [offers, setOffers] = React.useState<Offer[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    setError(null);
    try {
      const [j, o] = await Promise.all([
        canJobs
          ? hrApi.get<JobOpening[]>("/hr/jobs?approval_status=pending_approval")
          : Promise.resolve<JobOpening[]>([]),
        canOffers
          ? hrApi.get<Offer[]>("/hr/offers?status=pending_approval")
          : Promise.resolve<Offer[]>([]),
      ]);
      setJobs(j);
      setOffers(o);
    } catch (err) {
      setError((err as HrApiError).message);
      setJobs((prev) => prev ?? []);
      setOffers((prev) => prev ?? []);
    }
  }, [canJobs, canOffers]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  // Live refresh when any operator approves / submits elsewhere.
  useHrDataSync(refresh);

  const loading = jobs === null || offers === null;
  const total = (jobs?.length ?? 0) + (offers?.length ?? 0);

  return (
    <HrShell
      title="Approvals"
      description="Job openings and offers awaiting your approval. Approve to publish / issue, or send back with a reason."
      actions={
        <Button type="button" variant="outline" onClick={() => void refresh()}>
          Refresh
        </Button>
      }
    >
      {!canJobs && !canOffers ? (
        <div className="rounded-xl border border-dashed border-border/60 py-16 text-center text-sm text-muted-foreground">
          You don&apos;t have approval rights. Ask a Super Admin to grant{" "}
          <code className="text-xs">hr:jobs:approve</code> or{" "}
          <code className="text-xs">hr:offers:approve</code>.
        </div>
      ) : (
        <>
          {error ? (
            <p
              role="alert"
              className="mb-4 rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-700 dark:text-rose-300"
            >
              {error}
            </p>
          ) : null}

          {loading ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading the approval
              queue…
            </p>
          ) : total === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border/60 py-16 text-center">
              <ShieldCheck className="h-8 w-8 text-emerald-500" />
              <p className="text-sm font-medium">Nothing awaiting approval</p>
              <p className="text-xs text-muted-foreground">
                Jobs and offers submitted for approval will appear here.
              </p>
            </div>
          ) : (
            <div className="space-y-8">
              {canJobs && jobs && jobs.length > 0 ? (
                <section className="space-y-3">
                  <h2 className="flex items-center gap-2 text-sm font-semibold">
                    <Briefcase className="h-4 w-4 text-primary" />
                    Job openings
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {jobs.length}
                    </span>
                  </h2>
                  <div className="space-y-3">
                    {jobs.map((job) => (
                      <article
                        key={job.id}
                        className="rounded-lg border border-border/60 bg-background/60 p-4"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-medium">{job.title}</p>
                            <p className="text-xs text-muted-foreground">
                              {job.department ?? "—"}
                            </p>
                          </div>
                          <Link
                            href="/hr/jobs"
                            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                          >
                            Open <ExternalLink className="h-3 w-3" />
                          </Link>
                        </div>
                        <div className="mt-3">
                          <JobApprovalActions
                            job={job}
                            canApprove={canJobs}
                            canSubmit={false}
                            canPublish={false}
                            onUpdated={() => void refresh()}
                          />
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
              ) : null}

              {canOffers && offers && offers.length > 0 ? (
                <section className="space-y-3">
                  <h2 className="flex items-center gap-2 text-sm font-semibold">
                    <Handshake className="h-4 w-4 text-primary" />
                    Offers
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {offers.length}
                    </span>
                  </h2>
                  <div className="space-y-3">
                    {offers.map((offer) => (
                      <article
                        key={offer.id}
                        className="rounded-lg border border-border/60 bg-background/60 p-4"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="font-medium">
                              {offer.candidate_name ?? "Candidate"}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {[
                                offer.position ?? offer.job_title,
                                offer.department,
                                offer.salary_offered != null
                                  ? `Salary: ${offer.salary_offered.toLocaleString()}`
                                  : null,
                              ]
                                .filter(Boolean)
                                .join(" · ") || "—"}
                            </p>
                          </div>
                          <Link
                            href="/hr/offers"
                            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                          >
                            Open <ExternalLink className="h-3 w-3" />
                          </Link>
                        </div>
                        <div className="mt-3">
                          <OfferApprovalRow
                            offer={offer}
                            onDone={() => void refresh()}
                          />
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
              ) : null}
            </div>
          )}
        </>
      )}
    </HrShell>
  );
}
