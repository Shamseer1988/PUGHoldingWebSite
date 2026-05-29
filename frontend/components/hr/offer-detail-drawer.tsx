"use client";

import * as React from "react";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Edit3,
  FileDown,
  Loader2,
  Send,
  TrendingUp,
  UserX,
  X,
  XCircle,
} from "lucide-react";

import { usePermission } from "@/components/auth/permission";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import {
  PERM_HR_OFFERS_APPROVE,
  PERM_HR_OFFERS_CREATE,
  PERM_HR_OFFERS_DELETE,
} from "@/lib/hr/permissions";
import type {
  Offer,
  OfferStatusHistoryItem,
  OfferUpdatePayload,
} from "@/lib/hr/types";


interface Props {
  offerId: number;
  onClose: () => void;
  /** Fired after any state-changing action so the parent re-fetches. */
  onChanged: () => void;
}


/**
 * Detail drawer for one OfferTracking row. Shows:
 *   * Editable content (only enabled while status ∈ draft/pending/approved)
 *   * Lifecycle action buttons gated by status + permission
 *   * Status history timeline
 *
 * The buttons map directly to backend endpoints:
 *   submit-approval / approve / reject / issue / respond /
 *   mark-joined / mark-not-joined / withdraw / delete
 */
export function OfferDetailDrawer({ offerId, onClose, onChanged }: Props) {
  const perms = usePermission();
  const [offer, setOffer] = React.useState<Offer | null>(null);
  const [history, setHistory] = React.useState<OfferStatusHistoryItem[] | null>(
    null
  );
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [o, h] = await Promise.all([
        hrApi.get<Offer>(`/hr/offers/${offerId}`),
        hrApi.get<OfferStatusHistoryItem[]>(
          `/hr/offers/${offerId}/status-history`
        ),
      ]);
      setOffer(o);
      setHistory(h);
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setLoading(false);
    }
  }, [offerId]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  async function fire(
    method: "post" | "delete",
    path: string,
    body?: Record<string, unknown>
  ) {
    setError(null);
    try {
      if (method === "post") {
        await hrApi.post(path, body ?? {});
      } else {
        await hrApi.delete(path);
      }
      await refresh();
      onChanged();
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Offer detail"
      className="fixed inset-0 z-[60] flex"
    >
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="flex w-full max-w-2xl flex-col bg-background shadow-2xl">
        <header className="flex items-start justify-between gap-3 border-b border-border/60 px-5 py-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold">
              {offer?.candidate_name ?? `Offer #${offerId}`}
            </h2>
            <p className="truncate text-xs text-muted-foreground">
              {offer?.job_title ?? ""}
              {offer?.department ? ` · ${offer.department}` : ""}
              {offer?.offer_letter_number
                ? ` · ${offer.offer_letter_number}`
                : ""}
            </p>
          </div>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {loading && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
            </p>
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

          {offer && (
            <>
              <OfferActions
                offer={offer}
                onAction={fire}
                canApprove={perms.has(PERM_HR_OFFERS_APPROVE)}
                canCreate={perms.has(PERM_HR_OFFERS_CREATE)}
                canDelete={perms.has(PERM_HR_OFFERS_DELETE)}
              />
              <OfferContent
                offer={offer}
                canEdit={
                  perms.has(PERM_HR_OFFERS_CREATE) &&
                  ["draft", "pending_approval", "approved"].includes(
                    offer.status
                  )
                }
                onSaved={refresh}
              />
              <OfferHistorySection history={history ?? []} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Action buttons
// ---------------------------------------------------------------------------


function OfferActions({
  offer,
  onAction,
  canApprove,
  canCreate,
  canDelete,
}: {
  offer: Offer;
  onAction: (
    method: "post" | "delete",
    path: string,
    body?: Record<string, unknown>
  ) => Promise<void>;
  canApprove: boolean;
  canCreate: boolean;
  canDelete: boolean;
}) {
  const [busy, setBusy] = React.useState<string | null>(null);
  const [rejectMode, setRejectMode] = React.useState<
    "reject" | "withdraw" | "decline" | "not_joined" | null
  >(null);
  const [reason, setReason] = React.useState("");

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    try {
      await fn();
    } finally {
      setBusy(null);
      setRejectMode(null);
      setReason("");
    }
  }

  const status = offer.status;
  const path = `/hr/offers/${offer.id}`;

  return (
    <section className="space-y-3 rounded-md border border-border/60 bg-card p-3">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
        Actions
      </p>
      <div className="flex flex-wrap gap-2">
        {canCreate && status === "draft" && (
          <Button
            size="sm"
            onClick={() =>
              run("submit", async () =>
                onAction("post", `${path}/submit-approval`)
              )
            }
            disabled={busy !== null}
          >
            <Send className="h-3.5 w-3.5" />
            Submit for approval
          </Button>
        )}
        {canApprove && status === "pending_approval" && (
          <Button
            size="sm"
            onClick={() => run("approve", async () => onAction("post", `${path}/approve`))}
            disabled={busy !== null}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            Approve
          </Button>
        )}
        {canApprove && status === "pending_approval" && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => setRejectMode("reject")}
            disabled={busy !== null}
            className="text-rose-600"
          >
            <XCircle className="h-3.5 w-3.5" />
            Reject (back to draft)
          </Button>
        )}
        {canCreate && status === "approved" && (
          <Button
            size="sm"
            onClick={() => run("issue", async () => onAction("post", `${path}/issue`))}
            disabled={busy !== null}
          >
            <Send className="h-3.5 w-3.5" />
            Issue to candidate
          </Button>
        )}
        {canCreate && status === "sent" && (
          <>
            <Button
              size="sm"
              onClick={() =>
                run("accept", async () =>
                  onAction("post", `${path}/respond`, { accepted: true })
                )
              }
              disabled={busy !== null}
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Mark accepted
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setRejectMode("decline")}
              disabled={busy !== null}
              className="text-rose-600"
            >
              <XCircle className="h-3.5 w-3.5" />
              Mark declined
            </Button>
          </>
        )}
        {canCreate && status === "accepted" && (
          <>
            <Button
              size="sm"
              onClick={() =>
                run("joined", async () => onAction("post", `${path}/mark-joined`))
              }
              disabled={busy !== null}
            >
              <TrendingUp className="h-3.5 w-3.5" />
              Mark joined
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setRejectMode("not_joined")}
              disabled={busy !== null}
              className="text-rose-600"
            >
              <UserX className="h-3.5 w-3.5" />
              Mark not joined
            </Button>
          </>
        )}
        {canCreate && ["draft", "pending_approval", "approved", "sent", "accepted"].includes(status) && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => setRejectMode("withdraw")}
            disabled={busy !== null}
            className="text-rose-600"
          >
            <Ban className="h-3.5 w-3.5" />
            Withdraw
          </Button>
        )}
        {canDelete && status === "draft" && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() =>
              run("delete", async () => onAction("delete", path))
            }
            disabled={busy !== null}
            className="ml-auto text-rose-600"
          >
            Delete draft
          </Button>
        )}
      </div>

      {rejectMode !== null && (
        <div className="space-y-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-3">
          <Label className="text-xs">
            {rejectMode === "reject"
              ? "Reason for rejection (required, ≥ 4 chars)"
              : rejectMode === "withdraw"
                ? "Reason for withdrawal (required, ≥ 4 chars)"
                : rejectMode === "decline"
                  ? "Candidate's decline reason (optional)"
                  : "Reason for not joining (optional)"}
          </Label>
          <Textarea
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={busy !== null}
          />
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setRejectMode(null);
                setReason("");
              }}
              disabled={busy !== null}
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => {
                const trimmed = reason.trim();
                if (rejectMode === "reject") {
                  if (trimmed.length < 4) return;
                  void run("reject", async () =>
                    onAction("post", `${path}/reject`, { remarks: trimmed })
                  );
                } else if (rejectMode === "withdraw") {
                  if (trimmed.length < 4) return;
                  void run("withdraw", async () =>
                    onAction("post", `${path}/withdraw`, { remarks: trimmed })
                  );
                } else if (rejectMode === "decline") {
                  void run("decline", async () =>
                    onAction("post", `${path}/respond`, {
                      accepted: false,
                      decline_reason: trimmed || null,
                    })
                  );
                } else {
                  void run("not_joined", async () =>
                    onAction("post", `${path}/mark-not-joined`, {
                      reason: trimmed || null,
                    })
                  );
                }
              }}
              disabled={
                busy !== null ||
                ((rejectMode === "reject" || rejectMode === "withdraw") &&
                  reason.trim().length < 4)
              }
            >
              Confirm
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}


