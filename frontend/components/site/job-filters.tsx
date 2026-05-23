"use client";

import * as React from "react";
import { Search, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  EMPLOYMENT_TYPE_LABELS,
  type EmploymentType,
  type JobOpening,
} from "@/lib/dummy-data/jobs";

export interface JobFilterState {
  query: string;
  department: string;
  company: string;
  location: string;
  employmentType: EmploymentType | "";
}

export const EMPTY_JOB_FILTERS: JobFilterState = {
  query: "",
  department: "",
  company: "",
  location: "",
  employmentType: "",
};

interface JobFiltersProps {
  value: JobFilterState;
  onChange: (next: JobFilterState) => void;
  departments: string[];
  companies: string[];
  locations: string[];
}

export function JobFilters({
  value,
  onChange,
  departments,
  companies,
  locations,
}: JobFiltersProps) {
  function set<K extends keyof JobFilterState>(key: K, v: JobFilterState[K]) {
    onChange({ ...value, [key]: v });
  }

  const hasFilters =
    value.query ||
    value.department ||
    value.company ||
    value.location ||
    value.employmentType;

  return (
    <div className="rounded-2xl border border-border/60 bg-background/60 p-4 backdrop-blur sm:p-5">
      <div className="grid gap-3 lg:grid-cols-[1.5fr_repeat(4,1fr)_auto] lg:items-end">
        <div className="space-y-1.5">
          <Label htmlFor="job-query">Search</Label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="job-query"
              placeholder="Job title or skill"
              value={value.query}
              onChange={(e) => set("query", e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        <FilterSelect
          id="job-department"
          label="Department"
          value={value.department}
          onChange={(v) => set("department", v)}
          options={departments}
        />
        <FilterSelect
          id="job-company"
          label="Company"
          value={value.company}
          onChange={(v) => set("company", v)}
          options={companies}
        />
        <FilterSelect
          id="job-location"
          label="Location"
          value={value.location}
          onChange={(v) => set("location", v)}
          options={locations}
        />

        <div className="space-y-1.5">
          <Label htmlFor="job-type">Type</Label>
          <Select
            id="job-type"
            value={value.employmentType}
            onChange={(e) =>
              set("employmentType", e.target.value as EmploymentType | "")
            }
          >
            <option value="">All</option>
            {Object.entries(EMPLOYMENT_TYPE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </Select>
        </div>

        <Button
          type="button"
          variant="outline"
          onClick={() => onChange(EMPTY_JOB_FILTERS)}
          disabled={!hasFilters}
          className="self-end"
        >
          <X className="h-4 w-4" />
          Reset
        </Button>
      </div>
    </div>
  );
}

function FilterSelect({
  id,
  label,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </Select>
    </div>
  );
}

export function applyJobFilters(
  jobs: JobOpening[],
  filters: JobFilterState
): JobOpening[] {
  const q = filters.query.trim().toLowerCase();
  return jobs.filter((job) => {
    if (filters.department && job.department !== filters.department) return false;
    if (filters.company && job.company !== filters.company) return false;
    if (filters.location && job.location !== filters.location) return false;
    if (
      filters.employmentType &&
      job.employmentType !== filters.employmentType
    )
      return false;
    if (q) {
      const haystack = [
        job.title,
        job.company,
        job.department,
        job.location,
        ...job.requiredSkills,
        ...(job.preferredSkills ?? []),
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });
}
