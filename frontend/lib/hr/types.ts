/**
 * TypeScript mirrors of the Phase 8 HR ATS schemas.
 */

export interface StatItem {
  key: string;
  label: string;
  value: number;
}

export interface FunnelStage {
  status: string;
  label: string;
  count: number;
}

export interface MonthlyCount {
  month: string;
  count: number;
}

export interface NamedCount {
  name: string;
  count: number;
}

export type InterviewMode = "online" | "phone" | "in_person";

export interface InterviewSummary {
  id: number;
  candidate_name: string;
  job_title: string | null;
  round_name: string;
  scheduled_at: string;
  interviewer_name: string | null;
  mode: InterviewMode;
}

export type OfferStatus =
  | "draft"
  | "sent"
  | "accepted"
  | "declined"
  | "withdrawn"
  | "joined";

export interface OfferSummary {
  id: number;
  candidate_name: string;
  job_title: string | null;
  salary_offered: number | null;
  status: OfferStatus;
  sent_at: string | null;
}

export interface DashboardSummary {
  stats: StatItem[];
  pipeline_funnel: FunnelStage[];
  applications_per_month: MonthlyCount[];
  candidates_by_job: NamedCount[];
  candidates_by_department: NamedCount[];
  pending_interviews: InterviewSummary[];
  pending_offers: OfferSummary[];
}

// Job openings -----------------------------------------------------------

export type JobStatus = "open" | "on_hold" | "closed";
export type EmploymentType = "full_time" | "part_time" | "contract";

export interface JobOpening {
  id: number;
  slug: string;
  title: string;
  department: string;
  division: string | null;
  company: string;
  location: string;
  employment_type: EmploymentType;
  min_experience: number;
  max_experience: number;
  required_education: string | null;
  salary_min: number | null;
  salary_max: number | null;
  visa_requirement: string | null;
  nationality_preference: string | null;
  language_requirement: string | null;
  notice_period_preference: string | null;
  description: string | null;
  responsibilities: string | null;
  requirements: string | null;
  required_skills: string | null;
  preferred_skills: string | null;
  status: JobStatus;
  posted_at: string;
  closed_at: string | null;
  created_by_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface HrAuditEntry {
  id: number;
  action: string;
  scope: string | null;
  actor_id: number | null;
  actor_email: string | null;
  target_type: string | null;
  target_id: string | null;
  ip_address: string | null;
  details: Record<string, unknown> | null;
  created_at: string | null;
}
