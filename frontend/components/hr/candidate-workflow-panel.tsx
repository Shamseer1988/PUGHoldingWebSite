"use client";

import * as React from "react";
import {
  AlertTriangle,
  ArrowRight,
  Ban,
  Briefcase,
  CheckCircle2,
  History,
  Loader2,
  MoveRight,
  ShieldAlert,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import type {
  Candidate,
  CandidateApplicationSummary,
  CandidateStatusHistoryEntry,
  StatusOption,
  StatusPipelineMeta,
} from "@/lib/hr/types";
import { cn } from "@/lib/utils";


interface CandidateWorkflowPanelProps {
  candidate: Candidate;
  onChanged: () => void;
}

export function CandidateWorkflowPanel({
  candidate,
  onChanged,
}: CandidateWorkflowPanelProps) {
  const [meta, setMeta] = React.useState<StatusPipelineMeta | null>(null);
  const [metaErr, setMetaErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    hrApi
      .get<StatusPipelineMeta>("/hr/candidates/workflow/meta")
      .then(setMeta)
      .catch((err) => setMetaErr((err as HrApiError).message));
  }, []);

  if (candidate.applications.length === 0) {
    return (
      <section className="rounded-xl border border-dashed border-border/60 bg-card p-5 text-sm text-muted-foreground">
        Workflow status is per-application — link this candidate to a job first.
      </section>
    );
  }

  return (
    <section className="space-y-3 rounded-xl border border-border/60 bg-card p-5">
      <header>
        <h3 className="text-sm font-semibold">Recruitment workflow</h3>
        <p className="text-xs text-muted-foreground">
          Move each application through the pipeline. Rejection and blacklist
          require a reason and are audited.
        </p>
      </header>

      {metaErr && (
        <p className="text-xs text-rose-600 dark:text-rose-300" role="alert">
          {metaErr}
        </p>
      )}

      <div className="space-y-3">
        {candidate.applications.map((app) => (
          <ApplicationWorkflowRow
            key={app.id}
            candidateId={candidate.id}
            application={app}
            meta={meta}
            onChanged={onChanged}
          />
        ))}
      </div>
    </section>
  );
}

interface RowProps {
  candidateId: number;
  application: CandidateApplicationSummary;
  meta: StatusPipelineMeta | null;
  onChanged: () => void;
}

