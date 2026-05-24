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

// Candidates (Phase 10) ---------------------------------------------------

export interface CandidateListItem {
  id: number;
  full_name: string;
  email: string | null;
  mobile: string | null;
  current_designation: string | null;
  total_experience_years: number | null;
  source: string | null;
  is_blacklisted: boolean;
  is_archived: boolean;
  created_at: string;
}

export interface CandidateDocument {
  id: number;
  filename: string;
  file_path: string;
  mime_type: string | null;
  file_size: number | null;
  file_hash: string | null;
  is_primary: boolean;
  uploaded_by_id: number | null;
  created_at: string;
}

export interface ParsedEducationEntry {
  raw: string;
  degree: string | null;
  institution: string | null;
  year: number | null;
}

export interface ParsedCompanyEntry {
  name: string;
  title: string | null;
  duration: string | null;
}

export interface CandidateExtractedData {
  skills: string | null;
  education: ParsedEducationEntry[] | null;
  certifications: string[] | null;
  languages: string[] | null;
  previous_companies: ParsedCompanyEntry[] | null;
  full_text: string | null;
  parser_version: string | null;
  updated_at: string | null;
}

export interface Candidate {
  id: number;
  full_name: string;
  email: string | null;
  mobile: string | null;
  nationality: string | null;
  current_location: string | null;
  current_designation: string | null;
  current_company: string | null;
  total_experience_years: number | null;
  gcc_experience_years: number | null;
  qatar_experience_years: number | null;
  expected_salary: number | null;
  notice_period: string | null;
  visa_status: string | null;
  availability: string | null;
  is_blacklisted: boolean;
  is_archived: boolean;
  source: string | null;
  created_at: string;
  updated_at: string;
  documents: CandidateDocument[];
  extracted_data: CandidateExtractedData | null;
}

export interface CvReparseResult {
  candidate: Candidate;
  parsed: boolean;
  parser_version: string | null;
  detail: string | null;
}

export interface ApplicationSubmissionResponse {
  candidate_id: number;
  application_id: number;
  was_existing_candidate: boolean;
  job_title: string | null;
  job_slug: string | null;
}

export interface BulkUploadSkip {
  name: string;
  reason: string;
}

export interface BulkUploadResult {
  total_files: number;
  created_candidates: number;
  matched_existing_candidates: number;
  duplicate_applications_skipped: number;
  skipped_files: BulkUploadSkip[];
  candidate_ids: number[];
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
