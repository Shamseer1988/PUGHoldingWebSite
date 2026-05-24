"use client";

import * as React from "react";
import Link from "next/link";
import {
  CheckCircle2,
  ExternalLink,
  FileUp,
  Loader2,
  Plus,
  Search,
  Upload,
  Users,
  X,
} from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
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
import { env } from "@/lib/env";
import type {
  BulkUploadResult,
  Candidate,
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
  const [items, setItems] = React.useState<CandidateListItem[] | null>(null);
  const [searchQ, setSearchQ] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [singleOpen, setSingleOpen] = React.useState(false);
  const [bulkOpen, setBulkOpen] = React.useState(false);
  const [jobs, setJobs] = React.useState<JobOpening[]>([]);

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
      const params = new URLSearchParams();
      if (searchQ.trim()) params.set("q", searchQ.trim());
      const url = `/hr/candidates${params.toString() ? `?${params}` : ""}`;
      setItems(await hrApi.get<CandidateListItem[]>(url));
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  return (
    <HrShell
      title="Candidates"
      description="Every CV received from the public careers page or uploaded by HR."
      actions={
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setBulkOpen(true)}
          >
            <Upload className="h-4 w-4" />
            Bulk ZIP
          </Button>
          <Button size="sm" onClick={() => setSingleOpen(true)}>
            <Plus className="h-4 w-4" />
            Upload CV
          </Button>
        </div>
      }
    >
      <Toast message={toast} onClose={() => setToast(null)} />

      {error && (
        <div role="alert" className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">
          {error}
        </div>
      )}

      {/* Search row */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          refresh();
        }}
        className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border/60 bg-background/60 p-4 backdrop-blur"
      >
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="cands-search">Search</Label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="cands-search"
              placeholder="Name, email or mobile"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>
        <Button type="submit" variant="outline">Apply</Button>
      </form>

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
                <TableHead>Candidate</TableHead>
                <TableHead className="hidden md:table-cell">Contact</TableHead>
                <TableHead className="hidden lg:table-cell w-24">Exp.</TableHead>
                <TableHead className="hidden md:table-cell w-32">Source</TableHead>
                <TableHead className="hidden lg:table-cell w-36">Created</TableHead>
                <TableHead className="w-24 text-right">CV</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((c) => (
                <CandidateRow key={c.id} c={c} />
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
    </HrShell>
  );
}

function CandidateRow({ c }: { c: CandidateListItem }) {
  const [detail, setDetail] = React.useState<Candidate | null>(null);
  const [loading, setLoading] = React.useState(false);

  async function loadDetail() {
    if (detail) return;
    setLoading(true);
    try {
      setDetail(await hrApi.get<Candidate>(`/hr/candidates/${c.id}`));
    } finally {
      setLoading(false);
    }
  }

  // Resolve uploads against the backend host (uploads are served by FastAPI,
  // not by Next.js).
  function resolveCvUrl(path: string): string {
    if (/^https?:\/\//i.test(path)) return path;
    if (path.startsWith("/api/")) {
      try {
        return `${new URL(env.apiBaseUrl).origin}${path}`;
      } catch {
        return path;
      }
    }
    return path;
  }

  return (
    <TableRow>
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
        {loading ? (
          <Loader2 className="ml-auto inline h-4 w-4 animate-spin" />
        ) : detail ? (
          detail.documents[0] ? (
            <Link
              href={resolveCvUrl(detail.documents[0].file_path)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-primary"
            >
              Open
              <ExternalLink className="h-3 w-3" />
            </Link>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )
        ) : (
          <Button
            size="sm"
            variant="ghost"
            onClick={loadDetail}
            className="px-2 text-xs"
          >
            View
          </Button>
        )}
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
