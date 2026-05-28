/**
 * HR real-time notification client (Phase C-2).
 *
 * Single hook that opens the ``/ws/hr`` WebSocket once per HR
 * console mount and fires a toast for every event the backend
 * pushes. Reconnects with exponential backoff when the socket drops
 * — operators leaving a tab open all day shouldn't have to refresh
 * because the wifi blipped.
 *
 * Auth: the JWT lives in ``localStorage`` per scope. The browser
 * ``WebSocket`` constructor can't attach an ``Authorization`` header,
 * so the token rides in the URL query — the backend endpoint
 * validates it the same way the HTTP routes do.
 */
import * as React from "react";

import { loadSession } from "@/lib/auth";
import { env } from "@/lib/env";
import { toast } from "@/lib/toast";

interface WsEnvelope {
  type: string;
  data: Record<string, unknown>;
}

interface CandidateApplicationNew {
  candidate_name: string;
  job_title: string | null;
  source: string;
}

const RECONNECT_DELAYS_MS = [1_000, 2_000, 5_000, 10_000, 30_000] as const;

function buildWsUrl(token: string): string {
  // ``env.apiBaseUrl`` is e.g. ``http://localhost:8000/api/v1`` —
  // swap the scheme and append the endpoint path so a single env
  // var drives both transports.
  const httpBase = env.apiBaseUrl;
  const wsBase = httpBase
    .replace(/^https:\/\//i, "wss://")
    .replace(/^http:\/\//i, "ws://");
  const sep = wsBase.includes("?") ? "&" : "?";
  return `${wsBase}/ws/hr${sep}token=${encodeURIComponent(token)}`;
}

function handleEvent(envelope: WsEnvelope): void {
  switch (envelope.type) {
    case "system.hello":
      // Server acknowledged the upgrade. Nothing to surface.
      return;
    case "candidate.application.new": {
      const data = envelope.data as unknown as CandidateApplicationNew;
      const name = data.candidate_name?.toString() || "A new candidate";
      const job = data.job_title?.toString();
      toast.info(`New application — ${name}`, {
        description: job
          ? `Applied to ${job}.`
          : "Profile is open for review.",
      });
      return;
    }
    default:
      // Unknown event types are ignored on purpose — the backend
      // can ship new ones without forcing a frontend deploy.
      return;
  }
}

export function useHrNotifications(): void {
  React.useEffect(() => {
    if (typeof window === "undefined") return;

    let attempt = 0;
    let ws: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let cancelled = false;

    const open = () => {
      const session = loadSession("hr");
      if (!session) {
        // No HR session yet (operator landed on /hr/login or is
        // still rehydrating). Try again with a small backoff so
        // we pick up the token once login completes.
        reconnectTimer = window.setTimeout(open, 2_000);
        return;
      }

      const url = buildWsUrl(session.accessToken);
      ws = new WebSocket(url);

      ws.onopen = () => {
        // Reset the backoff after a successful connect so the
        // *next* drop starts from 1s again.
        attempt = 0;
      };

      ws.onmessage = (e) => {
        try {
          const envelope = JSON.parse(e.data) as WsEnvelope;
          handleEvent(envelope);
        } catch {
          // Malformed payload — log to console (the rare debug aid)
          // and move on. Crashing the hook would lose every future
          // event for this session.
          // eslint-disable-next-line no-console
          console.warn("[ws] bad payload", e.data);
        }
      };

      ws.onclose = () => {
        if (cancelled) return;
        const delay =
          RECONNECT_DELAYS_MS[
            Math.min(attempt, RECONNECT_DELAYS_MS.length - 1)
          ];
        attempt += 1;
        reconnectTimer = window.setTimeout(open, delay);
      };

      ws.onerror = () => {
        // ``onclose`` always fires after ``onerror`` so the reconnect
        // path lives there; this handler exists to silence the
        // "unhandled WS error" warning some browsers emit.
      };
    };

    open();

    return () => {
      cancelled = true;
      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer);
      }
      if (ws !== null) {
        ws.onclose = null;
        ws.onerror = null;
        ws.onmessage = null;
        ws.close();
      }
    };
  }, []);
}
