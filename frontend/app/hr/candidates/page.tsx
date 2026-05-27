"use client";

import * as React from "react";
import {
  CheckCircle2,
  ExternalLink,
  FileUp,
  Filter,
  Loader2,
  Plus,
  Search,
  Upload,
  Users,
  X,
} from "lucide-react";

import { usePermission } from "@/components/auth/permission";
import { BulkStatusModal } from "@/components/hr/bulk-status-modal";
import { CandidateDetailDrawer } from "@/components/hr/candidate-detail-drawer";
import {
  CandidateFilterPanel,
  filtersToQueryParams,
} from "@/components/hr/candidate-filter-panel";
import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { ScoreBadge } from "@/components/hr/score-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { hrApi, HrApiError } from "@/lib/hr/api";
import {
  PERM_HR_CANDIDATES_EDIT,
  PERM_HR_CANDIDATES_STATUS_UPDATE,
} from "@/lib/hr/permissions";
import type {
  BulkUploadResult,
  CandidateAdvancedFilters,
  CandidateListItem,
  ApplicationSubmissionResponse,
  JobOpening,
} from "@/lib/hr/types";

const SOURCE_LABEL: Record<string, string> = {
  public_form: "Public form",
  manual_upload: "Manual upload",
  bulk_upload: "Bulk ZIP",
};


