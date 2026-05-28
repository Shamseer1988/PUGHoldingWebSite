/**
 * TanStack Query hooks for the Website Admin (Phase B-4).
 *
 * Wraps ``adminApi.*`` in declarative query / mutation hooks so the
 * pages stop hand-rolling ``useEffect`` + ``setState`` + manual
 * refresh. The actual transport (auth header, error parsing) lives
 * in ``lib/admin/api.ts``; this module is the cache + lifecycle
 * surface React components consume.
 *
 * Migration strategy: opt-in per page. Pages still using the bare
 * ``adminApi`` keep working unchanged — once they're touched, they
 * move to the matching hook here.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import { adminApi, AdminApiError } from "@/lib/admin/api";
import type {
  AdminUser,
  AdminUserCreatePayload,
  AdminUserUpdatePayload,
  RoleSummary,
  Scope,
} from "@/lib/admin/types";

export interface AdminUsersFilters {
  scope: "" | Scope;
  includeInactive: boolean;
}

export const adminQueryKeys = {
  all: ["admin"] as const,
  users: (filters: AdminUsersFilters) =>
    [...adminQueryKeys.all, "users", filters] as const,
  usersRoot: () => [...adminQueryKeys.all, "users"] as const,
  roles: () => [...adminQueryKeys.all, "roles"] as const,
};

function buildUsersUrl(filters: AdminUsersFilters): string {
  const params = new URLSearchParams();
  if (filters.scope) params.set("scope", filters.scope);
  if (!filters.includeInactive) params.set("include_inactive", "false");
  const qs = params.toString();
  return qs ? `/admin/users?${qs}` : "/admin/users";
}

export function useAdminUsers(
  filters: AdminUsersFilters,
  options: { enabled?: boolean } = {}
): UseQueryResult<AdminUser[], AdminApiError> {
  return useQuery<AdminUser[], AdminApiError>({
    queryKey: adminQueryKeys.users(filters),
    queryFn: () => adminApi.get<AdminUser[]>(buildUsersUrl(filters)),
    enabled: options.enabled ?? true,
  });
}

export function useAdminRoles(
  options: { enabled?: boolean } = {}
): UseQueryResult<RoleSummary[], AdminApiError> {
  return useQuery<RoleSummary[], AdminApiError>({
    queryKey: adminQueryKeys.roles(),
    queryFn: () => adminApi.get<RoleSummary[]>("/admin/roles"),
    enabled: options.enabled ?? true,
  });
}

export function useCreateAdminUser(): UseMutationResult<
  AdminUser,
  AdminApiError,
  AdminUserCreatePayload
> {
  const qc = useQueryClient();
  return useMutation<AdminUser, AdminApiError, AdminUserCreatePayload>({
    mutationFn: (body) => adminApi.post<AdminUser>("/admin/users", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: adminQueryKeys.usersRoot() });
    },
  });
}

export interface UpdateAdminUserVars {
  id: number;
  body: AdminUserUpdatePayload;
}

export function useUpdateAdminUser(): UseMutationResult<
  AdminUser,
  AdminApiError,
  UpdateAdminUserVars
> {
  const qc = useQueryClient();
  return useMutation<AdminUser, AdminApiError, UpdateAdminUserVars>({
    mutationFn: ({ id, body }) =>
      adminApi.patch<AdminUser>(`/admin/users/${id}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: adminQueryKeys.usersRoot() });
    },
  });
}

export function useDeactivateAdminUser(): UseMutationResult<
  void,
  AdminApiError,
  number
> {
  const qc = useQueryClient();
  return useMutation<void, AdminApiError, number>({
    mutationFn: (id) => adminApi.delete<void>(`/admin/users/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: adminQueryKeys.usersRoot() });
    },
  });
}
