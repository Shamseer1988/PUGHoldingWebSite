"use client";

import * as React from "react";
import {
  Archive,
  ArchiveRestore,
  Briefcase,
  CheckCircle2,
  Edit3,
  Loader2,
  PauseCircle,
  PlayCircle,
  Plus,
  Trash2,
  X,
  XCircle,
} from "lucide-react";

import { usePermission } from "@/components/auth/permission";
import { ConfirmReasonDialog } from "@/components/hr/confirm-reason-dialog";
import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { JobApprovalActions } from "@/components/hr/job-approval-actions";
import { JobApprovalBadge } from "@/components/hr/job-approval-badge";
import { JobApprovalTimeline } from "@/components/hr/job-approval-timeline";
import {
  PERM_HR_JOBS_APPROVE,
  PERM_HR_JOBS_CREATE,
  PERM_HR_JOBS_DELETE,
  PERM_HR_JOBS_EDIT,
  PERM_HR_JOBS_PUBLISH,
} from "@/lib/hr/permissions";
import { Badge } from "@/components/ui/badge";
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
import type { EmploymentType, JobOpening, JobStatus } from "@/lib/hr/types";

const STATUS_LABEL: Record<JobStatus, string> = {
  open: "Open",
  on_hold: "On hold",
  closed: "Closed",
};

const EMPLOYMENT_LABEL: Record<EmploymentType, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
};

interface JobFormState {
  slug: string;
  title: string;
  department: string;
  division: string;
  company: string;
  location: string;
  employment_type: EmploymentType;
  min_experience: number;
  max_experience: number;
  required_education: string;
  salary_min: string;
  salary_max: string;
  visa_requirement: string;
  nationality_preference: string;
  language_requirement: string;
  notice_period_preference: string;
  description: string;
  responsibilities: string;
  requirements: string;
  required_skills: string;
  preferred_skills: string;
  status: JobStatus;
}

const EMPTY_FORM: JobFormState = {
  slug: "",
  title: "",
  department: "",
  division: "",
  company: "Paris United Group Holding",
  location: "Doha, Qatar",
  employment_type: "full_time",
  min_experience: 0,
  max_experience: 0,
  required_education: "",
  salary_min: "",
  salary_max: "",
  visa_requirement: "",
  nationality_preference: "",
  language_requirement: "",
  notice_period_preference: "",
  description: "",
  responsibilities: "",
  requirements: "",
  required_skills: "",
  preferred_skills: "",
  status: "open",
};

