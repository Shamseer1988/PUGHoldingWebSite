"use client";

import * as React from "react";
import { Filter, RotateCcw, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { hrApi } from "@/lib/hr/api";
import type {
  CandidateAdvancedFilters,
  JobOption,
} from "@/lib/hr/types";
import { cn } from "@/lib/utils";


/**
 * Advanced HR search panel.
 *
 * Used by:
 *   - /hr/candidates  (collapsible drawer above the table)
 *   - /hr/reports     (filter card next to every report runner)
 *
 * Stays controlled: receives the current `value` filter bundle and
 * pushes changes through `onChange`. Job + department dropdowns load
 * from /hr/reports/options once on mount.
 */


const STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "cv_received", label: "CV Received" },
  { value: "ai_reviewed", label: "AI Reviewed" },
  { value: "hr_review_pending", label: "HR Review Pending" },
  { value: "shortlisted", label: "Shortlisted" },
  { value: "first_interview", label: "First Interview" },
  { value: "technical_interview", label: "Technical Interview" },
  { value: "final_interview", label: "Final Interview" },
  { value: "selected", label: "Selected" },
  { value: "offer_sent", label: "Offer Sent" },
  { value: "joined", label: "Joined" },
  { value: "rejected", label: "Rejected" },
  { value: "blacklisted", label: "Blacklisted" },
];


interface CandidateFilterPanelProps {
  value: CandidateAdvancedFilters;
  onChange: (next: CandidateAdvancedFilters) => void;
  onApply: () => void;
  onReset: () => void;
  /** Optional className for the outer card wrapper. */
  className?: string;
  /** When true, the action bar (Apply / Reset) is rendered. */
  showActions?: boolean;
}


