/**
 * Auth client for the Website Admin and HR ATS portals.
 *
 * Two separate token slots are stored in localStorage so a website-admin
 * session and an HR session can coexist in the same browser without
 * leaking permissions across portals.
 *
 * Phase 2 ships with bearer tokens in localStorage; Phase 19 will revisit
 * for httpOnly cookies + CSRF as part of the security hardening pass.
 */
import { apiFetch } from "@/lib/api";

export type AuthScope = "admin" | "hr";

export interface AuthRole {
  id: number;
  name: string;
  scope: string;
  description: string | null;
  permissions: Array<{
    id: number;
    key: string;
    scope: string;
    description: string | null;
  }>;
}

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  last_login_at: string | null;
  roles: AuthRole[];
  scopes: string[];
  permissions: string[];
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthUser;
}

interface StoredSession {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
  /** Epoch milliseconds when the access token expires. */
  expiresAt: number;
}

const STORAGE_KEYS: Record<AuthScope, string> = {
  admin: "pug.auth.admin",
  hr: "pug.auth.hr",
};

const SCOPE_TO_BACKEND_PATH: Record<AuthScope, string> = {
  admin: "/admin/auth",
  hr: "/hr/auth",
};

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export function loadSession(scope: AuthScope): StoredSession | null {
  if (!isBrowser()) return null;
  const raw = window.localStorage.getItem(STORAGE_KEYS[scope]);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredSession;
    if (!parsed.accessToken || !parsed.user) return null;
    return parsed;
  } catch {
    return null;
  }
}

function storeSession(scope: AuthScope, session: StoredSession): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(STORAGE_KEYS[scope], JSON.stringify(session));
}

export function clearSession(scope: AuthScope): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(STORAGE_KEYS[scope]);
}

export function isSessionValid(session: StoredSession | null): boolean {
  if (!session) return false;
  // Treat tokens within 30s of expiry as already expired so the UI
  // doesn't spin on a doomed request.
  return session.expiresAt - Date.now() > 30_000;
}

export class AuthApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "AuthApiError";
  }
}

export async function login(
  scope: AuthScope,
  email: string,
  password: string
): Promise<StoredSession> {
  const path = `${SCOPE_TO_BACKEND_PATH[scope]}/login`;
  const response = await apiFetchRaw(path, {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const detail = await safeDetail(response);
    throw new AuthApiError(detail, response.status);
  }

  const body = (await response.json()) as LoginResponse;
  const session: StoredSession = {
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    user: body.user,
    expiresAt: Date.now() + body.expires_in * 1000,
  };
  storeSession(scope, session);
  return session;
}

export async function logout(scope: AuthScope): Promise<void> {
  const session = loadSession(scope);
  if (session) {
    try {
      await apiFetchRaw(`${SCOPE_TO_BACKEND_PATH[scope]}/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.accessToken}` },
      });
    } catch {
      // Server-side audit is best-effort here; always clear the client.
    }
  }
  clearSession(scope);
}

export async function fetchMe(scope: AuthScope): Promise<AuthUser> {
  const session = loadSession(scope);
  if (!session) throw new AuthApiError("Not authenticated", 401);
  return apiFetch<AuthUser>(`${SCOPE_TO_BACKEND_PATH[scope]}/me`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

async function apiFetchRaw(path: string, init: RequestInit): Promise<Response> {
  const { env } = await import("@/lib/env");
  const url = `${env.apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
  return fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
}

async function safeDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && body.detail.length > 0) {
      const first = body.detail[0];
      if (typeof first?.msg === "string") return first.msg;
    }
  } catch {
    /* fall through */
  }
  return `Request failed with status ${response.status}`;
}
