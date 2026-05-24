"use client";

import * as React from "react";
import { CheckCircle2, Edit3, Loader2, MessageSquareQuote, Plus, Trash2, X } from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import type { LeadershipMessage } from "@/lib/admin/types";
import { cn } from "@/lib/utils";

interface LeaderForm {
  slug: string;
  name: string;
  role: string;
  short_message: string;
  full_message: string;
  accent: string;
  initials: string;
  signature: string;
  display_order: number;
  is_active: boolean;
}

const EMPTY: LeaderForm = {
  slug: "",
  name: "",
  role: "",
  short_message: "",
  full_message: "",
  accent: "from-pug-green-600 to-pug-gold-500",
  initials: "",
  signature: "",
  display_order: 0,
  is_active: true,
};

export default function LeadershipAdminPage() {
  const [items, setItems] = React.useState<LeadershipMessage[] | null>(null);
  const [editing, setEditing] = React.useState<LeadershipMessage | null>(null);
  const [form, setForm] = React.useState<LeaderForm>(EMPTY);
  const [open, setOpen] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  React.useEffect(() => { refresh(); }, []);

  async function refresh() {
    setItems(null);
    try {
      setItems(await adminApi.get<LeadershipMessage[]>("/admin/cms/leadership"));
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  function openNew() { setEditing(null); setForm(EMPTY); setError(null); setOpen(true); }
  function openEdit(item: LeadershipMessage) {
    setEditing(item);
    setForm({
      slug: item.slug,
      name: item.name,
      role: item.role,
      short_message: item.short_message ?? "",
      full_message: item.full_message ?? "",
      accent: item.accent,
      initials: item.initials,
      signature: item.signature ?? "",
      display_order: item.display_order,
      is_active: item.is_active,
    });
    setError(null);
    setOpen(true);
  }

  async function save() {
    setSaving(true); setError(null);
    try {
      const body = {
        ...form,
        slug: form.slug.trim(),
        name: form.name.trim(),
        role: form.role.trim(),
        short_message: form.short_message.trim() || null,
        full_message: form.full_message.trim() || null,
        signature: form.signature.trim() || null,
        initials: form.initials.trim(),
        accent: form.accent.trim(),
        display_order: Number(form.display_order) || 0,
      };
      if (editing) {
        await adminApi.patch(`/admin/cms/leadership/${editing.id}`, body);
        setToast(`Updated “${body.name}”.`);
      } else {
        await adminApi.post("/admin/cms/leadership", body);
        setToast(`Added “${body.name}”.`);
      }
      setOpen(false);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(item: LeadershipMessage) {
    if (!confirm(`Delete “${item.name}”?`)) return;
    try {
      await adminApi.delete(`/admin/cms/leadership/${item.id}`);
      setToast("Deleted.");
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  return (
    <AdminShell
      title="Leadership messages"
      description="Chairman, MD, and Executive Directors messages shown on About and Home."
      actions={<Button onClick={openNew} size="sm"><Plus className="h-4 w-4" />New leader</Button>}
    >
      <Toast message={toast} onClose={() => setToast(null)} />
      {error && <div role="alert" className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">{error}</div>}

      {items === null ? (
        <p className="text-sm text-muted-foreground"><Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />Loading leadership…</p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={MessageSquareQuote}
          title="No leadership entries yet"
          description="Add the Chairman, MD, and Executive Directors here so they appear on the About and Home pages."
          action={<Button onClick={openNew} size="sm"><Plus className="h-4 w-4" />New leader</Button>}
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Person</TableHead>
                <TableHead className="hidden md:table-cell">Role</TableHead>
                <TableHead className="w-24">Order</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead className="w-24 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <span className={cn("inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br text-xs font-bold text-white", item.accent)} aria-hidden>
                        {item.initials}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate font-medium">{item.name}</p>
                        <p className="truncate text-xs text-muted-foreground md:hidden">{item.role}</p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-muted-foreground">{item.role}</TableCell>
                  <TableCell>{item.display_order}</TableCell>
                  <TableCell>{item.is_active ? <Badge variant="success">Active</Badge> : <Badge variant="muted">Hidden</Badge>}</TableCell>
                  <TableCell className="text-right">
                    <Button size="icon" variant="ghost" onClick={() => openEdit(item)} aria-label={`Edit ${item.name}`}><Edit3 className="h-4 w-4" /></Button>
                    <Button size="icon" variant="ghost" onClick={() => remove(item)} aria-label={`Delete ${item.name}`} className="text-rose-600 hover:text-rose-700"><Trash2 className="h-4 w-4" /></Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {open && (
        <div role="dialog" aria-modal="true" className="fixed inset-0 z-40 flex">
          <div className="flex-1 bg-background/50 backdrop-blur-sm" onClick={() => setOpen(false)} aria-hidden />
          <div className="flex w-full max-w-xl flex-col bg-background shadow-2xl">
            <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
              <h2 className="text-base font-semibold">{editing ? "Edit leader" : "New leader"}</h2>
              <Button size="icon" variant="ghost" onClick={() => setOpen(false)} aria-label="Close"><X className="h-4 w-4" /></Button>
            </header>
            <form className="flex flex-1 flex-col overflow-y-auto" onSubmit={(e) => { e.preventDefault(); save(); }}>
              <div className="flex-1 space-y-4 p-5">
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Name" required><Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} disabled={saving} /></Field>
                  <Field label="Slug" required hint="lowercase, dashes only"><Input required pattern="^[a-z0-9-]+$" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} disabled={saving} /></Field>
                  <Field label="Role" required><Input required value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} disabled={saving} /></Field>
                  <Field label="Initials" required><Input required maxLength={8} value={form.initials} onChange={(e) => setForm({ ...form, initials: e.target.value.toUpperCase() })} disabled={saving} /></Field>
                </div>
                <Field label="Short message"><Input value={form.short_message} onChange={(e) => setForm({ ...form, short_message: e.target.value })} disabled={saving} /></Field>
                <Field label="Full message"><Textarea rows={5} value={form.full_message} onChange={(e) => setForm({ ...form, full_message: e.target.value })} disabled={saving} /></Field>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Signature"><Input value={form.signature} onChange={(e) => setForm({ ...form, signature: e.target.value })} disabled={saving} /></Field>
                  <Field label="Portrait gradient" hint="from-… to-…"><Input value={form.accent} onChange={(e) => setForm({ ...form, accent: e.target.value })} disabled={saving} /></Field>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Order"><Input type="number" value={form.display_order} onChange={(e) => setForm({ ...form, display_order: Number(e.target.value) || 0 })} disabled={saving} /></Field>
                  <Field label="Active">
                    <label className="inline-flex items-center gap-2 pt-2 text-sm">
                      <input type="checkbox" className="h-4 w-4 rounded border-border text-primary focus:ring-ring" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} disabled={saving} />
                      Show on About + Home
                    </label>
                  </Field>
                </div>
              </div>
              <footer className="flex items-center justify-end gap-2 border-t border-border/60 px-5 py-3">
                <Button type="button" variant="ghost" onClick={() => setOpen(false)} disabled={saving}>Cancel</Button>
                <Button type="submit" disabled={saving}>{saving && <Loader2 className="h-4 w-4 animate-spin" />}{saving ? "Saving…" : "Save"}</Button>
              </footer>
            </form>
          </div>
        </div>
      )}
    </AdminShell>
  );
}

function Field({ label, children, hint, required }: { label: string; children: React.ReactNode; hint?: string; required?: boolean }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}{required && <span className="ml-0.5 text-rose-500">*</span>}</Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function Toast({ message, onClose }: { message: string | null; onClose: () => void }) {
  React.useEffect(() => {
    if (!message) return;
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [message, onClose]);
  if (!message) return null;
  return (
    <div role="status" className="mb-4 inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-200">
      <CheckCircle2 className="h-4 w-4" />{message}
    </div>
  );
}
