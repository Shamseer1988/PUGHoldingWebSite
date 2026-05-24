"use client";

import * as React from "react";
import {
  CheckCircle2,
  Filter,
  KeyRound,
  Loader2,
  Lock,
  Plus,
  ShieldCheck,
  Trash2,
  UserCog,
  X,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import type {
  AdminUser,
  AdminUserCreatePayload,
  AdminUserUpdatePayload,
  RoleSummary,
  Scope,
} from "@/lib/admin/types";
import { cn } from "@/lib/utils";

const SCOPE_LABEL: Record<Scope, string> = {
  system: "System",
  website: "Website",
  hr: "HR",
};

const SCOPE_TONE: Record<Scope, string> = {
  system:
    "border-pug-gold-500/40 bg-pug-gold-500/10 text-pug-gold-700 dark:text-pug-gold-300",
  website: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  hr: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300",
};

interface FormState {
  email: string;
  full_name: string;
  password: string;
  is_active: boolean;
  is_superuser: boolean;
  role_ids: number[];
}

const EMPTY_FORM: FormState = {
  email: "",
  full_name: "",
  password: "",
  is_active: true,
  is_superuser: false,
  role_ids: [],
};

export default function UsersAdminPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = React.useState<AdminUser[] | null>(null);
  const [roles, setRoles] = React.useState<RoleSummary[]>([]);
  const [scopeFilter, setScopeFilter] = React.useState<"" | Scope>("");
  const [includeInactive, setIncludeInactive] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<AdminUser | null>(null);
  const [form, setForm] = React.useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    void refresh();
    void loadRoles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeFilter, includeInactive]);

  async function loadRoles() {
    try {
      const list = await adminApi.get<RoleSummary[]>("/admin/roles");
      setRoles(list);
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function refresh() {
    setUsers(null);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (scopeFilter) params.set("scope", scopeFilter);
      if (!includeInactive) params.set("include_inactive", "false");
      const url = `/admin/users${
        params.toString() ? `?${params}` : ""
      }`;
      setUsers(await adminApi.get<AdminUser[]>(url));
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setError(null);
    setDrawerOpen(true);
  }

  function openEdit(target: AdminUser) {
    setEditing(target);
    setForm({
      email: target.email,
      full_name: target.full_name,
      password: "",
      is_active: target.is_active,
      is_superuser: target.is_superuser,
      role_ids: target.roles.map((r) => r.id),
    });
    setError(null);
    setDrawerOpen(true);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      if (editing) {
        const body: AdminUserUpdatePayload = {
          full_name: form.full_name.trim() || undefined,
          is_active: form.is_active,
          is_superuser: form.is_superuser,
          role_ids: form.role_ids,
        };
        if (form.password.trim()) body.password = form.password;
        await adminApi.patch<AdminUser>(
          `/admin/users/${editing.id}`,
          body
        );
        setToast(`Updated ${form.email}.`);
      } else {
        const body: AdminUserCreatePayload = {
          email: form.email.trim().toLowerCase(),
          full_name: form.full_name.trim(),
          password: form.password,
          is_active: form.is_active,
          is_superuser: form.is_superuser,
          role_ids: form.role_ids,
        };
        await adminApi.post<AdminUser>("/admin/users", body);
        setToast(`Created ${body.email}.`);
      }
      setDrawerOpen(false);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function deactivate(target: AdminUser) {
    if (
      !confirm(
        `Deactivate ${target.email}? They will be logged out and unable to sign in until reactivated. Their audit history is preserved.`
      )
    ) {
      return;
    }
    try {
      await adminApi.delete(`/admin/users/${target.id}`);
      setToast(`Deactivated ${target.email}.`);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function reactivate(target: AdminUser) {
    try {
      await adminApi.patch<AdminUser>(`/admin/users/${target.id}`, {
        is_active: true,
      });
      setToast(`Reactivated ${target.email}.`);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  return (
    <AdminShell
      title="Users & roles"
      description="Manage who can sign in to the admin and HR portals — and what they can do once inside."
      actions={
        <Button onClick={openNew} size="sm" aria-label="Add a new user">
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New user</span>
        </Button>
      }
    >
      <Toast message={toast} onClose={() => setToast(null)} />
      {error && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border/60 bg-background/60 p-4 backdrop-blur">
        <div className="space-y-1.5">
          <Label htmlFor="user-scope-filter">Scope</Label>
          <Select
            id="user-scope-filter"
            value={scopeFilter}
            onChange={(e) => setScopeFilter(e.target.value as "" | Scope)}
          >
            <option value="">All scopes</option>
            <option value="system">System</option>
            <option value="website">Website</option>
            <option value="hr">HR</option>
          </Select>
        </div>
        <label className="inline-flex items-center gap-2 pt-1 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
          />
          Show inactive users
        </label>
      </div>

      {users === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading users…
        </p>
      ) : users.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/60 p-10 text-center text-sm text-muted-foreground">
          <UserCog className="mx-auto mb-3 h-8 w-8 opacity-50" />
          No users match those filters.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead className="hidden md:table-cell">Roles</TableHead>
                <TableHead className="hidden lg:table-cell w-32">
                  Last login
                </TableHead>
                <TableHead className="w-24 sm:w-32">Status</TableHead>
                <TableHead className="w-24 sm:w-32 text-right">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>
                    <p className="flex items-center gap-1.5 font-medium leading-tight">
                      {u.full_name}
                      {u.is_superuser && (
                        <span
                          title="Superuser"
                          aria-label="Superuser"
                          className="inline-flex items-center gap-1 rounded-full border border-pug-gold-500/40 bg-pug-gold-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-pug-gold-700 dark:text-pug-gold-300"
                        >
                          <ShieldCheck className="h-2.5 w-2.5" />
                          Super
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">{u.email}</p>
                    {/* Mobile: roles inline under email */}
                    <div className="mt-1.5 flex flex-wrap gap-1 md:hidden">
                      {u.roles.map((r) => (
                        <ScopeChip key={r.id} role={r} />
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {u.roles.length === 0 ? (
                        <span className="text-xs text-muted-foreground">
                          —
                        </span>
                      ) : (
                        u.roles.map((r) => <ScopeChip key={r.id} role={r} />)
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-xs text-muted-foreground">
                    {u.last_login_at
                      ? new Date(u.last_login_at).toLocaleDateString()
                      : "—"}
                  </TableCell>
                  <TableCell>
                    {u.is_active ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
                        <CheckCircle2 className="h-3 w-3" />
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[11px] font-medium text-rose-700 dark:text-rose-300">
                        <Lock className="h-3 w-3" />
                        Inactive
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => openEdit(u)}
                        aria-label={`Edit ${u.email}`}
                      >
                        <UserCog className="h-4 w-4" />
                      </Button>
                      {u.is_active ? (
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => deactivate(u)}
                          disabled={u.id === currentUser?.id}
                          aria-label={`Deactivate ${u.email}`}
                          title={
                            u.id === currentUser?.id
                              ? "You can't deactivate yourself."
                              : "Deactivate user"
                          }
                          className="text-rose-600 hover:text-rose-700 disabled:opacity-30"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : (
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => reactivate(u)}
                          aria-label={`Reactivate ${u.email}`}
                          title="Reactivate user"
                          className="text-emerald-700 hover:text-emerald-800"
                        >
                          <KeyRound className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {drawerOpen && (
        <UserDrawer
          editing={editing}
          form={form}
          setForm={setForm}
          roles={roles}
          saving={saving}
          error={error}
          onClose={() => setDrawerOpen(false)}
          onSave={save}
        />
      )}
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// Drawer
// ---------------------------------------------------------------------------

function UserDrawer({
  editing,
  form,
  setForm,
  roles,
  saving,
  error,
  onClose,
  onSave,
}: {
  editing: AdminUser | null;
  form: FormState;
  setForm: React.Dispatch<React.SetStateAction<FormState>>;
  roles: RoleSummary[];
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSave: () => void;
}) {
  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toggleRole(roleId: number, on: boolean) {
    setForm((prev) => ({
      ...prev,
      role_ids: on
        ? Array.from(new Set([...prev.role_ids, roleId]))
        : prev.role_ids.filter((id) => id !== roleId),
    }));
  }

  // Group roles by scope so the picker stays readable when there are
  // many roles across surfaces.
  const grouped = React.useMemo(() => {
    const out: Record<Scope, RoleSummary[]> = {
      system: [],
      website: [],
      hr: [],
    };
    for (const role of roles) out[role.scope].push(role);
    return out;
  }, [roles]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={editing ? "Edit user" : "Create user"}
      className="fixed inset-0 z-40 flex"
    >
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSave();
        }}
        className="flex w-full max-w-lg flex-col bg-background shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">
            {editing ? `Edit ${editing.email}` : "New user"}
          </h2>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {error && (
            <p
              role="alert"
              className="rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-700 dark:text-rose-200"
            >
              {error}
            </p>
          )}

          <Field label="Email" required>
            <Input
              type="email"
              required
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              disabled={!!editing || saving}
              placeholder="person@pug.example.com"
            />
            {editing && (
              <p className="text-[11px] text-muted-foreground">
                Email is immutable. Deactivate and create a new account if
                someone changes role + email together.
              </p>
            )}
          </Field>

          <Field label="Full name" required>
            <Input
              required
              value={form.full_name}
              onChange={(e) => set("full_name", e.target.value)}
              disabled={saving}
            />
          </Field>

          <Field
            label={editing ? "Reset password (optional)" : "Password"}
            required={!editing}
            hint={
              editing
                ? "Leave blank to keep the current password."
                : "Min 8 characters."
            }
          >
            <Input
              type="password"
              required={!editing}
              minLength={8}
              value={form.password}
              onChange={(e) => set("password", e.target.value)}
              disabled={saving}
              autoComplete="new-password"
            />
          </Field>

          <div className="flex flex-wrap gap-x-6 gap-y-2 pt-2">
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                checked={form.is_active}
                onChange={(e) => set("is_active", e.target.checked)}
                disabled={saving}
              />
              Active
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                checked={form.is_superuser}
                onChange={(e) => set("is_superuser", e.target.checked)}
                disabled={saving}
              />
              Superuser
              <span
                className="text-[11px] text-muted-foreground"
                aria-label="Superuser explanation"
              >
                (bypasses every permission check)
              </span>
            </label>
          </div>

          <fieldset className="space-y-3">
            <legend className="text-sm font-medium">Assigned roles</legend>
            {(Object.keys(grouped) as Scope[]).map((scope) => {
              const list = grouped[scope];
              if (list.length === 0) return null;
              return (
                <div
                  key={scope}
                  className="rounded-xl border border-border/60 bg-muted/30 p-3"
                >
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    {SCOPE_LABEL[scope]} scope
                  </p>
                  <div className="grid gap-1.5">
                    {list.map((role) => {
                      const checked = form.role_ids.includes(role.id);
                      return (
                        <label
                          key={role.id}
                          className={cn(
                            "flex cursor-pointer items-start gap-2 rounded-md border px-3 py-2 text-sm transition-colors",
                            checked
                              ? "border-primary/40 bg-primary/[0.06]"
                              : "border-border/60 bg-background/40 hover:border-primary/30"
                          )}
                        >
                          <input
                            type="checkbox"
                            className="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-ring"
                            checked={checked}
                            onChange={(e) =>
                              toggleRole(role.id, e.target.checked)
                            }
                            disabled={saving}
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block font-medium leading-tight">
                              {role.name}
                            </span>
                            {role.description && (
                              <span className="block text-xs text-muted-foreground">
                                {role.description}
                              </span>
                            )}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              );
            })}
            <p className="text-[11px] text-muted-foreground">
              Roles are seeded by the backend (
              <code className="rounded bg-muted px-1">
                python -m app.scripts.seed_users
              </code>
              ). To add a new role, edit the seed script and re-run it.
            </p>
          </fieldset>
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-border/60 bg-background px-5 py-3">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {saving ? "Saving…" : editing ? "Save changes" : "Create user"}
          </Button>
        </footer>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reusable bits
// ---------------------------------------------------------------------------

function ScopeChip({ role }: { role: RoleSummary }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        SCOPE_TONE[role.scope]
      )}
      title={role.description ?? role.name}
    >
      {role.name}
    </span>
  );
}

function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label>
        {label}
        {required && <span className="ml-0.5 text-rose-500">*</span>}
      </Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function Toast({
  message,
  onClose,
}: {
  message: string | null;
  onClose: () => void;
}) {
  React.useEffect(() => {
    if (!message) return;
    const t = setTimeout(onClose, 3500);
    return () => clearTimeout(t);
  }, [message, onClose]);
  if (!message) return null;
  return (
    <div
      role="status"
      className="mb-4 inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-200"
    >
      <CheckCircle2 className="h-4 w-4" />
      {message}
    </div>
  );
}
