"use client";

import * as React from "react";
import { ArrowDown, ArrowUp, ClipboardList, Loader2 } from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { SubmissionReviewDrawer } from "@/components/hr/submission-review-drawer";
import { Badge } from "@/components/ui/badge";
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
import type {
  AssessmentSummary,
  AssessmentSubmissionListItem,
  AssessmentSubmissionListResponse,
  JobOption,
} from "@/lib/hr/types";

const INVITE_STATUSES = ["submitted", "opened", "expired", "cancelled"];
const PAGE_SIZE = 25;

interface Filters {
  template_id: string;
  job_id: string;
  status: string;
  candidate_query: string;
  submitted_from: string;
  submitted_to: string;
  min_score: string;
  max_score: string;
}

const EMPTY_FILTERS: Filters = {
  template_id: "",
  job_id: "",
  status: "",
  candidate_query: "",
  submitted_from: "",
  submitted_to: "",
  min_score: "",
  max_score: "",
};

export default function HrAssessmentSubmissionsPage() {
  const [filters, setFilters] = React.useState<Filters>(EMPTY_FILTERS);
  const [sortBy, setSortBy] = React.useState<"submitted_at" | "score">(
    "submitted_at",
  );
  const [sortDir, setSortDir] = React.useState<"asc" | "desc">("desc");
  const [page, setPage] = React.useState(1);
  const [data, setData] =
    React.useState<AssessmentSubmissionListResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [templates, setTemplates] = React.useState<AssessmentSummary[]>([]);
  const [jobs, setJobs] = React.useState<JobOption[]>([]);
  const [open, setOpen] = React.useState<{
    inviteId: number;
    assessmentId: number;
    candidateName: string;
  } | null>(null);

  React.useEffect(() => {
    hrApi
      .get<{ items: AssessmentSummary[] }>("/hr/assessments")
      .then((r) => setTemplates(r.items))
      .catch(() => setTemplates([]));
    hrApi
      .get<JobOption[]>("/hr/reports/options/jobs")
      .then(setJobs)
      .catch(() => setJobs([]));
  }, []);

  const refresh = React.useCallback(async () => {
    setData(null);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filters.template_id) params.set("template_id", filters.template_id);
      if (filters.job_id) params.set("job_id", filters.job_id);
      if (filters.status) params.set("status", filters.status);
      if (filters.candidate_query)
        params.set("candidate_query", filters.candidate_query.trim());
      if (filters.submitted_from)
        params.set("submitted_from", `${filters.submitted_from}T00:00:00`);
      if (filters.submitted_to)
        params.set("submitted_to", `${filters.submitted_to}T23:59:59`);
      if (filters.min_score) params.set("min_score", filters.min_score);
      if (filters.max_score) params.set("max_score", filters.max_score);
      params.set("sort_by", sortBy);
      params.set("sort_dir", sortDir);
      params.set("page", String(page));
      params.set("page_size", String(PAGE_SIZE));
      setData(
        await hrApi.get<AssessmentSubmissionListResponse>(
          `/hr/assessments/submissions?${params}`,
        ),
      );
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }, [filters, sortBy, sortDir, page]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  function toggleScoreSort() {
    if (sortBy === "score") {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy("score");
      setSortDir("desc");
    }
    setPage(1);
  }

  function set<K extends keyof Filters>(key: K, value: string) {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <HrShell
      title="Assessment submissions"
      description="Every candidate-submitted assessment across all templates."
    >
      {/* Filters */}
      <div className="mb-4 grid gap-3 rounded-xl border border-border/60 bg-card p-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Template">
          <Select
            value={filters.template_id}
            onChange={(e) => set("template_id", e.target.value)}
          >
            <option value="">All templates</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.title}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Job">
          <Select
            value={filters.job_id}
            onChange={(e) => set("job_id", e.target.value)}
          >
            <option value="">All jobs</option>
            {jobs.map((j) => (
              <option key={j.slug} value={String(j.slug)}>
                {j.title}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Invite status">
          <Select
            value={filters.status}
            onChange={(e) => set("status", e.target.value)}
          >
            <option value="">All statuses</option>
            {INVITE_STATUSES.map((s) => (
              <option key={s} value={s} className="capitalize">
                {s}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Candidate">
          <Input
            value={filters.candidate_query}
            onChange={(e) => set("candidate_query", e.target.value)}
            placeholder="Name or email"
          />
        </Field>
        <Field label="Submitted from">
          <Input
            type="date"
            value={filters.submitted_from}
            onChange={(e) => set("submitted_from", e.target.value)}
          />
        </Field>
        <Field label="Submitted to">
          <Input
            type="date"
            value={filters.submitted_to}
            onChange={(e) => set("submitted_to", e.target.value)}
          />
        </Field>
        <Field label="Min score">
          <Input
            type="number"
            value={filters.min_score}
            onChange={(e) => set("min_score", e.target.value)}
            placeholder="0"
          />
        </Field>
        <Field label="Max score">
          <Input
            type="number"
            value={filters.max_score}
            onChange={(e) => set("max_score", e.target.value)}
            placeholder="—"
          />
        </Field>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-3 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {data === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
          Loading submissions…
        </p>
      ) : data.items.length === 0 ? (
        <HrEmptyState
          icon={ClipboardList}
          title="No submissions match the current filter"
          description="Candidate-submitted assessments will appear here, newest first."
        />
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Candidate</TableHead>
                  <TableHead className="hidden md:table-cell">Job</TableHead>
                  <TableHead className="hidden lg:table-cell">
                    Template
                  </TableHead>
                  <TableHead className="w-24">Status</TableHead>
                  <TableHead className="w-24">
                    <button
                      type="button"
                      onClick={toggleScoreSort}
                      className="inline-flex items-center gap-1 font-medium hover:text-foreground"
                    >
                      Score
                      {sortBy === "score" &&
                        (sortDir === "desc" ? (
                          <ArrowDown className="h-3 w-3" />
                        ) : (
                          <ArrowUp className="h-3 w-3" />
                        ))}
                    </button>
                  </TableHead>
                  <TableHead className="hidden sm:table-cell w-40">
                    Submitted
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((row) => (
                  <SubmissionRow
                    key={row.invite_id}
                    row={row}
                    onOpen={() =>
                      setOpen({
                        inviteId: row.invite_id,
                        assessmentId: row.assessment_id,
                        candidateName: row.candidate_name,
                      })
                    }
                  />
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="mt-3 flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {data.total} submission{data.total === 1 ? "" : "s"}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <span className="tabular-nums">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}

      {open && (
        <SubmissionReviewDrawer
          inviteId={open.inviteId}
          assessmentId={open.assessmentId}
          candidateName={open.candidateName}
          onClose={() => setOpen(null)}
        />
      )}
    </HrShell>
  );
}

function SubmissionRow({
  row,
  onOpen,
}: {
  row: AssessmentSubmissionListItem;
  onOpen: () => void;
}) {
  return (
    <TableRow
      onClick={onOpen}
      className="cursor-pointer transition-colors hover:bg-muted/40"
    >
      <TableCell>
        <p className="font-medium leading-tight">{row.candidate_name}</p>
        {row.candidate_email && (
          <p className="text-xs text-muted-foreground">{row.candidate_email}</p>
        )}
      </TableCell>
      <TableCell className="hidden md:table-cell text-sm">
        {row.job_title ?? "—"}
      </TableCell>
      <TableCell className="hidden lg:table-cell text-sm">
        {row.assessment_title}
      </TableCell>
      <TableCell>
        <Badge variant="muted" className="capitalize">
          {row.invite_status}
        </Badge>
      </TableCell>
      <TableCell className="tabular-nums">
        {row.score ?? "—"}
        {row.max_score != null && (
          <span className="text-muted-foreground"> / {row.max_score}</span>
        )}
      </TableCell>
      <TableCell className="hidden sm:table-cell text-xs text-muted-foreground">
        {row.submitted_at
          ? new Date(row.submitted_at).toLocaleString()
          : "—"}
      </TableCell>
    </TableRow>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <Label className="text-xs uppercase tracking-wider text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}
