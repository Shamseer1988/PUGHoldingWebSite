"use client";

import * as React from "react";
import {
  CheckCircle2,
  Loader2,
  Mailbox,
  Pause,
  Pencil,
  Play,
  Plus,
  Send,
  Trash2,
} from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { usePermission } from "@/components/auth/permission";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { hrApi, HrApiError } from "@/lib/hr/api";
import { PERM_HR_REPORTS_VIEW_ALL } from "@/lib/hr/permissions";
import { cn } from "@/lib/utils";


// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Frequency = "daily" | "weekly" | "monthly";
type RunStatus = "pending" | "success" | "failed" | null;

interface ScheduledReport {
  id: number;
  owner_id: number | null;
  owner_email: string | null;
  name: string;
  description: string | null;
  report_type: string;
  frequency: Frequency;
  recipients: string[];
  params: Record<string, unknown> | null;
  is_active: boolean;
  last_run_at: string | null;
  last_run_status: RunStatus;
  last_error: string | null;
  last_row_count: number | null;
  created_at: string;
  updated_at: string;
}

interface ReportTypeMeta {
  key: string;
  title: string;
  description: string;
  icon: string;
  min_scope: string;
}

interface RunResult {
  scheduled_report_id: number;
  name: string;
  recipients: string[];
  delivered_count: number;
  row_count: number;
  error: string | null;
}

const BASE = "/hr/scheduled-reports";

const FREQ_LABEL: Record<Frequency, string> = {
  daily: "Every day",
  weekly: "Every Monday",
  monthly: "1st of the month",
};


// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ScheduledReportsPage() {
  const { has } = usePermission();
  const canView = has(PERM_HR_REPORTS_VIEW_ALL);
  if (!canView) {
    return (
      <HrShell
        title="Scheduled report digests"
        description="Daily / weekly / monthly recurring report emails."
      >
        <HrEmptyState
          icon={Mailbox}
          title="Not available"
          description="You don't have permission to manage scheduled reports."
        />
      </HrShell>
    );
  }
  return <Body />;
}


