"use client";

import * as React from "react";
import {
  AlertTriangle,
  ChevronRight,
  Loader2,
  Plus,
  Save,
  ShieldAlert,
  Trash2,
  Users as UsersIcon,
  X,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { RequireSystemScope } from "@/components/admin/require-system-scope";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import type {
  PermissionInfo,
  RoleCreatePayload,
  RoleDetail,
  RolePermissionUpdatePayload,
  RoleSummary,
  RoleUpdatePayload,
  Scope,
} from "@/lib/admin/types";
import { cn } from "@/lib/utils";


/**
 * Phase 12 — Role & permission matrix admin.
 *
 * Two-pane layout:
 *   left  — role list (clickable, "New role" button at the top)
 *   right — role detail (rename + redescribe + scoped permission
 *           matrix with checkboxes; saves the grants diff in one
 *           PATCH /permissions call)
 *
 * All endpoints require system scope, which RequireSystemScope
 * enforces at the route level. Backend re-validates every action.
 */
export default function AdminRolesPage() {
  const { user } = useAuth();
  const hasSystem = Boolean(
    user?.is_superuser || user?.scopes?.includes("system"),
  );
  if (!hasSystem) {
    return (
      <AdminShell title="Roles & permissions" description="System-only.">
        <RequireSystemScope area="Roles & permissions">{null}</RequireSystemScope>
      </AdminShell>
    );
  }
  return <RolesBody />;
}


function RolesBody() {
  const [roles, setRoles] = React.useState<RoleSummary[] | null>(null);
  const [permissions, setPermissions] = React.useState<PermissionInfo[] | null>(
    null,
  );
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    void refresh();
  }, []);

  async function refresh() {
    setError(null);
    try {
      const [r, p] = await Promise.all([
        adminApi.get<RoleSummary[]>("/admin/roles"),
        adminApi.get<PermissionInfo[]>("/admin/permissions"),
      ]);
      setRoles(r);
      setPermissions(p);
      if (selectedId === null && r.length > 0) setSelectedId(r[0].id);
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  return (
    <AdminShell
      title="Roles & permissions"
      description="Super-admin only. Edit the permissions granted to each role and the audit log captures every change."
      actions={
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New role</span>
        </Button>
      }
    >
      {error && (
        <div
          role="alert"
          className="mb-3 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-300"
        >
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        {/* Role list */}
        <aside className="rounded-xl border border-border/60 bg-card">
          {roles === null ? (
            <p className="p-4 text-sm text-muted-foreground">
              <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" />
              Loading…
            </p>
          ) : roles.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">No roles yet.</p>
          ) : (
            <ul className="divide-y divide-border/60">
              {roles.map((role) => (
                <li key={role.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(role.id)}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted",
                      selectedId === role.id && "bg-primary/10 text-primary",
                    )}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">
                        {role.name}
                      </span>
                      <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
                        {role.scope}
                      </span>
                    </span>
                    <ChevronRight className="h-4 w-4 shrink-0 opacity-50" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* Role detail */}
        <section>
          {selectedId === null || permissions === null ? (
            <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-border/60 bg-card text-sm text-muted-foreground">
              Select a role on the left to edit its permissions.
            </div>
          ) : (
            <RoleEditor
              roleId={selectedId}
              permissions={permissions}
              onChanged={refresh}
              onDeleted={() => {
                setSelectedId(null);
                void refresh();
              }}
            />
          )}
        </section>
      </div>

      {createOpen && (
        <CreateRoleDialog
          permissions={permissions ?? []}
          onClose={() => setCreateOpen(false)}
          onCreated={(role) => {
            setCreateOpen(false);
            setSelectedId(role.id);
            void refresh();
          }}
        />
      )}
    </AdminShell>
  );
}


// ---------------------------------------------------------------------------
// Role editor (right pane)
// ---------------------------------------------------------------------------


function RoleEditor({
  roleId,
  permissions,
  onChanged,
  onDeleted,
}: {
  roleId: number;
  permissions: PermissionInfo[];
  onChanged: () => void;
  onDeleted: () => void;
}) {
  const [detail, setDetail] = React.useState<RoleDetail | null>(null);
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [scope, setScope] = React.useState<Scope>("hr");
  const [selectedIds, setSelectedIds] = React.useState<Set<number>>(new Set());
  const [saving, setSaving] = React.useState<"meta" | "perms" | "delete" | null>(
    null,
  );
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setError(null);
    setDetail(null);
    adminApi
      .get<RoleDetail>(`/admin/roles/${roleId}`)
      .then((row) => {
        if (cancelled) return;
        setDetail(row);
        setName(row.name);
        setDescription(row.description ?? "");
        setScope(row.scope);
        setSelectedIds(new Set(row.permission_ids));
      })
      .catch((err) => {
        if (!cancelled) setError((err as AdminApiError).message);
      });
    return () => {
      cancelled = true;
    };
  }, [roleId]);

  async function saveMeta() {
    setSaving("meta");
    setError(null);
    try {
      const payload: RoleUpdatePayload = {
        name: name.trim() !== detail?.name ? name.trim() : undefined,
        description:
          description !== (detail?.description ?? "")
            ? description.trim() || null
            : undefined,
        scope: scope !== detail?.scope ? scope : undefined,
      };
      const updated = await adminApi.patch<RoleDetail>(
        `/admin/roles/${roleId}`,
        payload,
      );
      setDetail(updated);
      setToast("Role details saved.");
      onChanged();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(null);
    }
  }

  async function savePermissions() {
    setSaving("perms");
    setError(null);
    try {
      const payload: RolePermissionUpdatePayload = {
        permission_ids: Array.from(selectedIds),
      };
      const updated = await adminApi.patch<RoleDetail>(
        `/admin/roles/${roleId}/permissions`,
        payload,
      );
      setDetail(updated);
      setToast("Permissions updated.");
      onChanged();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(null);
    }
  }

  async function deleteRole() {
    if (
      !confirm(
        `Delete the role "${detail?.name}"? This cannot be undone. Refused if any user still holds it.`,
      )
    ) {
      return;
    }
    setSaving("delete");
    setError(null);
    try {
      await adminApi.delete(`/admin/roles/${roleId}`);
      onDeleted();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(null);
    }
  }

  if (detail === null) {
    return (
      <p className="text-sm text-muted-foreground">
        <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" />
        Loading role detail…
      </p>
    );
  }

  // Restrict the matrix to permissions matching the role's scope.
  // SYSTEM roles can hold any permission so show everything.
  const visiblePermissions =
    scope === "system"
      ? permissions
      : permissions.filter((p) => p.scope === scope);

  return (
    <div className="space-y-5">
      {/* Header card */}
      <div className="rounded-xl border border-border/60 bg-card p-5">
        <header className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">{detail.name}</h2>
            <p className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wider">
                {detail.scope}
              </span>
              <span className="inline-flex items-center gap-1">
                <UsersIcon className="h-3 w-3" />
                {detail.user_count} user{detail.user_count === 1 ? "" : "s"}
              </span>
            </p>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={deleteRole}
            disabled={saving !== null || detail.user_count > 0}
            className="text-rose-600 hover:text-rose-700"
            title={
              detail.user_count > 0
                ? "Re-assign all users before deleting"
                : "Delete this role"
            }
          >
            {saving === "delete" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Trash2 className="h-3.5 w-3.5" />
            )}
          </Button>
        </header>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label className="text-xs">Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={saving !== null}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Scope</Label>
            <Select
              value={scope}
              onChange={(e) => setScope(e.target.value as Scope)}
              disabled={saving !== null || detail.user_count > 0}
            >
              <option value="hr">HR</option>
              <option value="website">Website</option>
              <option value="system">System</option>
            </Select>
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label className="text-xs">Description</Label>
            <Textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={saving !== null}
            />
          </div>
        </div>

        <div className="mt-3 flex justify-end">
          <Button size="sm" onClick={saveMeta} disabled={saving !== null}>
            {saving === "meta" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            Save role
          </Button>
        </div>
      </div>

      {/* Permission matrix */}
      <div className="rounded-xl border border-border/60 bg-card p-5">
        <header className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Permission grants</h3>
            <p className="text-xs text-muted-foreground">
              Tick the actions this role should be able to perform.
              Permissions outside the role&apos;s scope are filtered out;
              switch to <strong>System</strong> scope to grant cross-cutting
              permissions.
            </p>
          </div>
          <Button
            size="sm"
            onClick={savePermissions}
            disabled={saving !== null}
          >
            {saving === "perms" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            Save permissions
          </Button>
        </header>

        <PermissionMatrix
          permissions={visiblePermissions}
          selectedIds={selectedIds}
          onChange={setSelectedIds}
          disabled={saving !== null}
        />
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300"
        >
          <AlertTriangle className="mr-1 inline h-3.5 w-3.5" />
          {error}
        </p>
      )}
      {toast && (
        <p className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-300">
          {toast}
        </p>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Permission matrix component (shared between editor + create dialog)
// ---------------------------------------------------------------------------


function PermissionMatrix({
  permissions,
  selectedIds,
  onChange,
  disabled,
}: {
  permissions: PermissionInfo[];
  selectedIds: Set<number>;
  onChange: (next: Set<number>) => void;
  disabled?: boolean;
}) {
  // Group by the prefix of the permission key (e.g. "hr:jobs:approve"
  // -> area "jobs"). Falls back to "general" for non-namespaced keys.
  const groups = React.useMemo(() => {
    const out: Record<string, PermissionInfo[]> = {};
    for (const p of permissions) {
      const parts = p.key.split(":");
      const area = parts.length >= 2 ? parts[1] : "general";
      if (!out[area]) out[area] = [];
      out[area].push(p);
    }
    return Object.entries(out).sort((a, b) => a[0].localeCompare(b[0]));
  }, [permissions]);

  function toggle(id: number, checked: boolean) {
    const next = new Set(selectedIds);
    if (checked) next.add(id);
    else next.delete(id);
    onChange(next);
  }

  function toggleAll(area: string, checked: boolean) {
    const next = new Set(selectedIds);
    for (const [a, perms] of groups) {
      if (a !== area) continue;
      for (const p of perms) {
        if (checked) next.add(p.id);
        else next.delete(p.id);
      }
    }
    onChange(next);
  }

  if (permissions.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border/60 bg-background/50 px-3 py-4 text-center text-xs text-muted-foreground">
        No permissions available for this scope.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {groups.map(([area, perms]) => {
        const allOn = perms.every((p) => selectedIds.has(p.id));
        const someOn = perms.some((p) => selectedIds.has(p.id));
        return (
          <div
            key={area}
            className="rounded-md border border-border/60 bg-background/40"
          >
            <header className="flex items-center justify-between border-b border-border/60 px-3 py-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {area}
              </p>
              <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <input
                  type="checkbox"
                  className="h-3.5 w-3.5 rounded border-border accent-primary"
                  checked={allOn}
                  ref={(el) => {
                    if (el) el.indeterminate = !allOn && someOn;
                  }}
                  onChange={(e) => toggleAll(area, e.target.checked)}
                  disabled={disabled}
                />
                Select all
              </label>
            </header>
            <ul className="divide-y divide-border/60">
              {perms.map((p) => (
                <li key={p.id}>
                  <label className="flex cursor-pointer items-start gap-2.5 px-3 py-2 text-xs hover:bg-muted/40">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 rounded border-border accent-primary"
                      checked={selectedIds.has(p.id)}
                      onChange={(e) => toggle(p.id, e.target.checked)}
                      disabled={disabled}
                    />
                    <span className="min-w-0 flex-1">
                      <code className="font-mono text-[11px] text-foreground">
                        {p.key}
                      </code>
                      {p.description && (
                        <span className="mt-0.5 block text-muted-foreground">
                          {p.description}
                        </span>
                      )}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Create role dialog
// ---------------------------------------------------------------------------


function CreateRoleDialog({
  permissions,
  onClose,
  onCreated,
}: {
  permissions: PermissionInfo[];
  onClose: () => void;
  onCreated: (role: RoleDetail) => void;
}) {
  const [name, setName] = React.useState("");
  const [scope, setScope] = React.useState<Scope>("hr");
  const [description, setDescription] = React.useState("");
  const [selectedIds, setSelectedIds] = React.useState<Set<number>>(new Set());
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const visiblePermissions =
    scope === "system"
      ? permissions
      : permissions.filter((p) => p.scope === scope);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload: RoleCreatePayload = {
        name: name.trim(),
        scope,
        description: description.trim() || null,
        permission_ids: Array.from(selectedIds),
      };
      const created = await adminApi.post<RoleDetail>("/admin/roles", payload);
      onCreated(created);
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Create role"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-background/60 backdrop-blur-sm p-4"
    >
      <form
        onSubmit={submit}
        className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl border border-border/60 bg-background shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-border/60 px-5 py-3">
          <div className="flex items-start gap-2">
            <ShieldAlert className="mt-0.5 h-4 w-4 text-primary" />
            <div>
              <h3 className="text-sm font-semibold">New role</h3>
              <p className="text-xs text-muted-foreground">
                Pick the scope first — the permission list filters to match.
              </p>
            </div>
          </div>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={onClose}
            disabled={saving}
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">
                Name <span className="text-rose-500">*</span>
              </Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. HR Read-only"
                required
                disabled={saving}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Scope</Label>
              <Select
                value={scope}
                onChange={(e) => setScope(e.target.value as Scope)}
                disabled={saving}
              >
                <option value="hr">HR</option>
                <option value="website">Website</option>
                <option value="system">System (cross-scope)</option>
              </Select>
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label className="text-xs">Description</Label>
              <Textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={saving}
              />
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Permission grants
            </p>
            <PermissionMatrix
              permissions={visiblePermissions}
              selectedIds={selectedIds}
              onChange={setSelectedIds}
              disabled={saving}
            />
          </div>

          {error && (
            <p
              role="alert"
              className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300"
            >
              {error}
            </p>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-border/60 px-5 py-3">
          <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving || !name.trim()}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Create role
          </Button>
        </footer>
      </form>
    </div>
  );
}
