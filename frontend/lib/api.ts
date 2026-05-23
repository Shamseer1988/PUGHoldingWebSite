/**
 * Tiny typed fetch wrapper used by every frontend feature.
 *
 * Phase 1 only exposes a health-check helper; later phases will add
 * authenticated helpers for the website admin and HR ATS surfaces.
 */
import { env } from "@/lib/env";

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  database: string;
  timestamp: string;
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const url = `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      `Request to ${url} failed with status ${response.status}`
    );
  }

  return (await response.json()) as T;
}

export async function getBackendHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}