// ---------------------------------------------------------------------------
// Editable content section
// ---------------------------------------------------------------------------


function OfferContent({
  offer,
  canEdit,
  onSaved,
}: {
  offer: Offer;
  canEdit: boolean;
  onSaved: () => void;
}) {
  const [editing, setEditing] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Local form state — initialised from the offer.
  const [position, setPosition] = React.useState(offer.position ?? "");
  const [salary, setSalary] = React.useState(
    offer.salary_offered != null ? String(offer.salary_offered) : ""
  );
  const [allowances, setAllowances] = React.useState(offer.allowances ?? "");
  const [joining, setJoining] = React.useState(offer.joining_date ?? "");
  const [probation, setProbation] = React.useState(offer.probation_period ?? "");
  const [manager, setManager] = React.useState(offer.reporting_manager ?? "");
  const [workLocation, setWorkLocation] = React.useState(
    offer.work_location ?? ""
  );
  const [benefits, setBenefits] = React.useState(offer.benefits_summary ?? "");
  const [remarks, setRemarks] = React.useState(offer.remarks ?? "");

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const payload: OfferUpdatePayload = {
        position: position.trim() || null,
        salary_offered: salary ? Number(salary) : null,
        allowances: allowances.trim() || null,
        joining_date: joining || null,
        probation_period: probation.trim() || null,
        reporting_manager: manager.trim() || null,
        work_location: workLocation.trim() || null,
        benefits_summary: benefits.trim() || null,
        remarks: remarks.trim() || null,
      };
      await hrApi.patch(`/hr/offers/${offer.id}`, payload);
      setEditing(false);
      onSaved();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-3 rounded-md border border-border/60 bg-card p-3">
      <header className="flex items-center justify-between">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Offer content
        </p>
        <div className="inline-flex items-center gap-2">
          <DownloadLetterButton offerId={offer.id} />
          {canEdit && !editing && (
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              <Edit3 className="h-3.5 w-3.5" />
              Edit
            </Button>
          )}
        </div>
      </header>

      {!editing ? (
        <dl className="grid gap-2 text-xs sm:grid-cols-2">
          <Display label="Position" value={offer.position} />
          <Display
            label="Salary"
            value={
              offer.salary_offered != null
                ? offer.salary_offered.toLocaleString()
                : null
            }
          />
          <Display label="Joining date" value={offer.joining_date} />
          <Display label="Probation" value={offer.probation_period} />
          <Display
            label="Reporting manager"
            value={offer.reporting_manager}
          />
          <Display label="Work location" value={offer.work_location} />
          <Display label="Allowances" value={offer.allowances} wide />
          <Display label="Benefits summary" value={offer.benefits_summary} wide />
          <Display label="Remarks" value={offer.remarks} wide />
        </dl>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Position">
            <Input
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              disabled={saving}
            />
          </Field>
          <Field label="Salary">
            <Input
              type="number"
              min="0"
              value={salary}
              onChange={(e) => setSalary(e.target.value)}
              disabled={saving}
            />
          </Field>
          <Field label="Joining date">
            <Input
              type="date"
              value={joining}
              onChange={(e) => setJoining(e.target.value)}
              disabled={saving}
            />
          </Field>
          <Field label="Probation">
            <Input
              value={probation}
              onChange={(e) => setProbation(e.target.value)}
              placeholder="3 months"
              disabled={saving}
            />
          </Field>
          <Field label="Reporting manager">
            <Input
              value={manager}
              onChange={(e) => setManager(e.target.value)}
              disabled={saving}
            />
          </Field>
          <Field label="Work location">
            <Input
              value={workLocation}
              onChange={(e) => setWorkLocation(e.target.value)}
              disabled={saving}
            />
          </Field>
          <Field label="Allowances" wide>
            <Textarea
              rows={2}
              value={allowances}
              onChange={(e) => setAllowances(e.target.value)}
              disabled={saving}
            />
          </Field>
          <Field label="Benefits summary" wide>
            <Textarea
              rows={2}
              value={benefits}
              onChange={(e) => setBenefits(e.target.value)}
              disabled={saving}
            />
          </Field>
          <Field label="Remarks" wide>
            <Textarea
              rows={2}
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              disabled={saving}
            />
          </Field>
          <div className="sm:col-span-2 flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setEditing(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="button" onClick={save} disabled={saving}>
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Save
            </Button>
          </div>
          {error && (
            <p className="sm:col-span-2 text-xs text-rose-600 dark:text-rose-400">
              {error}
            </p>
          )}
        </div>
      )}
    </section>
  );
}


