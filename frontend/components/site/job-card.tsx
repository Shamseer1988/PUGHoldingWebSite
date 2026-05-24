import Link from "next/link";
import { ArrowUpRight, Briefcase, Clock, MapPin } from "lucide-react";

import { GlassCard } from "@/components/site/glass-card";
import { Badge } from "@/components/ui/badge";
import {
  EMPLOYMENT_TYPE_LABELS,
  splitSkills,
  type PublicJob,
} from "@/lib/public-api";

interface JobCardProps {
  job: PublicJob;
}

export function JobCard({ job }: JobCardProps) {
  const requiredSkills = splitSkills(job.required_skills);

  return (
    <Link href={`/careers/${job.slug}`} className="group block h-full">
      <GlassCard className="flex h-full flex-col p-5 transition-transform group-hover:-translate-y-1">
        <div className="flex items-start justify-between gap-3">
          <Badge variant="soft">{job.department}</Badge>
          <Badge variant="muted">{EMPLOYMENT_TYPE_LABELS[job.employment_type]}</Badge>
        </div>

        <h3 className="mt-3 text-lg font-semibold leading-snug tracking-tight">
          {job.title}
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">{job.company}</p>

        <ul className="mt-4 space-y-1.5 text-xs text-muted-foreground">
          <li className="inline-flex items-center gap-1.5">
            <MapPin className="h-3.5 w-3.5" />
            {job.location}
          </li>
          <li className="inline-flex items-center gap-1.5">
            <Briefcase className="h-3.5 w-3.5" />
            {job.min_experience}–{job.max_experience} years
          </li>
          <li className="inline-flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            Posted{" "}
            {new Date(job.posted_at).toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}
          </li>
        </ul>

        {requiredSkills.length > 0 && (
          <ul className="mt-4 flex flex-wrap gap-1.5">
            {requiredSkills.slice(0, 4).map((skill) => (
              <li key={skill}>
                <Badge variant="outline" className="font-normal">
                  {skill}
                </Badge>
              </li>
            ))}
          </ul>
        )}

        <span className="mt-auto inline-flex items-center gap-1 pt-5 text-sm font-medium text-primary">
          View role
          <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
        </span>
      </GlassCard>
    </Link>
  );
}
