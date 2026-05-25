/**
 * Authenticated fetch helpers for the HR ATS portal.
 *
 * Reads the access token from the per-scope localStorage slot owned
 * by the AuthProvider (lib/auth.ts) — the HR slot, separate from
 * the website-admin slot.
 */
import { loadSession } from "@/lib/auth";
import { env } from "@/lib/env";

export class HrApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "HrApiError";
  }
}

function authHeader(): Record<string, string> {
  const session = loadSession("hr");
  if (!session) throw new HrApiError("Not authenticated", 401);
  return { Authorization: `Bearer ${session.accessToken}` };
}

async function request<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const url = `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail) && body.detail[0]?.msg)
        detail = body.detail[0].msg;
    } catch {
      /* swallow */
    }
    throw new HrApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

async function postMultipart<T>(path: string, fd: FormData): Promise<T> {
  const session = loadSession("hr");
  if (!session) throw new HrApiError("Not authenticated", 401);
  const url = `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  const response = await fetch(url, {
    method: "POST",
    body: fd,
    headers: { Authorization: `Bearer ${session.accessToken}` },
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = `Upload failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail) && body.detail[0]?.msg)
        detail = body.detail[0].msg;
    } catch {
      /* swallow */
    }
    throw new HrApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export const hrApi = {
  get<T>(path: string) {
    return request<T>(path);
  },
  post<T>(path: string, body?: unknown) {
    return request<T>(path, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },
  patch<T>(path: string, body?: unknown) {
    return request<T>(path, {
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },
  delete<T = void>(path: string) {
    return request<T>(path, { method: "DELETE" });
  },
  postMultipart,
};
