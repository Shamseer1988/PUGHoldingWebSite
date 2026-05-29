/**
 * TanStack Query hooks for the admin dashboard (Phase B-4).
 *
 * Mocks the ``adminApi`` transport and asserts:
 *
 * * ``useAdminUsers`` builds the right URL from the filter shape.
 * * The filter object is part of the query key, so toggling
 *   ``includeInactive`` triggers a fresh fetch instead of returning
 *   the cached list.
 * * ``useCreateAdminUser`` invalidates the user list on success so
 *   the page sees the new row without a manual ``refresh()``.
 * * 4xx errors propagate as ``AdminApiError`` and are *not* retried
 *   (the QueryClient's retry predicate skips them).
 */
import { describe, expect, test, vi, afterEach, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AdminApiError } from "@/lib/admin/api";
import {
  adminQueryKeys,
  useAdminUsers,
  useCreateAdminUser,
} from "@/lib/admin/queries";

const adminApiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));

vi.mock("@/lib/admin/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/admin/api")>(
    "@/lib/admin/api"
  );
  return {
    ...actual,
    adminApi: adminApiMock,
  };
});

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

function makeTestClient(): QueryClient {
  // ``retry: false`` so error tests resolve quickly instead of
  // walking the production backoff.
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

beforeEach(() => {
  adminApiMock.get.mockReset();
  adminApiMock.post.mockReset();
  adminApiMock.patch.mockReset();
  adminApiMock.delete.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("adminQueryKeys", () => {
  test("users key embeds the filter object so toggles bust the cache", () => {
    const a = adminQueryKeys.users({ scope: "", includeInactive: true });
    const b = adminQueryKeys.users({ scope: "", includeInactive: false });
    expect(a).not.toEqual(b);
  });

  test("roles key is constant — same array for every call", () => {
    expect(adminQueryKeys.roles()).toEqual(adminQueryKeys.roles());
  });
});

describe("useAdminUsers", () => {
  test("requests /admin/users with no params for the default filters", async () => {
    adminApiMock.get.mockResolvedValueOnce([
      { id: 1, email: "admin@example.com" },
    ]);

    const { result } = renderHook(
      () => useAdminUsers({ scope: "", includeInactive: true }),
      { wrapper: makeWrapper(makeTestClient()) }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(adminApiMock.get).toHaveBeenCalledWith("/admin/users");
    expect(result.current.data).toEqual([
      { id: 1, email: "admin@example.com" },
    ]);
  });

  test("encodes the scope filter and the include_inactive=false param", async () => {
    adminApiMock.get.mockResolvedValueOnce([]);

    renderHook(
      () => useAdminUsers({ scope: "hr", includeInactive: false }),
      { wrapper: makeWrapper(makeTestClient()) }
    );

    await waitFor(() =>
      expect(adminApiMock.get).toHaveBeenCalledWith(
        "/admin/users?scope=hr&include_inactive=false"
      )
    );
  });

  test("4xx error surfaces as AdminApiError with status — no retry", async () => {
    const err = new AdminApiError("Forbidden", 403);
    adminApiMock.get.mockRejectedValueOnce(err);

    const { result } = renderHook(
      () => useAdminUsers({ scope: "", includeInactive: true }),
      { wrapper: makeWrapper(makeTestClient()) }
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Forbidden");
    expect(result.current.error?.status).toBe(403);
    // Single attempt — the production client's retry predicate skips
    // 4xx, and our test client has ``retry: false`` for safety.
    expect(adminApiMock.get).toHaveBeenCalledTimes(1);
  });

  test("enabled=false defers the fetch", () => {
    renderHook(
      () =>
        useAdminUsers(
          { scope: "", includeInactive: true },
          { enabled: false }
        ),
      { wrapper: makeWrapper(makeTestClient()) }
    );
    expect(adminApiMock.get).not.toHaveBeenCalled();
  });
});

describe("useCreateAdminUser", () => {
  test("posts the payload and invalidates the users root key on success", async () => {
    const created = { id: 7, email: "new@example.com" };
    adminApiMock.post.mockResolvedValueOnce(created);
    adminApiMock.get.mockResolvedValue([created]);

    const client = makeTestClient();
    // Seed a cached users query so we can prove it gets invalidated.
    client.setQueryData(
      adminQueryKeys.users({ scope: "", includeInactive: true }),
      []
    );

    const { result } = renderHook(() => useCreateAdminUser(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        email: "new@example.com",
        full_name: "New",
        password: "secret-pw-123",
        is_active: true,
        is_superuser: false,
        role_ids: [],
      });
    });

    expect(adminApiMock.post).toHaveBeenCalledWith("/admin/users", {
      email: "new@example.com",
      full_name: "New",
      password: "secret-pw-123",
      is_active: true,
      is_superuser: false,
      role_ids: [],
    });

    // The cached entry is marked stale; the next consumer will refetch.
    const state = client.getQueryState(
      adminQueryKeys.users({ scope: "", includeInactive: true })
    );
    expect(state?.isInvalidated).toBe(true);
  });
});
