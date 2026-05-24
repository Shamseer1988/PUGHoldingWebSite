/**
 * Browser-side helpers for the public form submissions.
 *
 * Server-side reads live in lib/public-api.ts and are imported into
 * Server Components. These helpers are imported from `"use client"`
 * components (newsletter form, contact form, etc.).
 */
import { env } from "@/lib/env";

export class PublicApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "PublicApiError";
  }
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const url = `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") detail = payload.detail;
      else if (Array.isArray(payload?.detail) && payload.detail[0]?.msg)
        detail = payload.detail[0].msg;
    } catch {
      /* swallow */
    }
    throw new PublicApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export interface ContactSubmitPayload {
  name: string;
  email: string;
  phone?: string;
  department?: string;
  subject?: string;
  message: string;
}

export async function submitContactMessage(payload: ContactSubmitPayload) {
  return post<{ id: number }>("/public/contact", payload);
}

export async function subscribeToNewsletter(email: string) {
  return post<{ id: number; email: string; is_active: boolean }>(
    "/public/newsletter",
    { email }
  );
}

// ---------------------------------------------------------------------------
// Candidate application (Phase 10)
// ---------------------------------------------------------------------------

export interface CandidateApplicationPayload {
  full_name: string;
  email: string;
  mobile: string;
  nationality?: string;
  current_location?: string;
  total_experience_years?: number;
  expected_salary?: number;
  notice_period?: string;
  cover_letter?: string;
  job_slug?: string;
  consent: boolean;
  cv: File;
}

export interface CandidateApplicationResult {
  candidate_id: number;
  application_id: number;
  was_existing_candidate: boolean;
  job_title?: string | null;
  job_slug?: string | null;
}

export async function submitCandidateApplication(
  payload: CandidateApplicationPayload
): Promise<CandidateApplicationResult> {
  const url = `${env.apiBaseUrl}/public/candidate-applications`;
  const fd = new FormData();
  fd.append("file", payload.cv);
  fd.append("full_name", payload.full_name);
  fd.append("email", payload.email);
  fd.append("mobile", payload.mobile);
  fd.append("consent", String(payload.consent));
  if (payload.job_slug) fd.append("job_slug", payload.job_slug);
  if (payload.nationality) fd.append("nationality", payload.nationality);
  if (payload.current_location)
    fd.append("current_location", payload.current_location);
  if (payload.total_experience_years !== undefined)
    fd.append(
      "total_experience_years",
      String(payload.total_experience_years)
    );
  if (payload.expected_salary !== undefined)
    fd.append("expected_salary", String(payload.expected_salary));
  if (payload.notice_period) fd.append("notice_period", payload.notice_period);
  if (payload.cover_letter) fd.append("cover_letter", payload.cover_letter);

  const response = await fetch(url, {
    method: "POST",
    body: fd,
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail) && body.detail[0]?.msg)
        detail = body.detail[0].msg;
    } catch {
      /* swallow */
    }
    throw new PublicApiError(detail, response.status);
  }

  return (await response.json()) as CandidateApplicationResult;
}
