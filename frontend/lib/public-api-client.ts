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
