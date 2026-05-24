"use client";

import * as React from "react";

import { JobCard } from "@/components/site/job-card";
import {
  EMPTY_JOB_FILTERS,
  JobFilters,
  applyJobFilters,
  deriveDepartments,
  deriveJobCompanies,
  deriveJobLocations,
  type JobFilterState,
} from "@/components/site/job-filters";
import type { PublicJob } from "@/lib/public-api";

interface CareersViewProps {
  jobs: PublicJob[];
}

/**
 * Client-side filter + list for the careers page. Server component
 * fetches the full open-job list once and hands it down; filtering
 * happens in memory.
 */
export function CareersView({ jobs }: CareersViewProps) {
  const departments = React.useMemo(() => deriveDepartments(jobs), [jobs]);
  const companies = React.useMemo(() => deriveJobCompanies(jobs), [jobs]);
  const locations = React.useMemo(() => deriveJobLocations(jobs), [jobs]);

  const [filters, setFilters] = React.useState<JobFilterState>(
    EMPTY_JOB_FILTERS
  );
  const filtered = React.useMemo(
    () => applyJobFilters(jobs, filters),
    [jobs, filters]
  );

  return (
    <>
      <JobFilters
        value={filters}
        onChange={setFilters}
        departments={departments}
        companies={companies}
        locations={locations}
      />

      <div className="mt-8 flex flex-wrap items-baseline justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Showing{" "}
          <span className="font-semibold text-foreground">
            {filtered.length}
          </span>{" "}
          of {jobs.length} open roles.
        </p>
      </div>

      {filtered.length === 0 ? (
        <p className="mt-8 text-center text-muted-foreground">
          {jobs.length === 0
            ? "No open roles right now — check back soon."
            : "No roles match your filters yet — try clearing some filters."}
        </p>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((job) => (
            <JobCard key={job.slug} job={job} />
          ))}
        </div>
      )}
    </>
  );
}
