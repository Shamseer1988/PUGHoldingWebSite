"use client";

import * as React from "react";
import {
  ArrowDownToLine,
  ArrowUpToLine,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Edit3,
  ExternalLink,
  Eye,
  EyeOff,
  Loader2,
  Plus,
  Trash2,
  X,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import type {
  NavMegaKind,
  NavigationItemCreatePayload,
  NavigationItemNode,
  NavigationItemUpdatePayload,
} from "@/lib/admin/types";
import { cn } from "@/lib/utils";

interface FormState {
  label: string;
  href: string;
  description: string;
  mega_kind: NavMegaKind | "";
  open_in_new_tab: boolean;
  display_order: number;
  is_active: boolean;
  parent_id: number | null;
}

const EMPTY_FORM: FormState = {
  label: "",
  href: "",
  description: "",
  mega_kind: "",
  open_in_new_tab: false,
  display_order: 0,
  is_active: true,
  parent_id: null,
};

export default function MenuAdminPage() {
  const [tree, setTree] = React.useState<NavigationItemNode[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<NavigationItemNode | null>(
    null
  );
  const [form, setForm] = React.useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = React.useState(false);
  const [expanded, setExpanded] = React.useState<Set<number>>(new Set());

  React.useEffect(() => {
    void refresh();
  }, []);

  async function refresh() {
    setTree(null);
    setError(null);
    try {
      const data = await adminApi.get<NavigationItemNode[]>(
        "/admin/cms/navigation"
      );
      setTree(data);
      // Default: expand every parent that has children so the admin
      // sees the full tree on first load.
      setExpanded(
        new Set(
          data
            .filter((n) => (n.children?.length ?? 0) > 0)
            .map((n) => n.id)
        )
      );
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  function openNew(parent: NavigationItemNode | null) {
    setEditing(null);
    setForm({
      ...EMPTY_FORM,
      parent_id: parent?.id ?? null,
    });
    setError(null);
    setDrawerOpen(true);
  }

  function openEdit(node: NavigationItemNode) {
    setEditing(node);
    setForm({
      label: node.label,
      href: node.href,
      description: node.description ?? "",
      mega_kind: (node.mega_kind ?? "") as NavMegaKind | "",
      open_in_new_tab: node.open_in_new_tab,
      display_order: node.display_order,
      is_active: node.is_active,
      parent_id: node.parent_id ?? null,
    });
    setError(null);
    setDrawerOpen(true);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const base = {
        label: form.label.trim(),
        href: form.href.trim(),
        description: form.description.trim() || null,
        mega_kind: form.mega_kind || null,
        open_in_new_tab: form.open_in_new_tab,
        display_order: Number(form.display_order) || 0,
        is_active: form.is_active,
      };
      if (editing) {
        const body: NavigationItemUpdatePayload = base;
        await adminApi.patch(`/admin/cms/navigation/${editing.id}`, body);
        setToast(`Updated "${base.label}".`);
      } else {
        const body: NavigationItemCreatePayload = {
          ...base,
          parent_id: form.parent_id,
        };
        await adminApi.post("/admin/cms/navigation", body);
        setToast(`Created "${base.label}".`);
      }
      setDrawerOpen(false);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(node: NavigationItemNode) {
    const childCount = node.children?.length ?? 0;
    const message = childCount
      ? `Delete "${node.label}" and its ${childCount} child item${
          childCount === 1 ? "" : "s"
        }? This cannot be undone.`
      : `Delete "${node.label}"? This cannot be undone.`;
    if (!confirm(message)) return;
    try {
      await adminApi.delete(`/admin/cms/navigation/${node.id}`);
      setToast(`Deleted "${node.label}".`);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function toggleActive(node: NavigationItemNode) {
    try {
      await adminApi.patch(`/admin/cms/navigation/${node.id}`, {
        is_active: !node.is_active,
      });
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function nudge(node: NavigationItemNode, delta: -1 | 1) {
    try {
      await adminApi.patch(`/admin/cms/navigation/${node.id}`, {
        display_order: Math.max(0, node.display_order + delta),
      });
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  function toggleExpand(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <AdminShell
      title="Navigation menu"
      description="Edit the public navbar + mobile drawer. Empty rows fall back to the compiled-in defaults."
      actions={
        <Button onClick={() => openNew(null)} size="sm" aria-label="Add a top-level item">
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New item</span>
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

      {tree === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading menu…
        </p>
      ) : tree.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/60 p-10 text-center text-sm text-muted-foreground">
          <p className="mb-3">
            No items yet — the public navbar is rendering the compiled-in
            defaults.
          </p>
          <p className="mb-4 text-xs">
            Add a top-level item to take over the public navigation.
          </p>
          <Button size="sm" onClick={() => openNew(null)}>
            <Plus className="h-4 w-4" />
            Add first item
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          {tree.map((node) => (
            <NodeCard
              key={node.id}
              node={node}
              isExpanded={expanded.has(node.id)}
              onToggleExpand={() => toggleExpand(node.id)}
              onEdit={openEdit}
              onAddChild={openNew}
              onDelete={remove}
              onToggleActive={toggleActive}
              onNudge={nudge}
            />
          ))}
        </div>
      )}

      {drawerOpen && (
        <Drawer
          editing={editing}
          form={form}
          setForm={setForm}
          parentOptions={tree?.filter((n) => n.parent_id === null) ?? []}
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
// One row for a parent (with collapsible children)
// ---------------------------------------------------------------------------

function NodeCard({
  node,
  isExpanded,
  onToggleExpand,
  onEdit,
  onAddChild,
  onDelete,
  onToggleActive,
  onNudge,
}: {
  node: NavigationItemNode;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onEdit: (n: NavigationItemNode) => void;
  onAddChild: (parent: NavigationItemNode) => void;
  onDelete: (n: NavigationItemNode) => void;
  onToggleActive: (n: NavigationItemNode) => void;
  onNudge: (n: NavigationItemNode, delta: -1 | 1) => void;
}) {
  const children = node.children ?? [];
  return (
    <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
      <NodeRow
        node={node}
        isTopLevel
        onEdit={() => onEdit(node)}
        onAddChild={() => onAddChild(node)}
        onDelete={() => onDelete(node)}
        onToggleActive={() => onToggleActive(node)}
        onNudge={(delta) => onNudge(node, delta)}
        canExpand={children.length > 0}
        isExpanded={isExpanded}
        onToggleExpand={onToggleExpand}
      />
      {isExpanded && children.length > 0 && (
        <div className="border-t border-border/40 bg-muted/20">
          {children.map((child) => (
            <NodeRow
              key={child.id}
              node={child}
              isTopLevel={false}
              onEdit={() => onEdit(child)}
              onDelete={() => onDelete(child)}
              onToggleActive={() => onToggleActive(child)}
              onNudge={(delta) => onNudge(child, delta)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// One row (used for both top-level + child)
// ---------------------------------------------------------------------------

function NodeRow({
  node,
  isTopLevel,
  onEdit,
  onAddChild,
  onDelete,
  onToggleActive,
  onNudge,
  canExpand,
  isExpanded,
  onToggleExpand,
}: {
  node: NavigationItemNode;
  isTopLevel: boolean;
  onEdit: () => void;
  onAddChild?: () => void;
  onDelete: () => void;
  onToggleActive: () => void;
  onNudge: (delta: -1 | 1) => void;
  canExpand?: boolean;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 px-4 py-3",
        !isTopLevel && "border-t border-border/30 pl-10",
        !node.is_active && "opacity-60"
      )}
    >
      {canExpand && onToggleExpand && (
        <button
          type="button"
          onClick={onToggleExpand}
          aria-label={isExpanded ? "Collapse children" : "Expand children"}
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md hover:bg-muted"
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
      )}

      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 truncate font-medium leading-tight">
          <span className="truncate">{node.label}</span>
          {node.mega_kind && (
            <span className="inline-flex items-center rounded-full border border-pug-gold-500/40 bg-pug-gold-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-pug-gold-700 dark:text-pug-gold-300">
              Mega: {node.mega_kind}
            </span>
          )}
          {node.open_in_new_tab && (
            <span title="Opens in new tab">
              <ExternalLink className="h-3 w-3 text-muted-foreground" />
            </span>
          )}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {node.href}
          {node.description && (
            <span className="ml-2 italic">· {node.description}</span>
          )}
        </p>
      </div>

      <span className="hidden text-[11px] font-mono text-muted-foreground sm:inline">
        #{node.display_order}
      </span>

      <div className="inline-flex items-center gap-1">
        <Button
          size="icon"
          variant="ghost"
          onClick={() => onNudge(-1)}
          aria-label="Move up"
          title="Decrease display order"
        >
          <ArrowUpToLine className="h-3.5 w-3.5" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={() => onNudge(1)}
          aria-label="Move down"
          title="Increase display order"
        >
          <ArrowDownToLine className="h-3.5 w-3.5" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={onToggleActive}
          aria-label={node.is_active ? "Disable item" : "Enable item"}
          title={
            node.is_active ? "Hide from public site" : "Show on public site"
          }
        >
          {node.is_active ? (
            <Eye className="h-4 w-4" />
          ) : (
            <EyeOff className="h-4 w-4 text-muted-foreground" />
          )}
        </Button>
        {isTopLevel && onAddChild && (
          <Button
            size="icon"
            variant="ghost"
            onClick={onAddChild}
            aria-label={`Add child to ${node.label}`}
            title="Add a dropdown item under this entry"
          >
            <Plus className="h-4 w-4" />
          </Button>
        )}
        <Button
          size="icon"
          variant="ghost"
          onClick={onEdit}
          aria-label={`Edit ${node.label}`}
        >
          <Edit3 className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={onDelete}
          aria-label={`Delete ${node.label}`}
          className="text-rose-600 hover:text-rose-700"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Drawer
// ---------------------------------------------------------------------------

function Drawer({
  editing,
  form,
  setForm,
  parentOptions,
  saving,
  error,
  onClose,
  onSave,
}: {
  editing: NavigationItemNode | null;
  form: FormState;
  setForm: React.Dispatch<React.SetStateAction<FormState>>;
  parentOptions: NavigationItemNode[];
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSave: () => void;
}) {
  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  // Hide the "parent" picker once an item exists with children — moving
  // a parent under another parent isn't supported by the backend.
  const canEditParent =
    !editing || (editing.children ?? []).length === 0;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={editing ? "Edit menu item" : "Create menu item"}
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
            {editing ? `Edit "${editing.label}"` : "New menu item"}
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

          <Field label="Label" required>
            <Input
              required
              value={form.label}
              onChange={(e) => set("label", e.target.value)}
              disabled={saving}
              placeholder="About Us"
              maxLength={120}
            />
          </Field>

          <Field
            label="URL"
            required
            hint="Use a relative path like /about, an anchor like /about#leadership, or a full https URL."
          >
            <Input
              required
              value={form.href}
              onChange={(e) => set("href", e.target.value)}
              disabled={saving}
              placeholder="/about"
              maxLength={500}
            />
          </Field>

          <Field
            label="Dropdown description (child items only)"
            hint="Optional secondary line shown under the label inside the parent dropdown."
          >
            <Input
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              disabled={saving}
              maxLength={255}
              placeholder="Vision, mission, and core values"
            />
          </Field>

          {canEditParent && (
            <Field
              label="Parent"
              hint="Children appear as items inside the parent's dropdown."
            >
              <Select
                value={form.parent_id ?? ""}
                onChange={(e) =>
                  set(
                    "parent_id",
                    e.target.value ? Number(e.target.value) : null
                  )
                }
                disabled={saving}
              >
                <option value="">— Top-level item —</option>
                {parentOptions
                  .filter((p) => !editing || p.id !== editing.id)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
              </Select>
            </Field>
          )}

          {!form.parent_id && (
            <Field
              label="Mega menu"
              hint="When set, this item renders a custom mega menu instead of a standard dropdown. Currently only the Group Companies mega menu is supported."
            >
              <Select
                value={form.mega_kind}
                onChange={(e) =>
                  set(
                    "mega_kind",
                    (e.target.value as NavMegaKind | "") || ""
                  )
                }
                disabled={saving}
              >
                <option value="">— None (standard dropdown) —</option>
                <option value="companies">Companies mega menu</option>
              </Select>
            </Field>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Display order" hint="Lower numbers appear first.">
              <Input
                type="number"
                value={form.display_order}
                onChange={(e) =>
                  set("display_order", Number(e.target.value) || 0)
                }
                disabled={saving}
              />
            </Field>
            <Field label="Behaviour">
              <div className="flex flex-col gap-2 pt-2">
                <label className="inline-flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                    checked={form.is_active}
                    onChange={(e) => set("is_active", e.target.checked)}
                    disabled={saving}
                  />
                  Show on public site
                </label>
                <label className="inline-flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                    checked={form.open_in_new_tab}
                    onChange={(e) =>
                      set("open_in_new_tab", e.target.checked)
                    }
                    disabled={saving}
                  />
                  Open in new tab
                </label>
              </div>
            </Field>
          </div>
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
            {saving ? "Saving…" : editing ? "Save changes" : "Create item"}
          </Button>
        </footer>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tiny helpers
// ---------------------------------------------------------------------------

function Field({
  label,
  children,
  hint,
  required,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
  required?: boolean;
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
    const t = setTimeout(onClose, 3000);
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