function Body() {
  const [rows, setRows] = React.useState<ScheduledReport[] | null>(null);
  const [reportTypes, setReportTypes] = React.useState<ReportTypeMeta[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [editing, setEditing] = React.useState<ScheduledReport | null>(null);
  const [running, setRunning] = React.useState<number | null>(null);
  const [includeInactive, setIncludeInactive] = React.useState(false);

  React.useEffect(() => {
    void refresh();
    void loadReportTypes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  async function refresh() {
    setError(null);
    try {
      const q = includeInactive ? "?include_inactive=true" : "";
      const data = await hrApi.get<ScheduledReport[]>(`${BASE}${q}`);
      setRows(data);
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  async function loadReportTypes() {
    try {
      const list = await hrApi.get<ReportTypeMeta[]>("/hr/reports/types");
      setReportTypes(list);
    } catch (err) {
      // Non-fatal — the dropdown will be empty but the page still works.
      setError((err as HrApiError).message);
    }
  }

  const titleByKey = React.useMemo(() => {
    const m: Record<string, string> = {};
    for (const r of reportTypes) m[r.key] = r.title;
    return m;
  }, [reportTypes]);

  async function runNow(row: ScheduledReport) {
    setRunning(row.id);
    setError(null);
    try {
      const res = await hrApi.post<RunResult>(`${BASE}/${row.id}/run`);
      if (res.error) {
        setError(
          `"${row.name}" ran but reported an error: ${res.error}`
        );
      } else {
        setToast(
          `"${row.name}" delivered to ${res.delivered_count} recipient(s) (${res.row_count} rows).`
        );
      }
      await refresh();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setRunning(null);
    }
  }

  async function togglePaused(row: ScheduledReport) {
    try {
      await hrApi.patch(`${BASE}/${row.id}`, { is_active: !row.is_active });
      setToast(
        row.is_active ? `Paused "${row.name}".` : `Resumed "${row.name}".`
      );
      await refresh();
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  async function remove(row: ScheduledReport) {
    if (
      !confirm(
        `Delete "${row.name}"? Recipients will stop receiving this digest. This can't be undone.`
      )
    ) {
      return;
    }
    try {
      await hrApi.delete(`${BASE}/${row.id}`);
      setToast(`Deleted "${row.name}".`);
      await refresh();
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  return (
    <HrShell
      title="Scheduled report digests"
      description="Have any report emailed automatically — daily, weekly, or monthly — to a list of recipients."
      actions={
        <Button onClick={() => setCreating(true)} size="sm">
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New digest</span>
        </Button>
      }
    >
      <Toast message={toast} onClose={() => setToast(null)} />
      {error && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      <label className="mb-4 inline-flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
          checked={includeInactive}
          onChange={(e) => setIncludeInactive(e.target.checked)}
        />
        Include paused digests
      </label>

      {rows === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading scheduled digests…
        </p>
      ) : rows.length === 0 ? (
        <HrEmptyState
          icon={Mailbox}
          title="No scheduled digests yet"
          description="Create one and HR will start receiving the report automatically — no need to remember to download it."
          action={
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" />
              Create the first digest
            </Button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Digest</TableHead>
                <TableHead className="hidden md:table-cell">Cadence</TableHead>
                <TableHead className="hidden lg:table-cell">Recipients</TableHead>
                <TableHead className="hidden lg:table-cell w-40">
                  Last run
                </TableHead>
                <TableHead className="w-44 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <p className="flex items-center gap-1.5 font-medium leading-tight">
                      {row.name}
                      {!row.is_active && (
                        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-300">
                          Paused
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {titleByKey[row.report_type] || row.report_type}
                    </p>
                    {row.description && (
                      <p className="line-clamp-1 text-[11px] text-muted-foreground">
                        {row.description}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-xs">
                    {FREQ_LABEL[row.frequency]}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {row.recipients.slice(0, 2).map((r) => (
                        <span
                          key={r}
                          className="inline-flex max-w-[180px] truncate rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-[11px]"
                          title={r}
                        >
                          {r}
                        </span>
                      ))}
                      {row.recipients.length > 2 && (
                        <span className="text-[11px] text-muted-foreground">
                          +{row.recipients.length - 2} more
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-xs">
                    {row.last_run_at ? (
                      <div>
                        <p
                          className={cn(
                            "font-medium",
                            row.last_run_status === "success"
                              ? "text-emerald-700 dark:text-emerald-300"
                              : "text-rose-600"
                          )}
                        >
                          {new Date(row.last_run_at).toLocaleString()}
                        </p>
                        <p className="text-muted-foreground">
                          {row.last_run_status === "success" ? (
                            <>{row.last_row_count ?? 0} row(s) delivered</>
                          ) : (
                            <span title={row.last_error ?? ""}>
                              {row.last_error?.slice(0, 40) || "failed"}…
                            </span>
                          )}
                        </p>
                      </div>
                    ) : (
                      <span className="text-muted-foreground">
                        Never — will fire next at 09:00 UTC
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => runNow(row)}
                        disabled={running === row.id}
                      >
                        {running === row.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Send className="h-3.5 w-3.5" />
                        )}
                        Run now
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => togglePaused(row)}
                        aria-label={row.is_active ? "Pause" : "Resume"}
                        title={row.is_active ? "Pause" : "Resume"}
                      >
                        {row.is_active ? (
                          <Pause className="h-4 w-4" />
                        ) : (
                          <Play className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => setEditing(row)}
                        aria-label={`Edit ${row.name}`}
                        title="Edit"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => remove(row)}
                        className="text-rose-600 hover:text-rose-700"
                        aria-label={`Delete ${row.name}`}
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {(creating || editing) && (
        <DigestDialog
          editing={editing}
          reportTypes={reportTypes}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={(name, mode) => {
            setCreating(false);
            setEditing(null);
            setToast(
              mode === "create"
                ? `Created "${name}".`
                : `Updated "${name}".`
            );
            void refresh();
          }}
          onError={setError}
        />
      )}
    </HrShell>
  );
}


// ---------------------------------------------------------------------------
// Create / Edit dialog
// ---------------------------------------------------------------------------

function DigestDialog({
  editing,
  reportTypes,
  onClose,
  onSaved,
  onError,
}: {
  editing: ScheduledReport | null;
  reportTypes: ReportTypeMeta[];
  onClose: () => void;
  onSaved: (name: string, mode: "create" | "edit") => void;
  onError: (msg: string) => void;
}) {
  const [name, setName] = React.useState(() => editing?.name ?? "");
  const [description, setDescription] = React.useState(
    () => editing?.description ?? ""
  );
  const [reportType, setReportType] = React.useState(
    () => editing?.report_type ?? "shortlist"
  );
  const [frequency, setFrequency] = React.useState<Frequency>(
    () => editing?.frequency ?? "daily"
  );
  const [recipientsRaw, setRecipientsRaw] = React.useState(() =>
    (editing?.recipients ?? []).join(", ")
  );
  const [paramsJson, setParamsJson] = React.useState(() =>
    editing?.params ? JSON.stringify(editing.params, null, 2) : "{}"
  );
  const [isActive, setIsActive] = React.useState(
    () => editing?.is_active ?? true
  );
  const [saving, setSaving] = React.useState(false);

  const recipientList = recipientsRaw
    .split(/[,;\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
  const validEmail = (s: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
  const allEmailsValid = recipientList.length > 0 && recipientList.every(validEmail);
  const canSubmit =
    name.trim().length > 0 &&
    reportType.length > 0 &&
    allEmailsValid &&
    !saving;

  async function submit() {
    setSaving(true);
    let params: Record<string, unknown> | null = null;
    if (paramsJson.trim() && paramsJson.trim() !== "{}") {
      try {
        params = JSON.parse(paramsJson);
        if (typeof params !== "object" || Array.isArray(params)) {
          throw new Error("Params must be a JSON object.");
        }
      } catch (err) {
        onError(
          `Params JSON is invalid: ${(err as Error).message}. Use {} for none.`
        );
        setSaving(false);
        return;
      }
    }
    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || undefined,
        report_type: reportType,
        frequency,
        recipients: recipientList,
        params,
        is_active: isActive,
      };
      if (editing) {
        await hrApi.patch(`${BASE}/${editing.id}`, payload);
        onSaved(name.trim(), "edit");
      } else {
        await hrApi.post(BASE, payload);
        onSaved(name.trim(), "create");
      }
    } catch (err) {
      onError((err as HrApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" className="fixed inset-0 z-40 flex">
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) submit();
        }}
        className="flex w-full max-w-xl flex-col bg-background shadow-2xl"
      >
        <header className="border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">
            {editing ? `Edit "${editing.name}"` : "New scheduled digest"}
          </h2>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <div className="space-y-1.5">
            <Label htmlFor="d-name">Name *</Label>
            <Input
              id="d-name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Monday shortlist digest"
              disabled={saving}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="d-desc">Description</Label>
            <Textarea
              id="d-desc"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What this digest is for and who reads it."
              disabled={saving}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="d-type">Report *</Label>
              <Select
                id="d-type"
                value={reportType}
                onChange={(e) => setReportType(e.target.value)}
                disabled={saving}
              >
                {reportTypes.length === 0 && (
                  <option value="">Loading…</option>
                )}
                {reportTypes.map((rt) => (
                  <option key={rt.key} value={rt.key}>
                    {rt.title}
                  </option>
                ))}
              </Select>
              {reportTypes.find((r) => r.key === reportType)?.description && (
                <p className="text-[11px] text-muted-foreground">
                  {reportTypes.find((r) => r.key === reportType)?.description}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="d-freq">Frequency *</Label>
              <Select
                id="d-freq"
                value={frequency}
                onChange={(e) => setFrequency(e.target.value as Frequency)}
                disabled={saving}
              >
                <option value="daily">Daily — every morning</option>
                <option value="weekly">Weekly — every Monday</option>
                <option value="monthly">Monthly — 1st of the month</option>
              </Select>
              <p className="text-[11px] text-muted-foreground">
                Fires at 09:00 UTC. Set SCHEDULED_REPORTS_HOUR_UTC on
                the server to change.
              </p>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="d-recipients">Recipients *</Label>
            <Textarea
              id="d-recipients"
              rows={2}
              value={recipientsRaw}
              onChange={(e) => setRecipientsRaw(e.target.value)}
              disabled={saving}
              placeholder="alice@example.com, bob@example.com"
              className="font-mono text-xs"
            />
            <p
              className={cn(
                "text-[11px]",
                recipientList.length === 0
                  ? "text-muted-foreground"
                  : allEmailsValid
                    ? "text-emerald-700 dark:text-emerald-300"
                    : "text-rose-600"
              )}
            >
              {recipientList.length === 0
                ? "Comma or newline separated."
                : allEmailsValid
                  ? `${recipientList.length} recipient(s) — looks valid.`
                  : "One or more entries don't look like email addresses."}
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="d-params">
              Filter overrides — JSON (optional)
            </Label>
            <Textarea
              id="d-params"
              rows={6}
              value={paramsJson}
              onChange={(e) => setParamsJson(e.target.value)}
              disabled={saving}
              className="font-mono text-xs"
              placeholder={`{\n  "department": "Engineering",\n  "status": "shortlisted"\n}`}
            />
            <p className="text-[11px] text-muted-foreground">
              Same shape as the candidate-list filters / saved searches.
              Leave as <code>{`{}`}</code> to email the unfiltered report.
            </p>
          </div>

          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              disabled={saving}
            />
            Active — fire on cadence
          </label>
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-border/60 px-5 py-3">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={!canSubmit}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {saving
              ? "Saving…"
              : editing
                ? "Save changes"
                : "Create digest"}
          </Button>
        </footer>
      </form>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

function Toast({
  message,
  onClose,
}: {
  message: string | null;
  onClose: () => void;
}) {
  React.useEffect(() => {
    if (!message) return;
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [message, onClose]);
  if (!message) return null;
  return (
    <div
      role="status"
      className="mb-4 inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-200"
    >
      <CheckCircle2 className="h-4 w-4" />
      {message}
    </div>
  );
}
