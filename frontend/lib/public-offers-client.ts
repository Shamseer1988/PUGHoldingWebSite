/**
 * Browser-side helpers for the public Offers viewer.
 *
 * These are imported only from ``"use client"`` components so the
 * server bundle stays clean.
 */
import { env } from "@/lib/env";


/** Stable per-browser id used as a privacy-preserving session key
 *  for the view-counter. Survives reloads via localStorage; not used
 *  for tracking the user — just for deduplicating "the same person
 *  opened this twice" inside the same session window. */
export function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return "";
  try {
    const KEY = "pug:offers:session";
    let value = window.localStorage.getItem(KEY);
    if (!value) {
      value =
        typeof crypto?.randomUUID === "function"
          ? crypto.randomUUID()
          : Math.random().toString(36).slice(2) + Date.now().toString(36);
      window.localStorage.setItem(KEY, value);
    }
    return value;
  } catch {
    return "";
  }
}

/** Very rough device classification — desktop (default), tablet, mobile.
 *  Read from ``navigator.userAgent`` so it works without third-party
 *  fingerprint libs. */
export function detectDevice(): "mobile" | "tablet" | "desktop" {
  if (typeof navigator === "undefined") return "desktop";
  const ua = navigator.userAgent || "";
  if (/iPad|Android(?!.*Mobile)|Tablet/.test(ua)) return "tablet";
  if (/Mobile|iPhone|Android/.test(ua)) return "mobile";
  return "desktop";
}

export interface LogCatalogueViewPayload {
  session_hash?: string;
  device?: "mobile" | "tablet" | "desktop";
  duration_seconds?: number;
}

/** POST the view beacon. Best-effort — failures are swallowed so the
 *  viewer never breaks because analytics misbehaved. */
export async function logCatalogueView(
  catalogueId: number,
  payload: LogCatalogueViewPayload = {}
): Promise<void> {
  const url = `${env.apiBaseUrl}/offers/catalogues/${catalogueId}/view`;
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    });
  } catch {
    /* analytics never blocks the user */
  }
}

/** Build the public download URL for a catalogue's source PDF. */
export function catalogueDownloadUrl(catalogueId: number): string {
  return `${env.apiBaseUrl}/offers/catalogues/${catalogueId}/download`;
}