export default function HrCandidatesPage() {
  const perms = usePermission();
  const [items, setItems] = React.useState<CandidateListItem[] | null>(null);
  const [filters, setFilters] = React.useState<CandidateAdvancedFilters>({});
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [singleOpen, setSingleOpen] = React.useState(false);
  const [bulkOpen, setBulkOpen] = React.useState(false);
  const [jobs, setJobs] = React.useState<JobOpening[]>([]);
  const [detailId, setDetailId] = React.useState<number | null>(null);
  const [selectedAppIds, setSelectedAppIds] = React.useState<Set<number>>(
    new Set(),
  );
  const [bulkStatusOpen, setBulkStatusOpen] = React.useState(false);

  React.useEffect(() => {
    refresh();
    // Pre-load open jobs once for the upload drawers.
    hrApi
      .get<JobOpening[]>("/hr/jobs?status=open")
      .then(setJobs)
      .catch(() => setJobs([]));
  }, []);

  async function refresh() {
    setItems(null);
    try {
      const params = filtersToQueryParams(filters);
      const url = `/hr/candidates${params.toString() ? `?${params}` : ""}`;
      setItems(await hrApi.get<CandidateListItem[]>(url));
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  function resetFilters() {
    setFilters({});
    // Refresh after the next render — see useEffect below.
  }

  // Re-run the list whenever the filter bundle changes from a Reset.
  React.useEffect(() => {
    if (Object.keys(filters).length === 0) void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const activeFilterCount = Object.entries(filters).filter(
    ([k, v]) =>
      v !== undefined &&
      v !== "" &&
      v !== null &&
      !(k === "include_archived" && v === false)
  ).length;

  return (
    <HrShell
      title="Candidates"
      description="Every CV received from the public careers page or uploaded by HR."
      actions={
        <div className="flex items-center gap-2">
          {selectedAppIds.size > 0 &&
          perms.has(PERM_HR_CANDIDATES_STATUS_UPDATE) ? (
            <Button
              size="sm"
              onClick={() => setBulkStatusOpen(true)}
              aria-label="Bulk status change"
            >
              <CheckCircle2 className="h-4 w-4" />
              <span className="hidden sm:inline">
                Bulk status ({selectedAppIds.size})
              </span>
              <span className="sm:hidden">{selectedAppIds.size}</span>
            </Button>
          ) : null}
          {perms.has(PERM_HR_CANDIDATES_EDIT) && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setBulkOpen(true)}
                aria-label="Bulk ZIP upload"
              >
                <Upload className="h-4 w-4" />
                <span className="hidden sm:inline">Bulk ZIP</span>
              </Button>
              <Button
                size="sm"
                onClick={() => setSingleOpen(true)}
                aria-label="Upload a single CV"
              >
                <Plus className="h-4 w-4" />
                <span className="hidden sm:inline">Upload CV</span>
              </Button>
            </>
          )}
        </div>
      }
    >
      <Toast message={toast} onClose={() => setToast(null)} />

      {error && (
        <div role="alert" className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">
          {error}
        </div>
      )}

      {/* Quick search + Advanced toggle */}
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border/60 bg-background/60 p-4 backdrop-blur">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            refresh();
          }}
          className="flex flex-1 items-end gap-3"
        >
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="cands-search">Search</Label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="cands-search"
                placeholder="Name, email or mobile"
                value={filters.q ?? ""}
                onChange={(e) =>
                  setFilters({ ...filters, q: e.target.value })
                }
                className="pl-9"
              />
            </div>
          </div>
          <Button type="submit" variant="outline">
            Apply
          </Button>
        </form>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setFiltersOpen((o) => !o)}
          aria-expanded={filtersOpen}
        >
          <Filter className="h-3.5 w-3.5" />
          Advanced filters
          {activeFilterCount > 0 && (
            <span className="ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-primary/15 px-1.5 text-[10px] font-semibold text-primary">
              {activeFilterCount}
            </span>
          )}
        </Button>
      </div>

      {filtersOpen && (
        <div className="mb-4">
          <CandidateFilterPanel
            value={filters}
            onChange={setFilters}
            onApply={refresh}
            onReset={resetFilters}
          />
        </div>
      )}

      {items === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading…
        </p>
      ) : items.length === 0 ? (
        <HrEmptyState
          icon={Users}
          title="No candidates yet"
          description="Once applicants submit through /careers or you upload a CV here, candidates will appear in this list."
          action={
            <Button size="sm" onClick={() => setSingleOpen(true)}>
              <Plus className="h-4 w-4" />
              Upload first CV
            </Button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <input
                    type="checkbox"
                    aria-label="Select all"
                    checked={
                      items.length > 0 &&
                      items.every(
                        (c) =>
                          c.latest_application_id !== null &&
                          selectedAppIds.has(c.latest_application_id!),
                      )
                    }
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setSelectedAppIds(() => {
                        if (!checked) return new Set();
                        const next = new Set<number>();
                        items.forEach((c) => {
                          if (c.latest_application_id != null)
                            next.add(c.latest_application_id);
                        });
                        return next;
                      });
                    }}
                  />
                </TableHead>
                <TableHead>Candidate</TableHead>
                <TableHead className="hidden md:table-cell">Contact</TableHead>
                <TableHead className="hidden lg:table-cell w-24">Exp.</TableHead>
                <TableHead className="w-24 sm:w-32">Status</TableHead>
                <TableHead className="w-16 sm:w-24">Score</TableHead>
                <TableHead className="hidden md:table-cell w-32">Source</TableHead>
                <TableHead className="hidden lg:table-cell w-36">Created</TableHead>
                <TableHead className="w-16 sm:w-24 text-right">CV</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((c) => (
                <CandidateRow
                  key={c.id}
                  c={c}
                  onOpenDetail={() => setDetailId(c.id)}
                  isSelected={
                    c.latest_application_id != null &&
                    selectedAppIds.has(c.latest_application_id)
                  }
                  onToggleSelect={(checked) => {
                    if (c.latest_application_id == null) return;
                    setSelectedAppIds((prev) => {
                      const next = new Set(prev);
                      if (checked) next.add(c.latest_application_id!);
                      else next.delete(c.latest_application_id!);
                      return next;
                    });
                  }}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <SingleUploadDrawer
        open={singleOpen}
        jobs={jobs}
        onClose={() => setSingleOpen(false)}
        onUploaded={async (result) => {
          setToast(
            result.was_existing_candidate
              ? "Attached to existing candidate."
              : "Candidate created."
          );
          setSingleOpen(false);
          await refresh();
        }}
      />

      <BulkUploadDrawer
        open={bulkOpen}
        jobs={jobs}
        onClose={() => setBulkOpen(false)}
        onUploaded={async (result) => {
          setToast(
            `Bulk upload complete: ${result.created_candidates} new, ${result.matched_existing_candidates} matched.`
          );
          setBulkOpen(false);
          await refresh();
        }}
      />

      <CandidateDetailDrawer
        candidateId={detailId}
        onClose={() => setDetailId(null)}
        onSaved={() => {
          void refresh();
        }}
      />

      <BulkStatusModal
        open={bulkStatusOpen}
        selectedApplicationIds={Array.from(selectedAppIds)}
        onClose={() => setBulkStatusOpen(false)}
        onCompleted={(result) => {
          setToast(
            `${result.success_count} updated · ${result.failed_count} failed`,
          );
          setSelectedAppIds(new Set());
          void refresh();
        }}
      />
    </HrShell>
  );
}

function CandidateRow({
  c,
  onOpenDetail,
  isSelected,
  onToggleSelect,
}: {
  c: CandidateListItem;
  onOpenDetail: () => void;
  isSelected: boolean;
  onToggleSelect: (checked: boolean) => void;
}) {
  return (
    <TableRow
      onClick={onOpenDetail}
      className="cursor-pointer transition-colors hover:bg-muted/40"
    >
      <TableCell onClick={(e) => e.stopPropagation()}>
        <input
          type="checkbox"
          aria-label={`Select ${c.full_name}`}
          checked={isSelected}
          disabled={c.latest_application_id == null}
          title={
            c.latest_application_id == null
              ? "No application to act on yet"
              : undefined
          }
          onChange={(e) => onToggleSelect(e.target.checked)}
        />
      </TableCell>
      <TableCell>
        <p className="font-medium leading-tight">{c.full_name}</p>
        {c.current_designation && (
          <p className="text-xs text-muted-foreground">
            {c.current_designation}
          </p>
        )}
      </TableCell>
      <TableCell className="hidden md:table-cell text-muted-foreground">
        <div className="space-y-0.5 text-xs">
          {c.email && <p>{c.email}</p>}
          {c.mobile && <p>{c.mobile}</p>}
        </div>
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        {c.total_experience_years !== null
          ? `${c.total_experience_years}y`
          : "—"}
      </TableCell>
      <TableCell>
        <StatusChip status={c.latest_status} label={c.latest_status_label} />
      </TableCell>
      <TableCell>
        <ScoreBadge total={c.top_score} compact />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        {c.source ? (
          <Badge variant="muted">{SOURCE_LABEL[c.source] ?? c.source}</Badge>
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell className="hidden lg:table-cell text-muted-foreground text-xs">
        {new Date(c.created_at).toLocaleDateString()}
      </TableCell>
      <TableCell className="text-right">
        <Button
          size="sm"
          variant="ghost"
          onClick={(e) => {
            e.stopPropagation();
            onOpenDetail();
          }}
          className="px-2 text-xs"
          aria-label="Open candidate detail"
        >
          <span className="hidden sm:inline">Open</span>
          <ExternalLink className="h-3 w-3 sm:ml-1" />
        </Button>
      </TableCell>
    </TableRow>
  );
}

// ---------------------------------------------------------------------------
// Single-upload drawer
// ---------------------------------------------------------------------------

function SingleUploadDrawer({
  open,
  jobs,
  onClose,
  onUploaded,
}: {
  open: boolean;
  jobs: JobOpening[];
  onClose: () => void;
  onUploaded: (result: ApplicationSubmissionResponse) => void;
}) {
  const [file, setFile] = React.useState<File | null>(null);
  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [mobile, setMobile] = React.useState("");
  const [jobSlug, setJobSlug] = React.useState<string>("");
  const [currentDesignation, setCurrentDesignation] = React.useState("");
  const [experience, setExperience] = React.useState("");
  const [salary, setSalary] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [visa, setVisa] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setFile(null);
      setFullName("");
      setEmail("");
      setMobile("");
      setJobSlug("");
      setCurrentDesignation("");
      setExperience("");
      setSalary("");
      setNotice("");
      setVisa("");
      setError(null);
    }
  }, [open]);

  async function save() {
    setError(null);
    if (!file) {
      setError("Please choose a CV file.");
      return;
    }
    if (!fullName.trim()) {
      setError("Full name is required.");
      return;
    }
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("full_name", fullName.trim());
      if (email.trim()) fd.append("email", email.trim());
      if (mobile.trim()) fd.append("mobile", mobile.trim());
      if (jobSlug) fd.append("job_slug", jobSlug);
      if (currentDesignation.trim())
        fd.append("current_designation", currentDesignation.trim());
      if (experience) fd.append("total_experience_years", experience);
      if (salary) fd.append("expected_salary", salary);
      if (notice.trim()) fd.append("notice_period", notice.trim());
      if (visa.trim()) fd.append("visa_status", visa.trim());

      const result = await hrApi.postMultipart<ApplicationSubmissionResponse>(
        "/hr/candidates/upload",
        fd
      );
      onUploaded(result);
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;
  return (
    <Drawer title="Upload CV" onClose={onClose}>
      <form
        className="flex flex-1 flex-col overflow-y-auto"
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <div className="flex-1 space-y-4 p-5">
          <Field label="CV file" required hint="PDF, DOC, DOCX, PNG, or JPG · max 10 MB">
            <FilePicker file={file} onChange={setFile} disabled={saving} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Full name" required>
              <Input
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                disabled={saving}
              />
            </Field>
            <Field label="Email">
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={saving}
              />
            </Field>
            <Field label="Mobile">
              <Input
                value={mobile}
                onChange={(e) => setMobile(e.target.value)}
                disabled={saving}
              />
            </Field>
            <Field label="Current designation">
              <Input
                value={currentDesignation}
                onChange={(e) => setCurrentDesignation(e.target.value)}
                disabled={saving}
              />
            </Field>
            <Field label="Years of experience">
              <Input
                type="number"
                min={0}
                max={60}
                value={experience}
                onChange={(e) => setExperience(e.target.value)}
                disabled={saving}
              />
            </Field>
            <Field label="Expected salary (QAR/mo)">
              <Input
                type="number"
                min={0}
                value={salary}
                onChange={(e) => setSalary(e.target.value)}
                disabled={saving}
              />
            </Field>
            <Field label="Notice period">
              <Input
                value={notice}
                onChange={(e) => setNotice(e.target.value)}
                disabled={saving}
              />
            </Field>
            <Field label="Visa status">
              <Input
                value={visa}
                onChange={(e) => setVisa(e.target.value)}
                disabled={saving}
              />
            </Field>
          </div>

          <Field label="Link to job opening" hint="Optional · associates the application with a job">
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={jobSlug}
              onChange={(e) => setJobSlug(e.target.value)}
              disabled={saving}
            >
              <option value="">— No specific job —</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.slug}>
                  {j.title} · {j.company}
                </option>
              ))}
            </select>
          </Field>

          {error && (
            <p role="alert" className="text-sm text-rose-600 dark:text-rose-300">
              {error}
            </p>
          )}
        </div>

        <DrawerFooter onClose={onClose} saving={saving} label="Upload" />
      </form>
    </Drawer>
  );
}

