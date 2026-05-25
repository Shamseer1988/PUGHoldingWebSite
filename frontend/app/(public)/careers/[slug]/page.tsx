import { notFound } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Briefcase,
  Building2,
  CalendarDays,
  Clock,
  GraduationCap,
  MapPin,
} from "lucide-react";

import { ApplyForm } from "@/components/site/apply-form";
import { GlassCard } from "@/components/site/glass-card";
import { PageHero } from "@/components/site/page-hero";
import { Section } from "@/components/site/section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  EMPLOYMENT_TYPE_LABELS,
  getPublicJobBySlug,
  getPublicJobs,
  splitLines,
  splitSkills,
} from "@/lib/public-api";

export const revalidate = 60;

export async function generateStaticParams() {
  const jobs = await getPublicJobs();
  return jobs.map((j) => ({ slug: j.slug }));
}

interface JobDetailPageProps {
  params: { slug: string };
}

export async function generateMetadata({ params }: JobDetailPageProps) {
  const job = await getPublicJobBySlug(params.slug);
  return {
    title: job ? job.title : "Job not found",
    description: job?.description ?? undefined,
  };
}

export default async function JobDetailPage({ params }: JobDetailPageProps) {
  const job = await getPublicJobBySlug(params.slug);
  if (!job) notFound();

  const responsibilities = splitLines(job.responsibilities);
  const requirements = splitLines(job.requirements);
  const requiredSkills = splitSkills(job.required_skills);
  const preferredSkills = splitSkills(job.preferred_skills);

  return (
    <>
      <PageHero
        eyebrow={job.department}
        title={job.title}
        description={job.description ?? undefined}
        accent="from-pug-green-500 via-pug-gold-500 to-pug-gold-700"
      >
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="muted" className="inline-flex items-center gap-1">
            <Building2 className="h-3 w-3" />
            {job.company}
          </Badge>
          <Badge variant="muted" className="inline-flex items-center gap-1">
            <MapPin className="h-3 w-3" />
            {job.location}
          </Badge>
          <Badge variant="muted" className="inline-flex items-center gap-1">
            <Briefcase className="h-3 w-3" />
            {job.min_experience}–{job.max_experience} years
          </Badge>
          <Badge variant="muted">
            {EMPLOYMENT_TYPE_LABELS[job.employment_type]}
          </Badge>
        </div>
      </PageHero>

      <Section className="pt-12">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[2fr_1fr]">
          <div className="space-y-6">
            {responsibilities.length > 0 && (
              <GlassCard className="p-6 sm:p-8">
                <h2 className="text-xl font-semibold tracking-tight">
                  Responsibilities
                </h2>
                <ul className="mt-4 space-y-2 text-sm text-foreground/90">
                  {responsibilities.map((r) => (
                    <li
                      key={r}
                      className="flex items-start gap-2 before:mt-2 before:inline-block before:h-1.5 before:w-1.5 before:shrink-0 before:rounded-full before:bg-primary"
                    >
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </GlassCard>
            )}

            <GlassCard className="p-6 sm:p-8">
              <h2 className="text-xl font-semibold tracking-tight">
                Requirements
              </h2>
              {requirements.length > 0 && (
                <ul className="mt-4 space-y-2 text-sm text-foreground/90">
                  {requirements.map((r) => (
                    <li
                      key={r}
                      className="flex items-start gap-2 before:mt-2 before:inline-block before:h-1.5 before:w-1.5 before:shrink-0 before:rounded-full before:bg-primary"
                    >
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              )}

              {requiredSkills.length > 0 && (
                <>
                  <h3 className="mt-6 text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    Required skills
                  </h3>
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {requiredSkills.map((skill) => (
                      <li key={skill}>
                        <Badge variant="soft" className="font-normal">
                          {skill}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {preferredSkills.length > 0 && (
                <>
                  <h3 className="mt-5 text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    Nice to have
                  </h3>
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {preferredSkills.map((skill) => (
                      <li key={skill}>
                        <Badge variant="outline" className="font-normal">
                          {skill}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </GlassCard>

            <GlassCard className="p-6 sm:p-8" id="apply">
              <h2 className="text-xl font-semibold tracking-tight">
                Apply for this role
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Fill in the form below. Your CV will be reviewed by our HR team.
              </p>
              <div className="mt-6">
                <ApplyForm jobTitle={job.title} jobSlug={job.slug} />
              </div>
            </GlassCard>
          </div>

          <aside className="space-y-4">
            <GlassCard className="p-6">
              <h3 className="text-base font-semibold">Quick facts</h3>
              <ul className="mt-4 space-y-3 text-sm">
                <Fact
                  icon={<Building2 className="h-4 w-4" />}
                  label="Company"
                  value={job.company}
                />
                <Fact
                  icon={<MapPin className="h-4 w-4" />}
                  label="Location"
                  value={job.location}
                />
                <Fact
                  icon={<Briefcase className="h-4 w-4" />}
                  label="Experience"
                  value={`${job.min_experience}–${job.max_experience} years`}
                />
                {job.required_education && (
                  <Fact
                    icon={<GraduationCap className="h-4 w-4" />}
                    label="Education"
                    value={job.required_education}
                  />
                )}
                <Fact
                  icon={<Clock className="h-4 w-4" />}
                  label="Employment"
                  value={EMPLOYMENT_TYPE_LABELS[job.employment_type]}
                />
                <Fact
                  icon={<CalendarDays className="h-4 w-4" />}
                  label="Posted"
                  value={new Date(job.posted_at).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                />
              </ul>
              <Button asChild className="mt-5 w-full">
                <Link href={`#apply`}>Apply now</Link>
              </Button>
            </GlassCard>

            <GlassCard className="p-6">
              <h3 className="text-base font-semibold">All roles</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Browse every open position across Paris United Group.
              </p>
              <Button asChild variant="outline" className="mt-5 w-full">
                <Link href="/careers">
                  <ArrowLeft className="h-4 w-4" />
                  Back to careers
                </Link>
              </Button>
            </GlassCard>
          </aside>
        </div>
      </Section>
    </>
  );
}

function Fact({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="break-words font-medium">{value}</p>
      </div>
    </li>
  );
}
