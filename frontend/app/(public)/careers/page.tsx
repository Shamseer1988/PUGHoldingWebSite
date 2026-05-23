"use client";

import * as React from "react";

import { JobCard } from "@/components/site/job-card";
import {
  EMPTY_JOB_FILTERS,
  JobFilters,
  applyJobFilters,
  type JobFilterState,
} from "@/components/site/job-filters";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import {
  getDepartments,
  getJobCompanies,
  getJobLocations,
  getJobs,
} from "@/lib/dummy-data/jobs";

export default function CareersPage() {
  const jobs = React.useMemo(() => getJobs(), []);
  const departments = React.useMemo(() => getDepartments(), []);
  const companies = React.useMemo(() => getJobCompanies(), []);
  const locations = React.useMemo(() => getJobLocations(), []);

  const [filters, setFilters] = React.useState<JobFilterState>(
    EMPTY_JOB_FILTERS
  );
  const filtered = React.useMemo(
    () => applyJobFilters(jobs, filters),
    [jobs, filters]
  );

  return (
    <>
      <PageHero
        eyebrow="Careers"
        title="Build your career with Paris United Group"
        description="Roles across retail operations, FMCG sales, engineering, real estate, services, HR, and group functions."
        accent="from-emerald-500 via-teal-500 to-sky-500"
      />

      <Section className="pt-10">
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
            No roles match your filters yet — try clearing some filters.
          </p>
        ) : (
          <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((job) => (
              <JobCard key={job.slug} job={job} />
            ))}
          </div>
        )}
      </Section>
    </>
  );
}