// ---------------------------------------------------------------------------
// Bulk-upload drawer
// ---------------------------------------------------------------------------

function BulkUploadDrawer({
  open,
  jobs,
  onClose,
  onUploaded,
}: {
  open: boolean;
  jobs: JobOpening[];
  onClose: () => void;
  onUploaded: (result: BulkUploadResult) => void;
}) {
  const [file, setFile] = React.useState<File | null>(null);
  const [jobSlug, setJobSlug] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<BulkUploadResult | null>(null);

  React.useEffect(() => {
    if (open) {
      setFile(null);
      setJobSlug("");
      setError(null);
      setResult(null);
    }
  }, [open]);

  async function save() {
    setError(null);
    if (!file) {
      setError("Please choose a ZIP archive.");
      return;
    }
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (jobSlug) fd.append("job_slug", jobSlug);
      const out = await hrApi.postMultipart<BulkUploadResult>(
        "/hr/candidates/bulk-upload",
        fd
      );
      setResult(out);
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;
  return (
    <Drawer title="Bulk ZIP upload" onClose={onClose}>
      <form
        className="flex flex-1 flex-col overflow-y-auto"
        onSubmit={(e) => {
          e.preventDefault();
          if (result) {
            onUploaded(result);
          } else {
            save();
          }
        }}
      >
        <div className="flex-1 space-y-4 p-5">
          <Field label="ZIP archive" required hint="PDF / DOC / DOCX / PNG / JPG inside · max 50 MB">
            <FilePicker
              file={file}
              onChange={setFile}
              disabled={saving}
              accept=".zip,application/zip,application/x-zip-compressed"
              hint="ZIP only"
            />
          </Field>

          <Field label="Link to job opening" hint="Optional · all candidates will apply to this job">
            <select
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={jobSlug}
              onChange={(e) => setJobSlug(e.target.value)}
              disabled={saving}
            >
              <option value="">— No specific job —</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.slug}>
                  {j.title} · {j.company}
                </option>
              ))}
            </select>
          </Field>

          {error && (
            <p role="alert" className="text-sm text-rose-600 dark:text-rose-300">
              {error}
            </p>
          )}

          {result && (
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm">
              <p className="font-medium text-emerald-700 dark:text-emerald-200">
                Processed {result.total_files} files.
              </p>
              <ul className="mt-2 grid gap-1 text-xs text-emerald-800 dark:text-emerald-200">
                <li>New candidates: {result.created_candidates}</li>
                <li>Matched existing: {result.matched_existing_candidates}</li>
                <li>Duplicate applications skipped: {result.duplicate_applications_skipped}</li>
                <li>Skipped files: {result.skipped_files.length}</li>
              </ul>
              {result.skipped_files.length > 0 && (
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer text-emerald-800 dark:text-emerald-200">
                    Show skipped
                  </summary>
                  <ul className="mt-1 space-y-0.5">
                    {result.skipped_files.map((s) => (
                      <li key={s.name} className="text-muted-foreground">
                        <span className="font-mono">{s.name}</span> — {s.reason}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
        </div>

        <DrawerFooter
          onClose={onClose}
          saving={saving}
          label={result ? "Done" : "Upload"}
        />
      </form>
    </Drawer>
  );
}

// ---------------------------------------------------------------------------
// Reusable bits
// ---------------------------------------------------------------------------

function Drawer({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div role="dialog" aria-modal="true" className="fixed inset-0 z-40 flex">
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="flex w-full max-w-xl flex-col bg-background shadow-2xl">
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">{title}</h2>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </header>
        {children}
      </div>
    </div>
  );
}

function DrawerFooter({
  onClose,
  saving,
  label,
}: {
  onClose: () => void;
  saving: boolean;
  label: string;
}) {
  return (
    <footer className="flex items-center justify-end gap-2 border-t border-border/60 px-5 py-3">
      <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
        Cancel
      </Button>
      <Button type="submit" disabled={saving}>
        {saving && <Loader2 className="h-4 w-4 animate-spin" />}
        {saving ? "Uploading…" : label}
      </Button>
    </footer>
  );
}

function FilePicker({
  file,
  onChange,
  disabled,
  accept = ".pdf,.doc,.docx,.png,.jpg,.jpeg,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/png,image/jpeg",
  hint,
}: {
  file: File | null;
  onChange: (f: File | null) => void;
  disabled?: boolean;
  accept?: string;
  hint?: string;
}) {
  const id = React.useId();
  return (
    <>
      <label
        htmlFor={id}
        className="flex cursor-pointer items-center gap-3 rounded-md border border-dashed border-input bg-background/40 px-3 py-3 text-sm text-muted-foreground hover:border-primary/40 hover:text-foreground"
      >
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary">
          <FileUp className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-medium text-foreground">
            {file ? file.name : "Click to choose a file"}
          </span>
          {hint && (
            <span className="block text-xs text-muted-foreground">{hint}</span>
          )}
        </span>
      </label>
      <input
        id={id}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
        disabled={disabled}
      />
    </>
  );
}

function Field({
  label,
  children,
  hint,
  required,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
  required?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label>
        {label}
        {required && <span className="ml-0.5 text-rose-500">*</span>}
      </Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

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

function StatusChip({
  status,
  label,
}: {
  status: string | null;
  label: string | null;
}) {
  if (!status) return <span className="text-xs text-muted-foreground">—</span>;
  let tone = "border-border/60 bg-background/60 text-foreground";
  if (status === "joined") {
    tone = "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  } else if (status === "rejected") {
    tone = "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300";
  } else if (status === "blacklisted") {
    tone = "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300";
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
    tone = "border-primary/30 bg-primary/10 text-primary";
  }
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}
    >
      {label ?? status}
    </span>
  );
}
