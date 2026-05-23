"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import {
  type AuthScope,
  type AuthUser,
  clearSession,
  fetchMe,
  isSessionValid,
  loadSession,
  login as apiLogin,
  logout as apiLogout,
} from "@/lib/auth";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  scope: AuthScope;
  status: AuthStatus;
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  scope: AuthScope;
  /** Where to send users after a successful login. */
  loginRedirect: string;
  /** Where to send users after logout. */
  logoutRedirect: string;
  children: React.ReactNode;
}

export function AuthProvider({
  scope,
  loginRedirect,
  logoutRedirect,
  children,
}: AuthProviderProps) {
  const router = useRouter();
  const [status, setStatus] = React.useState<AuthStatus>("loading");
  const [user, setUser] = React.useState<AuthUser | null>(null);

  // On mount, hydrate from localStorage and verify with /me.
  React.useEffect(() => {
    let cancelled = false;
    const stored = loadSession(scope);
    if (!isSessionValid(stored)) {
      clearSession(scope);
      setStatus("unauthenticated");
      setUser(null);
      return;
    }
    setUser(stored!.user);
    setStatus("authenticated");
    // Best-effort revalidation against the backend.
    fetchMe(scope)
      .then((fresh) => {
        if (!cancelled) setUser(fresh);
      })
      .catch(() => {
        if (cancelled) return;
        clearSession(scope);
        setUser(null);
        setStatus("unauthenticated");
      });
    return () => {
      cancelled = true;
    };
  }, [scope]);

  const login = React.useCallback(
    async (email: string, password: string) => {
      const session = await apiLogin(scope, email, password);
      setUser(session.user);
      setStatus("authenticated");
      router.push(loginRedirect);
      router.refresh();
    },
    [scope, loginRedirect, router]
  );

  const logout = React.useCallback(async () => {
    await apiLogout(scope);
    setUser(null);
    setStatus("unauthenticated");
    router.push(logoutRedirect);
    router.refresh();
  }, [scope, logoutRedirect, router]);

  const refresh = React.useCallback(async () => {
    try {
      const fresh = await fetchMe(scope);
      setUser(fresh);
      setStatus("authenticated");
    } catch {
      clearSession(scope);
      setUser(null);
      setStatus("unauthenticated");
    }
  }, [scope]);

  const value = React.useMemo<AuthContextValue>(
    () => ({ scope, status, user, login, logout, refresh }),
    [scope, status, user, login, logout, refresh]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within <AuthProvider>");
  }
  return ctx;
}
