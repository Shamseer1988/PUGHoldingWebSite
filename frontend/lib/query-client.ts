/**
 * Shared TanStack Query client factory (Phase B-4).
 *
 * Used by the admin + HR dashboards. Defaults are tuned for an
 * operator-facing console:
 *
 * * ``staleTime: 30s`` — admins working through a list don't need
 *   per-keystroke refetches, and Strict Mode's double-invoke
 *   doesn't trigger a second network call.
 * * ``refetchOnWindowFocus: false`` — switching tabs / IDE
 *   shouldn't burn API calls; operators refresh deliberately.
 * * ``retry`` skips 4xx — a 401 means re-login, a 403 means denied,
 *   a 422 means the payload is wrong. Retrying any of those is noise.
 *   5xx and network errors still retry twice with the library's
 *   default exponential backoff.
 * * Mutations never auto-retry — double-submitting a POST is
 *   worse than failing loudly, and the UI surfaces the error so
 *   the operator can decide.
 */
import { QueryClient } from "@tanstack/react-query";

interface MaybeStatusError {
  status?: unknown;
}

function statusOf(error: unknown): number | undefined {
  const status = (error as MaybeStatusError | null)?.status;
  return typeof status === "number" ? status : undefined;
}

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          const status = statusOf(error);
          if (status !== undefined && status >= 400 && status < 500) {
            return false;
          }
          return failureCount < 2;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}