export function CandidateFilterPanel({
  value,
  onChange,
  onApply,
  onReset,
  className,
  showActions = true,
}: CandidateFilterPanelProps) {
  const [jobs, setJobs] = React.useState<JobOption[]>([]);
  const [departments, setDepartments] = React.useState<string[]>([]);

  React.useEffect(() => {
    let cancelled = false;
    Promise.all([
      hrApi.get<JobOption[]>("/hr/reports/options/jobs"),
      hrApi.get<string[]>("/hr/reports/options/departments"),
    ])
      .then(([j, d]) => {
        if (cancelled) return;
        setJobs(j);
        setDepartments(d);
      })
      .catch(() => {
        // Silent — the dropdowns just stay empty. Free-text Search,
        // Skill, Education etc. still cover the same intent.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function set<K extends keyof CandidateAdvancedFilters>(
    key: K,
    next: CandidateAdvancedFilters[K]
  ) {
    onChange({ ...value, [key]: next });
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onApply();
      }}
      className={cn(
        "space-y-4 rounded-2xl border border-border/60 bg-card p-4 sm:p-5",
        className
      )}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <FilterField label="Search">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={value.q ?? ""}
              onChange={(e) => set("q", e.target.value)}
              placeholder="Name, email, or mobile"
              className="pl-9"
            />
          </div>
        </FilterField>

        <FilterField label="Job">
          <Select
            value={value.job_slug ?? ""}
            onChange={(e) => set("job_slug", e.target.value || undefined)}
          >
            <option value="">Any job</option>
            {jobs.map((j) => (
              <option key={j.slug} value={j.slug}>
                {j.title}
                {j.department ? ` — ${j.department}` : ""}
              </option>
            ))}
          </Select>
        </FilterField>

        <FilterField label="Department">
          <Select
            value={value.department ?? ""}
            onChange={(e) => set("department", e.target.value || undefined)}
          >
            <option value="">Any department</option>
            {departments.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </Select>
        </FilterField>

        <FilterField label="Status">
          <Select
            value={value.status ?? ""}
            onChange={(e) => set("status", e.target.value || undefined)}
          >
            <option value="">Any status</option>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
        </FilterField>

        <FilterField label="Experience (yrs)">
          <RangePair
            min={value.experience_min}
            max={value.experience_max}
            step="0.5"
            onMinChange={(n) => set("experience_min", n)}
            onMaxChange={(n) => set("experience_max", n)}
          />
        </FilterField>

        <FilterField label="Score">
          <RangePair
            min={value.score_min}
            max={value.score_max}
            step="1"
            onMinChange={(n) => set("score_min", n)}
            onMaxChange={(n) => set("score_max", n)}
          />
        </FilterField>

        <FilterField label="Expected salary">
          <RangePair
            min={value.salary_min}
            max={value.salary_max}
            step="500"
            onMinChange={(n) => set("salary_min", n)}
            onMaxChange={(n) => set("salary_max", n)}
          />
        </FilterField>

        <FilterField label="Nationality">
          <Input
            value={value.nationality ?? ""}
            onChange={(e) => set("nationality", e.target.value)}
            placeholder="e.g. Filipino"
          />
        </FilterField>

        <FilterField label="Location">
          <Input
            value={value.location ?? ""}
            onChange={(e) => set("location", e.target.value)}
            placeholder="e.g. Doha"
          />
        </FilterField>

        <FilterField label="Visa">
          <Input
            value={value.visa ?? ""}
            onChange={(e) => set("visa", e.target.value)}
            placeholder="e.g. transferable NOC"
          />
        </FilterField>

        <FilterField label="Notice period">
          <Input
            value={value.notice_period ?? ""}
            onChange={(e) => set("notice_period", e.target.value)}
            placeholder="e.g. 1 month"
          />
        </FilterField>

        <FilterField label="Skill">
          <Input
            value={value.skill ?? ""}
            onChange={(e) => set("skill", e.target.value)}
            placeholder="e.g. MEP"
          />
        </FilterField>

        <FilterField label="Language">
          <Input
            value={value.language ?? ""}
            onChange={(e) => set("language", e.target.value)}
            placeholder="e.g. Arabic"
          />
        </FilterField>

        <FilterField label="Education">
          <Input
            value={value.education ?? ""}
            onChange={(e) => set("education", e.target.value)}
            placeholder="e.g. MBA"
          />
        </FilterField>

        <FilterField label="Uploaded from">
          <Input
            type="date"
            value={value.uploaded_from ?? ""}
            onChange={(e) => set("uploaded_from", e.target.value || undefined)}
          />
        </FilterField>

        <FilterField label="Uploaded to">
          <Input
            type="date"
            value={value.uploaded_to ?? ""}
            onChange={(e) => set("uploaded_to", e.target.value || undefined)}
          />
        </FilterField>
      </div>

      <label className="flex items-center gap-2 text-xs text-muted-foreground">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
          checked={value.include_archived ?? false}
          onChange={(e) => set("include_archived", e.target.checked)}
        />
        Include archived candidates
      </label>

      {showActions && (
        <div className="flex items-center justify-between gap-2 border-t border-border/40 pt-3">
          <Button type="button" variant="ghost" size="sm" onClick={onReset}>
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </Button>
          <Button type="submit" size="sm">
            <Filter className="h-3.5 w-3.5" />
            Apply filters
          </Button>
        </div>
      )}
    </form>
  );
}


// ---------------------------------------------------------------------------
// Small reusable filter field — keeps consistent label + spacing
// ---------------------------------------------------------------------------


function FilterField({
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


function RangePair({
  min,
  max,
  step = "1",
  onMinChange,
  onMaxChange,
}: {
  min: number | "" | undefined;
  max: number | "" | undefined;
  step?: string;
  onMinChange: (next: number | "") => void;
  onMaxChange: (next: number | "") => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <Input
        type="number"
        step={step}
        value={min ?? ""}
        onChange={(e) =>
          onMinChange(e.target.value === "" ? "" : Number(e.target.value))
        }
        placeholder="Min"
        className="w-full"
      />
      <span className="text-xs text-muted-foreground">to</span>
      <Input
        type="number"
        step={step}
        value={max ?? ""}
        onChange={(e) =>
          onMaxChange(e.target.value === "" ? "" : Number(e.target.value))
        }
        placeholder="Max"
        className="w-full"
      />
    </div>
  );
}


/**
 * Helper that strips empty values + adds "include_archived" only when
 * true, ready for URLSearchParams.
 */
export function filtersToQueryParams(
  filters: CandidateAdvancedFilters
): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, raw] of Object.entries(filters)) {
    if (raw === undefined || raw === null || raw === "") continue;
    if (key === "include_archived") {
      if (raw === true) params.set(key, "true");
      continue;
    }
    params.set(key, String(raw));
  }
  return params;
}
