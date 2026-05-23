"use client";

import * as React from "react";
import { CheckCircle2, Edit3, Loader2, Plus, Sparkles, Trash2, X } from "lucide-react";

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
import type { HeroSlide } from "@/lib/admin/types";
import { cn } from "@/lib/utils";

interface SlideForm {
  eyebrow: string;
  title: string;
  description: string;
  cta_label: string;
  cta_href: string;
  secondary_cta_label: string;
  secondary_cta_href: string;
  gradient: string;
  display_order: number;
  is_active: boolean;
}

const EMPTY: SlideForm = {
  eyebrow: "",
  title: "",
  description: "",
  cta_label: "",
  cta_href: "",
  secondary_cta_label: "",
  secondary_cta_href: "",
  gradient: "from-pug-green-700 via-pug-green-500 to-pug-gold-500",
  display_order: 0,
  is_active: true,
};

export default function HeroSlidesAdminPage() {
  const [items, setItems] = React.useState<HeroSlide[] | null>(null);
  const [editing, setEditing] = React.useState<HeroSlide | null>(null);
  const [form, setForm] = React.useState<SlideForm>(EMPTY);
  const [open, setOpen] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  React.useEffect(() => { refresh(); }, []);

  async function refresh() {
    setItems(null);
    try {
      setItems(await adminApi.get<HeroSlide[]>("/admin/cms/hero-slides"));
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setError(null);
    setOpen(true);
  }

  function openEdit(item: HeroSlide) {
    setEditing(item);
    setForm({
      eyebrow: item.eyebrow ?? "",
      title: item.title,
      description: item.description ?? "",
      cta_label: item.cta_label ?? "",
      cta_href: item.cta_href ?? "",
      secondary_cta_label: item.secondary_cta_label ?? "",
      secondary_cta_href: item.secondary_cta_href ?? "",
      gradient: item.gradient,
      display_order: item.display_order,
      is_active: item.is_active,
    });
    setError(null);
    setOpen(true);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const body = {
        ...form,
        eyebrow: form.eyebrow.trim() || null,
        description: form.description.trim() || null,
        cta_label: form.cta_label.trim() || null,
        cta_href: form.cta_href.trim() || null,
        secondary_cta_label: form.secondary_cta_label.trim() || null,
        secondary_cta_href: form.secondary_cta_href.trim() || null,
        title: form.title.trim(),
        gradient: form.gradient.trim(),
        display_order: Number(form.display_order) || 0,
      };
      if (editing) {
        await adminApi.patch(`/admin/cms/hero-slides/${editing.id}`, body);
        setToast(`Updated slide.`);
      } else {
        await adminApi.post("/admin/cms/hero-slides", body);
        setToast(`Slide created.`);
      }
      setOpen(false);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(item: HeroSlide) {
    if (!confirm(`Delete slide “${item.title}”?`)) return;
    try {
      await adminApi.delete(`/admin/cms/hero-slides/${item.id}`);
      setToast(`Slide deleted.`);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  return (
    <AdminShell
      title="Hero slides"
      description="Auto-rotating banners on the public home page."
      actions={
        <Button onClick={openNew} size="sm">
          <Plus className="h-4 w-4" />
          New slide
        </Button>
      }
    >
      <Toast message={toast} onClose={() => setToast(null)} />
      {error && (
        <div role="alert" className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">
          {error}
        </div>
      )}

      {items === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading slides…
        </p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="No hero slides yet"
          description="Add a slide to populate the rotating banner on the home page."
          action={<Button onClick={openNew} size="sm"><Plus className="h-4 w-4" />New slide</Button>}
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Slide</TableHead>
                <TableHead className="hidden md:table-cell">CTAs</TableHead>
                <TableHead className="w-24">Order</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead className="w-24 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((slide) => (
                <TableRow key={slide.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <span className={cn("inline-block h-9 w-12 shrink-0 rounded-md bg-gradient-to-br", slide.gradient)} aria-hidden />
                      <div className="min-w-0">
                        <p className="truncate font-medium">{slide.title}</p>
                        {slide.eyebrow && (
                          <p className="truncate text-xs text-muted-foreground">{slide.eyebrow}</p>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-xs text-muted-foreground">
                    {slide.cta_label || "—"}
                    {slide.secondary_cta_label && (
                      <span className="ml-1">/ {slide.secondary_cta_label}</span>
                    )}
                  </TableCell>
                  <TableCell>{slide.display_order}</TableCell>
                  <TableCell>{slide.is_active ? <Badge variant="success">Active</Badge> : <Badge variant="muted">Hidden</Badge>}</TableCell>
                  <TableCell className="text-right">
                    <Button size="icon" variant="ghost" onClick={() => openEdit(slide)} aria-label="Edit slide">
                      <Edit3 className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => remove(slide)} aria-label="Delete slide" className="text-rose-600 hover:text-rose-700">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <SlideDrawer
        open={open}
        title={editing ? "Edit slide" : "New slide"}
        form={form}
        onChange={setForm}
        onClose={() => setOpen(false)}
        onSave={save}
        saving={saving}
      />
    </AdminShell>
  );
}

function SlideDrawer({ open, title, form, onChange, onClose, onSave, saving }: {
  open: boolean; title: string; form: SlideForm; onChange: (next: SlideForm) => void;
  onClose: () => void; onSave: () => void; saving: boolean;
}) {
  if (!open) return null;
  function set<K extends keyof SlideForm>(k: K, v: SlideForm[K]) { onChange({ ...form, [k]: v }); }
  return (
    <div role="dialog" aria-modal="true" className="fixed inset-0 z-40 flex">
      <div className="flex-1 bg-background/50 backdrop-blur-sm" onClick={onClose} aria-hidden />
      <div className="flex w-full max-w-xl flex-col bg-background shadow-2xl">
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">{title}</h2>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></Button>
        </header>
        <form className="flex flex-1 flex-col overflow-y-auto" onSubmit={(e) => { e.preventDefault(); onSave(); }}>
          <div className="flex-1 space-y-4 p-5">
            <Labeled label="Title" required>
              <Input required value={form.title} onChange={(e) => set("title", e.target.value)} disabled={saving} />
            </Labeled>
            <Labeled label="Eyebrow"><Input value={form.eyebrow} onChange={(e) => set("eyebrow", e.target.value)} disabled={saving} /></Labeled>
            <Labeled label="Description"><Textarea rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} disabled={saving} /></Labeled>
            <div className="grid gap-3 sm:grid-cols-2">
              <Labeled label="Primary CTA label"><Input value={form.cta_label} onChange={(e) => set("cta_label", e.target.value)} disabled={saving} /></Labeled>
              <Labeled label="Primary CTA URL"><Input value={form.cta_href} onChange={(e) => set("cta_href", e.target.value)} disabled={saving} /></Labeled>
              <Labeled label="Secondary CTA label"><Input value={form.secondary_cta_label} onChange={(e) => set("secondary_cta_label", e.target.value)} disabled={saving} /></Labeled>
              <Labeled label="Secondary CTA URL"><Input value={form.secondary_cta_href} onChange={(e) => set("secondary_cta_href", e.target.value)} disabled={saving} /></Labeled>
            </div>
            <Labeled label="Gradient" hint="Tailwind from-… via-… to-… classes">
              <Input value={form.gradient} onChange={(e) => set("gradient", e.target.value)} disabled={saving} />
            </Labeled>
            <div className="grid gap-3 sm:grid-cols-2">
              <Labeled label="Display order">
                <Input type="number" value={form.display_order} onChange={(e) => set("display_order", Number(e.target.value) || 0)} disabled={saving} />
              </Labeled>
              <Labeled label="Active">
                <label className="inline-flex items-center gap-2 pt-2 text-sm">
                  <input type="checkbox" className="h-4 w-4 rounded border-border text-primary focus:ring-ring" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} disabled={saving} />
                  Show on home page
                </label>
              </Labeled>
            </div>
          </div>
          <footer className="flex items-center justify-end gap-2 border-t border-border/60 px-5 py-3">
            <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>Cancel</Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {saving ? "Saving…" : "Save"}
            </Button>
          </footer>
        </form>
      </div>
    </div>
  );
}

function Labeled({ label, children, hint, required }: { label: string; children: React.ReactNode; hint?: string; required?: boolean }) {
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

function Toast({ message, onClose }: { message: string | null; onClose: () => void }) {
  React.useEffect(() => {
    if (!message) return;
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [message, onClose]);
  if (!message) return null;
  return (
    <div role="status" className="mb-4 inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-200">
      <CheckCircle2 className="h-4 w-4" />
      {message}
    </div>
  );
}
