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
  top_score: number | null;
  latest_status: string | null;
  latest_status_label: string | null;
}

// Phase 16 — advanced search filters ------------------------------------

export interface CandidateAdvancedFilters {
  q?: string;
  nationality?: string;
  location?: string;
  experience_min?: number | "";
  experience_max?: number | "";
  salary_min?: number | "";
  salary_max?: number | "";
  visa?: string;
  notice_period?: string;
  education?: string;
  language?: string;
  skill?: string;
  job_slug?: string;
  department?: string;
  status?: string;
  score_min?: number | "";
  score_max?: number | "";
  uploaded_from?: string;
  uploaded_to?: string;
  include_archived?: boolean;
}

// Phase 16 — reports ----------------------------------------------------

export interface ReportType {
  key: string;
  title: string;
  description: string;
  icon: string;
}

export interface ReportResponse {
  type: string;
  title: string;
  description: string;
  generated_at: string;
  columns: string[];
  rows: (string | number | null)[][];
  summary: Record<string, string | number>;
}

export interface JobOption {
  slug: string;
  title: string;
  department: string | null;
}

export interface CandidateScoreBreakdown {
  relevant_experience: number;
  required_skills: number;
  education: number;
  industry_experience: number;
  gcc_qatar_experience: number;
  salary_fit: number;
  notice_period: number;
  visa_status: number;
  language_match: number;
  notes: Record<string, string> | null;
}

export interface CandidateScore {
  id: number;
  application_id: number;
  total: number;
  is_manual_override: boolean;
  override_reason: string | null;
  overridden_by_id: number | null;
  overridden_at: string | null;
  breakdown: CandidateScoreBreakdown | null;
  updated_at: string | null;
}

export type AIRecommendation =
  | "strong_fit"
  | "possible_fit"
  | "weak_fit"
  | "needs_more_info";

export interface CandidateAIReviewPreview {
  id: number;
  recommendation: AIRecommendation | string | null;
  model_name: string | null;
  generated_at: string;
  updated_at: string | null;
}

export interface CandidateAIReview {
  id: number;
  application_id: number;
  summary: string | null;
  strengths: string | null;
  weaknesses: string | null;
  missing_information: string | null;
  risk_points: string | null;
  suggested_questions: string | null;
  recommendation: AIRecommendation | string | null;
  model_name: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  generated_at: string;
  updated_at: string | null;
}

export interface AIReviewGenerateResult {
  review: CandidateAIReview;
  mode: "disabled" | "mock" | "live" | string;
  model_name: string | null;
}

export interface AISettings {
  id: number;
  mode: "disabled" | "mock" | "live";
  azure_endpoint: string | null;
  azure_deployment: string | null;
  azure_api_version: string | null;
  model_name: string | null;
  temperature: number;
  max_output_tokens: number;
  request_timeout_seconds: number;
  extra_system_prompt: string | null;
  updated_by_id: number | null;
  updated_at: string | null;
  has_azure_api_key: boolean;
  effective_mode: string | null;
}

export interface CandidateApplicationSummary {
  id: number;
  status: string;
  status_label: string | null;
  job_opening_id: number | null;
  job_title: string | null;
  applied_at: string;
  source: string | null;
  last_rejection_reason: string | null;
  score: CandidateScore | null;
  ai_review: CandidateAIReviewPreview | null;
  history_count: number;
  allowed_next_statuses: string[];
  interviews: InterviewSummaryForApplication[];
  interview_count: number;
  next_interview_at: string | null;
}

export interface CandidateStatusHistoryEntry {
  id: number;
  application_id: number;
  old_status: string | null;
  new_status: string;
  changed_by_id: number | null;
  changed_by_email: string | null;
  remarks: string | null;
  rejection_reason: string | null;
  blacklist_approval: string | null;
  created_at: string;
}

export interface StatusOption {
  value: string;
  label: string;
  is_final: boolean;
}

export interface StatusPipelineMeta {
  statuses: StatusOption[];
  transitions: Record<string, string[]>;
}

export interface CandidateStatusChangePayload {
  new_status: string;
  remarks?: string | null;
  rejection_reason?: string | null;
  blacklist_approval?: string | null;
}

// Interview management ---------------------------------------------------

export type InterviewStatus =
  | "scheduled"
  | "completed"
  | "cancelled"
  | "rescheduled"
  | "no_show";

export type InterviewRecommendation = "hire" | "no_hire" | "maybe";

export interface InterviewFeedback {
  id: number;
  interview_id: number;
  submitted_by_id: number | null;
  submitted_by_email: string | null;
  rating: number | null;
  recommendation: InterviewRecommendation | string | null;
  feedback: string | null;
  technical_score: number | null;
  communication_score: number | null;
  cultural_fit_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface InterviewSummaryForApplication {
  id: number;
  round_name: string;
  round_number: number;
  scheduled_at: string;
  duration_minutes: number;
  mode: InterviewMode | string;
  mode_label: string;
  location_or_link: string | null;
  status: InterviewStatus | string;
  status_label: string;
  interviewer_id: number | null;
  interviewer_email: string | null;
  interviewer_name: string | null;
  has_feedback: boolean;
  latest_recommendation: InterviewRecommendation | string | null;
}

export interface Interview {
  id: number;
  application_id: number;
  round_name: string;
  round_number: number;
  scheduled_at: string;
  duration_minutes: number;
  mode: InterviewMode | string;
  mode_label: string;
  location_or_link: string | null;
  interviewer_id: number | null;
  interviewer_email: string | null;
  interviewer_name: string | null;
  status: InterviewStatus | string;
  status_label: string;
  created_by_id: number | null;
  created_at: string;
  updated_at: string;
  feedback: InterviewFeedback[];
}

export interface InterviewListRow {
  id: number;
  application_id: number;
  candidate_id: number;
  candidate_name: string;
  job_title: string | null;
  round_name: string;
  round_number: number;
  scheduled_at: string;
  duration_minutes: number;
  mode: string;
  mode_label: string;
  location_or_link: string | null;
  interviewer_id: number | null;
  interviewer_email: string | null;
  interviewer_name: string | null;
  status: string;
  status_label: string;
  has_feedback: boolean;
  latest_recommendation: string | null;
}

export interface InterviewCreatePayload {
  application_id: number;
  round_name: string;
  round_number: number;
  scheduled_at: string;
  duration_minutes: number;
  mode: InterviewMode | string;
  location_or_link?: string | null;
  interviewer_id?: number | null;
}

export interface InterviewFeedbackPayload {
  rating?: number | null;
  recommendation?: InterviewRecommendation | string | null;
  feedback?: string | null;
  technical_score?: number | null;
  communication_score?: number | null;
  cultural_fit_score?: number | null;
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
  applications: CandidateApplicationSummary[];
  top_score: number | null;
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