function ApplicationWorkflowRow({
  candidateId,
  application,
  meta,
  onChanged,
}: RowProps) {
  const [historyOpen, setHistoryOpen] = React.useState(false);
  const [history, setHistory] = React.useState<
    CandidateStatusHistoryEntry[] | null
  >(null);
  const [changing, setChanging] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [newStatus, setNewStatus] = React.useState<string>("");
  const [remarks, setRemarks] = React.useState("");
  const [rejectionReason, setRejectionReason] = React.useState("");
  const [blacklistApproval, setBlacklistApproval] = React.useState("");

  React.useEffect(() => {
    setNewStatus(application.allowed_next_statuses[0] ?? "");
    setRemarks("");
    setRejectionReason("");
    setBlacklistApproval("");
    setError(null);
  }, [application.id, application.status, application.allowed_next_statuses]);

  const statusLabels = React.useMemo(() => {
    const map: Record<string, StatusOption> = {};
    if (meta) {
      for (const s of meta.statuses) map[s.value] = s;
    }
    return map;
  }, [meta]);

  async function loadHistory() {
    if (history !== null) return;
    try {
      const data = await hrApi.get<CandidateStatusHistoryEntry[]>(
        `/hr/candidates/${candidateId}/applications/${application.id}/status-history`
      );
      setHistory(data);
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  async function submit() {
    if (!newStatus) return;
    setChanging(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { new_status: newStatus };
      if (remarks.trim()) body.remarks = remarks.trim();
      if (newStatus === "rejected") body.rejection_reason = rejectionReason.trim();
      if (newStatus === "blacklisted")
        body.blacklist_approval = blacklistApproval.trim();

      await hrApi.post(
        `/hr/candidates/${candidateId}/applications/${application.id}/status`,
        body
      );
      // Re-fetch history if it was open.
      setHistory(null);
      if (historyOpen) await loadHistory();
      onChanged();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setChanging(false);
    }
  }

  const isRejection = newStatus === "rejected";
  const isBlacklist = newStatus === "blacklisted";
  const isFinal =
    statusLabels[application.status]?.is_final ?? false;
  const noMoves = application.allowed_next_statuses.length === 0;

  return (
    <div className="rounded-lg border border-border/60 bg-background/40">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <Briefcase className="h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">
            {application.job_title ?? "Unlinked application"}
          </p>
          <p className="text-[11px] text-muted-foreground">
            Applied {new Date(application.applied_at).toLocaleDateString()}
            {application.history_count > 0
              ? ` · ${application.history_count} status change${
                  application.history_count === 1 ? "" : "s"
                }`
              : ""}
          </p>
        </div>
        <StatusPill
          status={application.status}
          label={application.status_label ?? application.status}
          isFinal={isFinal}
        />
      </div>

      {application.last_rejection_reason && application.status === "rejected" && (
        <p className="flex items-start gap-2 border-t border-border/60 bg-rose-500/5 px-4 py-2 text-[11px] text-rose-700 dark:text-rose-300">
          <XCircle className="mt-0.5 h-3.5 w-3.5" />
          <span>
            <strong>Rejection reason:</strong> {application.last_rejection_reason}
          </span>
        </p>
      )}

      {noMoves && (
        <p className="border-t border-border/60 bg-background/60 px-4 py-2 text-[11px] text-muted-foreground">
          No further transitions available from <code>{application.status}</code>.
        </p>
      )}

      {!noMoves && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
          className="space-y-3 border-t border-border/60 bg-background/60 p-4"
        >
          <div className="grid items-end gap-3 sm:grid-cols-[1fr_auto]">
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                Move to
              </Label>
              <Select
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
                disabled={changing}
              >
                {application.allowed_next_statuses.map((value) => (
                  <option key={value} value={value}>
                    {statusLabels[value]?.label ?? value}
                  </option>
                ))}
              </Select>
            </div>
            <Button type="submit" disabled={changing || !newStatus}>
              {changing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <MoveRight className="h-4 w-4" />
              )}
              Update status
            </Button>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Remarks (optional)</Label>
            <Input
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="Add a short note (visible in the audit log + timeline)"
              disabled={changing}
            />
          </div>

          {isRejection && (
            <div className="space-y-1.5 rounded-md border border-rose-500/30 bg-rose-500/5 p-3">
              <Label className="flex items-center gap-1.5 text-xs text-rose-700 dark:text-rose-300">
                <XCircle className="h-3.5 w-3.5" />
                Rejection reason <span className="text-rose-500">*</span>
              </Label>
              <Textarea
                rows={3}
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="Required — explain why this candidate is being rejected."
                required
                disabled={changing}
              />
            </div>
          )}

          {isBlacklist && (
            <div className="space-y-1.5 rounded-md border border-orange-500/30 bg-orange-500/5 p-3">
              <Label className="flex items-center gap-1.5 text-xs text-orange-700 dark:text-orange-300">
                <ShieldAlert className="h-3.5 w-3.5" />
                Blacklist approval <span className="text-rose-500">*</span>
              </Label>
              <Textarea
                rows={3}
                value={blacklistApproval}
                onChange={(e) => setBlacklistApproval(e.target.value)}
                placeholder="Required — who approved the blacklist and why."
                required
                disabled={changing}
              />
              <p className="text-[11px] text-orange-700 dark:text-orange-300">
                Blacklisting is restricted to superusers. The candidate's
                blacklist flag will be set automatically.
              </p>
            </div>
          )}

          {error && (
            <p
              role="alert"
              className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300"
            >
              <AlertTriangle className="mr-1 inline h-3.5 w-3.5" />
              {error}
            </p>
          )}
        </form>
      )}

      <div className="border-t border-border/60 px-4 py-2">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="px-2 text-xs"
          onClick={() => {
            setHistoryOpen((o) => !o);
            if (!historyOpen && history === null) void loadHistory();
          }}
          aria-expanded={historyOpen}
        >
          <History className="h-3.5 w-3.5" />
          {historyOpen ? "Hide history" : "Show history"}
          {application.history_count > 0 && (
            <span className="ml-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px]">
              {application.history_count}
            </span>
          )}
        </Button>

        {historyOpen && (
          <div className="mt-2 space-y-2 pb-1">
            {history === null ? (
              <p className="text-xs text-muted-foreground">
                <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" />
                Loading timeline…
              </p>
            ) : history.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No status changes yet — every transition will appear here.
              </p>
            ) : (
              <Timeline entries={history} labels={statusLabels} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}


function Timeline({
  entries,
  labels,
}: {
  entries: CandidateStatusHistoryEntry[];
  labels: Record<string, StatusOption>;
}) {
  return (
    <ol className="ml-2 space-y-3 border-l border-border/60 pl-4">
      {entries.map((entry) => {
        const oldLabel = entry.old_status
          ? labels[entry.old_status]?.label ?? entry.old_status
          : "—";
        const newLabel = labels[entry.new_status]?.label ?? entry.new_status;
        const isReject = entry.new_status === "rejected";
        const isBlacklist = entry.new_status === "blacklisted";
        return (
          <li key={entry.id} className="relative text-xs">
            <span
              aria-hidden
              className={cn(
                "absolute -left-[1.0625rem] top-1 inline-block h-2.5 w-2.5 rounded-full ring-2 ring-background",
                isReject
                  ? "bg-rose-500"
                  : isBlacklist
                    ? "bg-orange-500"
                    : entry.new_status === "joined"
                      ? "bg-emerald-500"
                      : "bg-primary"
              )}
            />
            <div className="flex flex-wrap items-baseline gap-1">
              <span className="font-medium text-foreground">{oldLabel}</span>
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
              <span className="font-medium text-foreground">{newLabel}</span>
              <span className="text-muted-foreground">
                · {new Date(entry.created_at).toLocaleString()}
              </span>
              {entry.changed_by_email && (
                <span className="text-muted-foreground">
                  · {entry.changed_by_email}
                </span>
              )}
            </div>
            {entry.remarks && (
              <p className="mt-0.5 text-muted-foreground">{entry.remarks}</p>
            )}
            {entry.rejection_reason && (
              <p className="mt-0.5 rounded bg-rose-500/5 px-2 py-1 text-rose-700 dark:text-rose-300">
                <XCircle className="mr-1 inline h-3 w-3" />
                {entry.rejection_reason}
              </p>
            )}
            {entry.blacklist_approval && (
              <p className="mt-0.5 rounded bg-orange-500/5 px-2 py-1 text-orange-700 dark:text-orange-300">
                <Ban className="mr-1 inline h-3 w-3" />
                {entry.blacklist_approval}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}


function StatusPill({
  status,
  label,
  isFinal,
}: {
  status: string;
  label: string;
  isFinal: boolean;
}) {
  let tone =
    "border-border/60 bg-background/60 text-foreground";
  if (status === "joined") {
    tone =
      "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  } else if (status === "rejected") {
    tone =
      "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300";
  } else if (status === "blacklisted") {
    tone =
      "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300";
  } else if (
    [
      "shortlisted",
      "first_interview",
      "technical_interview",
      "final_interview",
      "selected",
      "offer_sent",
    ].includes(status)
  ) {
    tone =
      "border-primary/30 bg-primary/10 text-primary";
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold",
        tone
      )}
    >
      {status === "joined" && <CheckCircle2 className="h-3 w-3" />}
      {status === "rejected" && <XCircle className="h-3 w-3" />}
      {status === "blacklisted" && <Ban className="h-3 w-3" />}
      {label}
      {isFinal && (
        <span className="ml-0.5 text-[10px] uppercase tracking-wider opacity-70">
          Final
        </span>
      )}
    </span>
  );
}