function Display({
  label,
  value,
  wide,
}: {
  label: string;
  value: string | null | undefined;
  wide?: boolean;
}) {
  return (
    <div className={wide ? "sm:col-span-2" : ""}>
      <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 whitespace-pre-wrap break-words">
        {value || <span className="text-muted-foreground">—</span>}
      </dd>
    </div>
  );
}


function Field({
  label,
  wide,
  children,
}: {
  label: string;
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={`space-y-1.5 ${wide ? "sm:col-span-2" : ""}`}>
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}


// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------


function OfferHistorySection({
  history,
}: {
  history: OfferStatusHistoryItem[];
}) {
  if (history.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border/60 bg-card px-3 py-4 text-center text-xs text-muted-foreground">
        Status history will populate as the offer moves through its lifecycle.
      </p>
    );
  }
  return (
    <section className="space-y-2 rounded-md border border-border/60 bg-card p-3">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
        Status history
      </p>
      <ol className="space-y-2">
        {history.map((h) => (
          <li
            key={h.id}
            className="rounded border border-border/60 bg-background/40 px-3 py-2 text-xs"
          >
            <div className="flex justify-between gap-2">
              <p className="font-medium">{h.action.replace(/_/g, " ")}</p>
              <p className="text-[11px] text-muted-foreground">
                {new Date(h.created_at).toLocaleString()}
              </p>
            </div>
            {(h.old_status || h.new_status) && (
              <p className="text-[11px] text-muted-foreground">
                {h.old_status ?? "—"} → {h.new_status ?? "—"}
              </p>
            )}
            {h.actor_email && (
              <p className="text-[11px] text-muted-foreground">
                by {h.actor_email}
              </p>
            )}
            {h.remarks && (
              <p className="mt-1 whitespace-pre-wrap rounded bg-muted/40 px-2 py-1 text-[11px]">
                {h.remarks}
              </p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}


function DownloadLetterButton({ offerId }: { offerId: number }) {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleClick() {
    setBusy(true);
    setError(null);
    try {
      await hrApi.downloadFile(
        `/hr/offers/${offerId}/pdf`,
        `offer_letter_${offerId}.pdf`,
        "GET"
      );
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="inline-flex flex-col items-end">
      <Button
        size="sm"
        variant="outline"
        onClick={handleClick}
        disabled={busy}
        title="Download as PDF"
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <FileDown className="h-3.5 w-3.5" />
        )}
        Letter PDF
      </Button>
      {error && (
        <span className="mt-1 text-[10px] text-rose-600" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