export default function HrJobsPage() {
  const perms = usePermission();
  const [items, setItems] = React.useState<JobOpening[] | null>(null);
  const [editing, setEditing] = React.useState<JobOpening | null>(null);
  const [form, setForm] = React.useState<JobFormState>(EMPTY_FORM);
  const [open, setOpen] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [busyId, setBusyId] = React.useState<number | null>(null);

  // Filter UI state
  const [filterStatus, setFilterStatus] = React.useState<"" | JobStatus>("");
  const [filterDept, setFilterDept] = React.useState("");
  const [filterCompany, setFilterCompany] = React.useState("");
  const [searchQ, setSearchQ] = React.useState("");

  React.useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterStatus, filterDept, filterCompany]);

  async function refresh() {
    setItems(null);
    try {
      const params = new URLSearchParams();
      if (filterStatus) params.set("status", filterStatus);
      if (filterDept) params.set("department", filterDept);
      if (filterCompany) params.set("company", filterCompany);
      if (searchQ.trim()) params.set("q", searchQ.trim());
      const url = `/hr/jobs${params.toString() ? `?${params}` : ""}`;
      setItems(await hrApi.get<JobOpening[]>(url));
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setError(null);
    setOpen(true);
  }

  function openEdit(job: JobOpening) {
    setEditing(job);
    setForm({
      slug: job.slug,
      title: job.title,
      department: job.department,
      division: job.division ?? "",
      company: job.company,
      location: job.location,
      employment_type: job.employment_type,
      min_experience: job.min_experience,
      max_experience: job.max_experience,
      required_education: job.required_education ?? "",
      salary_min: job.salary_min != null ? String(job.salary_min) : "",
      salary_max: job.salary_max != null ? String(job.salary_max) : "",
      visa_requirement: job.visa_requirement ?? "",
      nationality_preference: job.nationality_preference ?? "",
      language_requirement: job.language_requirement ?? "",
      notice_period_preference: job.notice_period_preference ?? "",
      description: job.description ?? "",
      responsibilities: job.responsibilities ?? "",
      requirements: job.requirements ?? "",
      required_skills: job.required_skills ?? "",
      preferred_skills: job.preferred_skills ?? "",
      status: job.status,
    });
    setError(null);
    setOpen(true);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const body = {
        slug: form.slug.trim(),
        title: form.title.trim(),
        department: form.department.trim(),
        division: form.division.trim() || null,
        company: form.company.trim(),
        location: form.location.trim(),
        employment_type: form.employment_type,
        min_experience: Number(form.min_experience) || 0,
        max_experience: Number(form.max_experience) || 0,
        required_education: form.required_education.trim() || null,
        salary_min: form.salary_min ? Number(form.salary_min) : null,
        salary_max: form.salary_max ? Number(form.salary_max) : null,
        visa_requirement: form.visa_requirement.trim() || null,
        nationality_preference: form.nationality_preference.trim() || null,
        language_requirement: form.language_requirement.trim() || null,
        notice_period_preference: form.notice_period_preference.trim() || null,
        description: form.description.trim() || null,
        responsibilities: form.responsibilities.trim() || null,
        requirements: form.requirements.trim() || null,
        required_skills: form.required_skills.trim() || null,
        preferred_skills: form.preferred_skills.trim() || null,
        status: form.status,
      };
      if (editing) {
        await hrApi.patch(`/hr/jobs/${editing.id}`, body);
        setToast(`Updated “${body.title}”.`);
      } else {
        await hrApi.post("/hr/jobs", body);
        setToast(`Created “${body.title}”.`);
      }
      setOpen(false);
      await refresh();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function transition(
    job: JobOpening,
    action: "close" | "reopen" | "hold"
  ) {
    setBusyId(job.id);
    try {
      await hrApi.post(`/hr/jobs/${job.id}/${action}`);
      setToast(`${action === "close" ? "Closed" : action === "reopen" ? "Reopened" : "Put on hold"}: ${job.title}`);
      await refresh();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setBusyId(null);
    }
  }

  // Phase 8 — destructive actions go through a reason-capturing modal
  // rather than a browser confirm(). The reason is sent in the request
  // body and recorded on the audit row.
  const [confirmJob, setConfirmJob] = React.useState<
    | { job: JobOpening; action: "delete" | "archive" | "unarchive" }
    | null
  >(null);

  async function performJobAction(
    job: JobOpening,
    action: "delete" | "archive" | "unarchive",
    reason: string,
  ): Promise<void> {
    if (action === "delete") {
      await hrApi.delete(`/hr/jobs/${job.id}`, { reason });
      setToast("Job deleted.");
    } else if (action === "archive") {
      await hrApi.post(`/hr/jobs/${job.id}/archive`, { reason });
      setToast("Job archived.");
    } else {
      await hrApi.post(`/hr/jobs/${job.id}/unarchive`, {});
      setToast("Job restored.");
    }
    setConfirmJob(null);
    await refresh();
  }

  // Derive filter dropdown options from the current list.
  const departments = React.useMemo(
    () => Array.from(new Set((items ?? []).map((j) => j.department))).sort(),
    [items]
  );
  const companies = React.useMemo(
    () => Array.from(new Set((items ?? []).map((j) => j.company))).sort(),
    [items]
  );

  return (
    <HrShell
      title="Job openings"
      description="Manage active, on-hold, and closed job postings."
      actions={
        perms.has(PERM_HR_JOBS_CREATE) ? (
          <Button onClick={openNew} size="sm" aria-label="Add a new job opening">
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">New job</span>
          </Button>
        ) : null
      }
    >
      <Toast message={toast} onClose={() => setToast(null)} />

      {error && (
        <div role="alert" className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">
          {error}
        </div>
      )}

      {/* Filters */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          refresh();
        }}
        className="mb-4 grid gap-3 rounded-xl border border-border/60 bg-background/60 p-4 backdrop-blur sm:grid-cols-2 lg:grid-cols-[1.5fr_repeat(3,1fr)_auto]"
      >
        <div className="space-y-1.5">
          <Label htmlFor="search">Search</Label>
          <Input
            id="search"
            placeholder="Title or skill"
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="status">Status</Label>
          <Select
            id="status"
            value={filterStatus}
            onChange={(e) =>
              setFilterStatus(e.target.value as "" | JobStatus)
            }
          >
            <option value="">All</option>
            <option value="open">Open</option>
            <option value="on_hold">On hold</option>
            <option value="closed">Closed</option>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="dept">Department</Label>
          <Select
            id="dept"
            value={filterDept}
            onChange={(e) => setFilterDept(e.target.value)}
          >
            <option value="">All</option>
            {departments.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="company">Company</Label>
          <Select
            id="company"
            value={filterCompany}
            onChange={(e) => setFilterCompany(e.target.value)}
          >
            <option value="">All</option>
            {companies.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex items-end">
          <Button type="submit" variant="outline" className="w-full sm:w-auto">
            Apply
          </Button>
        </div>
      </form>

      {items === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading…
        </p>
      ) : items.length === 0 ? (
        <HrEmptyState
          icon={Briefcase}
          title="No jobs match"
          description="Add a new role or relax your filters."
          action={
            <Button onClick={openNew} size="sm">
              <Plus className="h-4 w-4" />
              New job
            </Button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead className="hidden md:table-cell">Department</TableHead>
                <TableHead className="hidden md:table-cell">Company</TableHead>
                <TableHead className="hidden lg:table-cell w-32">Posted</TableHead>
                <TableHead className="w-56">Status</TableHead>
                <TableHead className="w-44 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((job) => (
                <TableRow key={job.id}>
                  <TableCell>
                    <p className="font-medium leading-tight">{job.title}</p>
                    <p className="text-xs text-muted-foreground">
                      /{job.slug} · {job.location}
                    </p>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {job.department}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {job.company}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-muted-foreground">
                    {new Date(job.posted_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1.5">
                      <div>
                        {job.status === "open" && (
                          <Badge variant="success">{STATUS_LABEL[job.status]}</Badge>
                        )}
                        {job.status === "on_hold" && (
                          <Badge variant="warning">{STATUS_LABEL[job.status]}</Badge>
                        )}
                        {job.status === "closed" && (
                          <Badge variant="muted">{STATUS_LABEL[job.status]}</Badge>
                        )}
                      </div>
                      <JobApprovalBadge
                        approvalStatus={job.approval_status}
                        publishStatus={job.publish_status}
                        hasPendingRevision={job.has_pending_revision}
                      />
                      <JobApprovalActions
                        job={job}
                        canApprove={perms.has(PERM_HR_JOBS_APPROVE)}
                        canSubmit={perms.has(PERM_HR_JOBS_CREATE)}
                        canPublish={perms.has(PERM_HR_JOBS_PUBLISH)}
                        onUpdated={(updated) => {
                          setItems((prev) =>
                            (prev ?? []).map((j) =>
                              j.id === updated.id ? updated : j,
                            ),
                          );
                        }}
                      />
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    {busyId === job.id ? (
                      <Loader2 className="ml-auto inline h-4 w-4 animate-spin" />
                    ) : (
                      <>
                        {job.status === "open" ? (
                          <>
                            <Button
                              size="icon"
                              variant="ghost"
                              onClick={() => transition(job, "hold")}
                              aria-label="Put on hold"
                              title="Put on hold"
                            >
                              <PauseCircle className="h-4 w-4 text-amber-600" />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              onClick={() => transition(job, "close")}
                              aria-label="Close job"
                              title="Close job"
                            >
                              <XCircle className="h-4 w-4 text-rose-600" />
                            </Button>
                          </>
                        ) : (
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() => transition(job, "reopen")}
                            aria-label="Reopen job"
                            title="Reopen job"
                          >
                            <PlayCircle className="h-4 w-4 text-emerald-600" />
                          </Button>
                        )}
                        {perms.has(PERM_HR_JOBS_EDIT) && (
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() => openEdit(job)}
                            aria-label={`Edit ${job.title}`}
                          >
                            <Edit3 className="h-4 w-4" />
                          </Button>
                        )}
                        {perms.has(PERM_HR_JOBS_DELETE) && !job.is_archived && (
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() =>
                              setConfirmJob({ job, action: "archive" })
                            }
                            aria-label={`Archive ${job.title}`}
                            title="Archive (soft-delete, keeps history)"
                            className="text-amber-600 hover:text-amber-700"
                          >
                            <Archive className="h-4 w-4" />
                          </Button>
                        )}
                        {perms.has(PERM_HR_JOBS_DELETE) && job.is_archived && (
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() =>
                              setConfirmJob({ job, action: "unarchive" })
                            }
                            aria-label={`Restore ${job.title}`}
                            title="Restore from archive"
                          >
                            <ArchiveRestore className="h-4 w-4" />
                          </Button>
                        )}
                        {perms.has(PERM_HR_JOBS_DELETE) && (
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() =>
                              setConfirmJob({ job, action: "delete" })
                            }
                            aria-label={`Delete ${job.title}`}
                            title="Hard delete (cannot be undone)"
                            className="text-rose-600 hover:text-rose-700"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <JobDrawer
        open={open}
        title={editing ? "Edit job" : "New job"}
        form={form}
        onChange={setForm}
        onClose={() => setOpen(false)}
        onSave={save}
        saving={saving}
        editingJob={editing}
      />

      {confirmJob && (
        <ConfirmReasonDialog
          title={
            confirmJob.action === "delete"
              ? `Delete "${confirmJob.job.title}" permanently?`
              : confirmJob.action === "archive"
                ? `Archive "${confirmJob.job.title}"?`
                : `Restore "${confirmJob.job.title}" from archive?`
          }
          description={
            confirmJob.action === "delete"
              ? "Hard delete cannot be undone. The job and its history are removed. Prefer Archive unless the row is truly invalid (test data, duplicate, etc.)."
              : confirmJob.action === "archive"
                ? "Archive hides the job from default listings but keeps all candidates, applications, and audit history. Use Restore to bring it back."
                : "Restore makes the job visible in default listings again."
          }
          confirmLabel={
            confirmJob.action === "delete"
              ? "Delete permanently"
              : confirmJob.action === "archive"
                ? "Archive"
                : "Restore"
          }
          tone={confirmJob.action === "delete" ? "danger" : "default"}
          requireReason={confirmJob.action !== "unarchive"}
          onConfirm={(reason) =>
            performJobAction(confirmJob.job, confirmJob.action, reason)
          }
          onClose={() => setConfirmJob(null)}
        />
      )}
    </HrShell>
  );
}

function JobDrawer({
  open,
  title,
  form,
  onChange,
  onClose,
  onSave,
  saving,
  editingJob,
}: {
  open: boolean;
  title: string;
  form: JobFormState;
  onChange: (next: JobFormState) => void;
  onClose: () => void;
  onSave: () => void;
  saving: boolean;
  /**
   * The job being edited (null when creating new). Used to:
   *  - render the JobApprovalTimeline at the bottom of the drawer
   *  - show a "this edit will require re-approval" warning when the
   *    job is already approved.
   */
  editingJob: JobOpening | null;
}) {
  if (!open) return null;

  function set<K extends keyof JobFormState>(k: K, v: JobFormState[K]) {
    onChange({ ...form, [k]: v });
  }

  // Re-approval warning fires when editing an approved job; the
  // backend will route the changes through a JobRevision rather than
  // mutating the live job, so HR knows the edit won't be public until
  // the manager approves the revision.
  const showReapprovalWarning =
    editingJob !== null && editingJob.approval_status === "approved";

  return (
    <div role="dialog" aria-modal="true" className="fixed inset-0 z-40 flex">
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="flex w-full max-w-2xl flex-col bg-background shadow-2xl">
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">{title}</h2>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </header>

        <form
          className="flex flex-1 flex-col overflow-y-auto"
          onSubmit={(e) => {
            e.preventDefault();
            onSave();
          }}
        >
          <div className="flex-1 space-y-4 p-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Title" required>
                <Input
                  required
                  value={form.title}
                  onChange={(e) => set("title", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Slug" required hint="lowercase, dashes only">
                <Input
                  required
                  pattern="^[a-z0-9-]+$"
                  value={form.slug}
                  onChange={(e) => set("slug", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Department" required>
                <Input
                  required
                  value={form.department}
                  onChange={(e) => set("department", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Division">
                <Input
                  value={form.division}
                  onChange={(e) => set("division", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Company" required>
                <Input
                  required
                  value={form.company}
                  onChange={(e) => set("company", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Location" required>
                <Input
                  required
                  value={form.location}
                  onChange={(e) => set("location", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Employment type">
                <Select
                  value={form.employment_type}
                  onChange={(e) =>
                    set("employment_type", e.target.value as EmploymentType)
                  }
                  disabled={saving}
                >
                  {Object.entries(EMPLOYMENT_LABEL).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Status">
                <Select
                  value={form.status}
                  onChange={(e) => set("status", e.target.value as JobStatus)}
                  disabled={saving}
                >
                  <option value="open">Open</option>
                  <option value="on_hold">On hold</option>
                  <option value="closed">Closed</option>
                </Select>
              </Field>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Min. experience (yrs)">
                <Input
                  type="number"
                  min={0}
                  max={60}
                  value={form.min_experience}
                  onChange={(e) => set("min_experience", Number(e.target.value) || 0)}
                  disabled={saving}
                />
              </Field>
              <Field label="Max. experience (yrs)">
                <Input
                  type="number"
                  min={0}
                  max={60}
                  value={form.max_experience}
                  onChange={(e) => set("max_experience", Number(e.target.value) || 0)}
                  disabled={saving}
                />
              </Field>
              <Field label="Salary min (QAR / month)">
                <Input
                  type="number"
                  min={0}
                  value={form.salary_min}
                  onChange={(e) => set("salary_min", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Salary max (QAR / month)">
                <Input
                  type="number"
                  min={0}
                  value={form.salary_max}
                  onChange={(e) => set("salary_max", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Required education">
                <Input
                  value={form.required_education}
                  onChange={(e) => set("required_education", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Visa requirement">
                <Input
                  value={form.visa_requirement}
                  onChange={(e) => set("visa_requirement", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Nationality preference">
                <Input
                  value={form.nationality_preference}
                  onChange={(e) =>
                    set("nationality_preference", e.target.value)
                  }
                  disabled={saving}
                />
              </Field>
              <Field label="Language requirement">
                <Input
                  value={form.language_requirement}
                  onChange={(e) => set("language_requirement", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Notice period">
                <Input
                  value={form.notice_period_preference}
                  onChange={(e) =>
                    set("notice_period_preference", e.target.value)
                  }
                  disabled={saving}
                />
              </Field>
            </div>

            <Field label="Description">
              <Textarea
                rows={3}
                value={form.description}
                onChange={(e) => set("description", e.target.value)}
                disabled={saving}
              />
            </Field>

            <Field label="Responsibilities" hint="One per line">
              <Textarea
                rows={5}
                value={form.responsibilities}
                onChange={(e) => set("responsibilities", e.target.value)}
                disabled={saving}
              />
            </Field>

            <Field label="Requirements" hint="One per line">
              <Textarea
                rows={5}
                value={form.requirements}
                onChange={(e) => set("requirements", e.target.value)}
                disabled={saving}
              />
            </Field>

            <Field label="Required skills" hint="Comma-separated">
              <Input
                value={form.required_skills}
                onChange={(e) => set("required_skills", e.target.value)}
                disabled={saving}
                placeholder="Python, Sales, Retail"
              />
            </Field>

            <Field label="Preferred skills" hint="Comma-separated">
              <Input
                value={form.preferred_skills}
                onChange={(e) => set("preferred_skills", e.target.value)}
                disabled={saving}
                placeholder="Arabic, GCC experience"
              />
            </Field>

            {showReapprovalWarning && (
              <div
                role="status"
                className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-300"
              >
                <p className="font-semibold">
                  Editing an approved job — re-approval required.
                </p>
                <p className="mt-1 leading-relaxed">
                  This job is already <strong>approved &amp; live</strong>.
                  Saving will create a pending revision; the public site
                  keeps showing the current version until an HR Manager
                  approves the revision.
                </p>
              </div>
            )}

            {editingJob && (
              <section className="rounded-md border border-border/60 bg-background/40 p-3">
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Approval timeline
                </h3>
                <JobApprovalTimeline jobId={editingJob.id} />
              </section>
            )}
          </div>

          <footer className="flex items-center justify-end gap-2 border-t border-border/60 px-5 py-3">
            <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {saving ? "Saving…" : "Save"}
            </Button>
          </footer>
        </form>
      </div>
    </div>
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
    const t = setTimeout(onClose, 3000);
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
