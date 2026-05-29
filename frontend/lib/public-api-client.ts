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

// ---------------------------------------------------------------------------
// Public CV parse-preview (advanced module — phase 7)
// ---------------------------------------------------------------------------

export interface PublicCvParsePreview {
  parsed: boolean;
  parser_version: string | null;
  warnings: string[];
  full_name: string | null;
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
  skills: string | null;
  education: Array<Record<string, unknown>> | null;
  languages: string[] | null;
  certifications: string[] | null;
}

export async function parseCvPreview(file: File): Promise<PublicCvParsePreview> {
  const url = `${env.apiBaseUrl}/public/candidate-applications/parse-preview`;
  const fd = new FormData();
  fd.append("file", file);
  const response = await fetch(url, {
    method: "POST",
    body: fd,
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = `CV preview failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* swallow */
    }
    throw new PublicApiError(detail, response.status);
  }
  return (await response.json()) as PublicCvParsePreview;
}

// ---------------------------------------------------------------------------
// Public Ask-PUG-AI assistant (Phase 17)
// ---------------------------------------------------------------------------

export interface AskPugAiTurn {
  role: "user" | "assistant";
  content: string;
}

export interface AskPugAiRequest {
  question: string;
  session_id?: string | null;
  history?: AskPugAiTurn[];
}

export interface AskPugAiResponse {
  answer: string;
  mode: "disabled" | "mock" | "live" | string;
  was_fallback: boolean;
  session_id: string | null;
  model_name: string | null;
}

export async function askPugAi(
  payload: AskPugAiRequest
): Promise<AskPugAiResponse> {
  return post<AskPugAiResponse>("/public/ai-assistant/ask", payload);
}


// ---------------------------------------------------------------------------
// Phase C-5 — streaming variant of askPugAi
// ---------------------------------------------------------------------------

export interface AskPugAiStreamDoneEvent {
  type: "done";
  mode: AskPugAiResponse["mode"];
  session_id: string | null;
  model_name: string | null;
  was_fallback: boolean;
}

export interface AskPugAiStreamCallbacks {
  /** Fires for every token chunk the backend emits. */
  onDelta: (text: string) => void;
  /** Fires once with the final metadata. Called before the promise resolves. */
  onDone?: (event: AskPugAiStreamDoneEvent) => void;
  /** Optional abort signal — the caller cancels the in-flight request when set. */
  signal?: AbortSignal;
}

/**
 * Server-Sent-Events client for the streaming AI endpoint.
 *
 * Posts to ``/public/ai-assistant/ask-stream`` and walks the body
 * with a ``ReadableStream`` reader instead of buffering — the
 * caller's ``onDelta`` runs as each chunk arrives, so the bubble
 * renders the answer live.
 *
 * Resolves to the parsed ``done`` frame. Throws if the server
 * returned a non-200 status, the body is missing, or the stream
 * is aborted mid-flight.
 *
 * Format expected on the wire:
 *
 *     data: {"type": "delta", "text": "Hello"}\n\n
 *     data: {"type": "delta", "text": ", world"}\n\n
 *     data: {"type": "done", "mode": "...", ...}\n\n
 */
export async function askPugAiStream(
  payload: AskPugAiRequest,
  callbacks: AskPugAiStreamCallbacks
): Promise<AskPugAiStreamDoneEvent> {
  const response = await fetch(
    `${env.apiBaseUrl}/public/ai-assistant/ask-stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(payload),
      signal: callbacks.signal,
      // ``no-store`` defeats any browser cache on the streaming
      // endpoint (which has its own no-cache headers but belt +
      // suspenders is cheap).
      cache: "no-store",
    }
  );
  if (!response.ok) {
    throw new PublicApiError(
      `AI request failed (${response.status})`,
      response.status
    );
  }
  if (response.body === null) {
    throw new PublicApiError("AI response had no streaming body", 0);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let done: AskPugAiStreamDoneEvent | null = null;

  while (true) {
    const { value, done: streamFinished } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: true });
      // SSE frames are separated by ``\n\n``. We pop completed
      // frames out and leave any partial trailing frame in the
      // buffer for the next read.
      let separatorIdx = buffer.indexOf("\n\n");
      while (separatorIdx !== -1) {
        const frame = buffer.slice(0, separatorIdx);
        buffer = buffer.slice(separatorIdx + 2);
        const parsed = parseSseFrame(frame);
        if (parsed) {
          if (parsed.type === "delta") {
            callbacks.onDelta(parsed.text);
          } else if (parsed.type === "done") {
            done = parsed;
            callbacks.onDone?.(parsed);
          }
        }
        separatorIdx = buffer.indexOf("\n\n");
      }
    }
    if (streamFinished) {
      // Flush the decoder for any unfinished multi-byte sequence.
      buffer += decoder.decode();
      // Some servers emit the final frame without the trailing
      // double-newline — try parsing whatever's left.
      const tail = buffer.trim();
      if (tail) {
        const parsed = parseSseFrame(tail);
        if (parsed) {
          if (parsed.type === "delta") {
            callbacks.onDelta(parsed.text);
          } else if (parsed.type === "done") {
            done = parsed;
            callbacks.onDone?.(parsed);
          }
        }
      }
      break;
    }
  }

  if (done === null) {
    throw new PublicApiError("AI stream ended without a done frame", 0);
  }
  return done;
}

interface ParsedDelta {
  type: "delta";
  text: string;
}

type ParsedFrame = ParsedDelta | AskPugAiStreamDoneEvent;

/**
 * Pure SSE-frame parser. Exported so tests can exercise the wire
 * decoding without standing up a fetch mock.
 */
export function parseSseFrame(frame: string): ParsedFrame | null {
  // Allow a leading "data:" prefix the framer might or might not
  // have already stripped — both forms appear in the wild.
  const payload = frame.startsWith("data:")
    ? frame.slice("data:".length).trim()
    : frame.trim();
  if (!payload) return null;
  try {
    const parsed = JSON.parse(payload);
    if (parsed && typeof parsed === "object") {
      if (parsed.type === "delta" && typeof parsed.text === "string") {
        return { type: "delta", text: parsed.text };
      }
      if (parsed.type === "done") {
        return {
          type: "done",
          mode: parsed.mode,
          session_id: parsed.session_id ?? null,
          model_name: parsed.model_name ?? null,
          was_fallback: Boolean(parsed.was_fallback),
        };
      }
    }
  } catch {
    // Malformed — caller's wider context (parser bug, server-side
    // hiccup) handles it. Returning ``null`` keeps the stream
    // moving instead of crashing on one bad frame.
  }
  return null;
}
