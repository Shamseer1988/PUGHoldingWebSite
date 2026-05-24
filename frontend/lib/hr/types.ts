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
