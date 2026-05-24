"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Edit3,
  ExternalLink,
  Eye,
  EyeOff,
  FileText,
  Loader2,
  Plus,
  Save,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";

import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { ImageUpload } from "@/components/admin/image-upload";
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
import type { CMSPage, CMSPageListItem } from "@/lib/admin/types";


interface PageForm {
  slug: string;
  title: string;
  eyebrow: string;
  summary: string;
  body: string;
  banner_image_url: string;
  banner_mobile_url: string;
  seo_title: string;
  seo_description: string;
  seo_keywords: string;
  is_published: boolean;
  display_order: number;
}

const EMPTY: PageForm = {
  slug: "",
  title: "",
  eyebrow: "",
  summary: "",
  body: "",
  banner_image_url: "",
  banner_mobile_url: "",
  seo_title: "",
  seo_description: "",
  seo_keywords: "",
  is_published: false,
  display_order: 0,
};


export default function PagesAdminPage() {
  const [items, setItems] = React.useState<CMSPageListItem[] | null>(null);
  const [editing, setEditing] = React.useState<CMSPage | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [form, setForm] = React.useState<PageForm>(EMPTY);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  React.useEffect(() => {
    void refresh();
  }, []);

  async function refresh() {
    setItems(null);
    setError(null);
    try {
      setItems(await adminApi.get<CMSPageListItem[]>("/admin/cms/pages"));
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setError(null);
    setDrawerOpen(true);
  }

  async function openEdit(row: CMSPageListItem) {
    setError(null);
    try {
      const full = await adminApi.get<CMSPage>(`/admin/cms/pages/${row.id}`);
      setEditing(full);
      setForm({
        slug: full.slug,
        title: full.title,
        eyebrow: full.eyebrow ?? "",
        summary: full.summary ?? "",
        body: full.body ?? "",
        banner_image_url: full.banner_image_url ?? "",
        banner_mobile_url: full.banner_mobile_url ?? "",
        seo_title: full.seo_title ?? "",
        seo_description: full.seo_description ?? "",
        seo_keywords: full.seo_keywords ?? "",
        is_published: full.is_published,
        display_order: full.display_order,
      });
      setDrawerOpen(true);
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const body = {
        slug: form.slug.trim(),
        title: form.title.trim(),
        eyebrow: form.eyebrow.trim() || null,
        summary: form.summary.trim() || null,
        body: form.body || null,
        banner_image_url: form.banner_image_url.trim() || null,
        banner_mobile_url: form.banner_mobile_url.trim() || null,
        seo_title: form.seo_title.trim() || null,
        seo_description: form.seo_description.trim() || null,
        seo_keywords: form.seo_keywords.trim() || null,
        is_published: form.is_published,
        display_order: Number(form.display_order) || 0,
      };
      if (editing) {
        await adminApi.patch(`/admin/cms/pages/${editing.id}`, body);
        setToast(`Updated "${body.title}".`);
      } else {
        await adminApi.post("/admin/cms/pages", body);
        setToast(`Created "${body.title}".`);
      }
      setDrawerOpen(false);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function togglePublish(row: CMSPageListItem) {
    try {
      await adminApi.patch(`/admin/cms/pages/${row.id}`, {
        is_published: !row.is_published,
      });
      setToast(
        row.is_published
          ? `"${row.title}" unpublished.`
          : `"${row.title}" published.`
      );
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function remove(row: CMSPageListItem) {
    if (!confirm(`Delete "${row.title}"? This cannot be undone.`)) return;
    try {
      await adminApi.delete(`/admin/cms/pages/${row.id}`);
      setToast("Page deleted.");
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  return (
    <AdminShell
      title="Pages"
      description="Free-form content pages like About us, Privacy policy, etc."
      actions={
        <Button onClick={openNew} size="sm" aria-label="Add a new page">
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New page</span>
        </Button>
      }
    >
      <Toast message={toast} onClose={() => setToast(null)} />
      {error && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          <AlertTriangle className="mr-1 inline h-3.5 w-3.5" />
          {error}
        </div>
      )}

      {items === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading…
        </p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No pages yet"
          description="Use New page to add ad-hoc content like privacy policy or careers landing."
          action={
            <Button onClick={openNew} size="sm">
              <Plus className="h-4 w-4" />
              New page
            </Button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead className="hidden md:table-cell">Summary</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead className="hidden lg:table-cell w-32">
                  Updated
                </TableHead>
                <TableHead className="w-40 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <p className="font-medium leading-tight">{row.title}</p>
                    <p className="text-xs text-muted-foreground">/{row.slug}</p>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-muted-foreground text-sm">
                    <p className="line-clamp-2">{row.summary ?? "—"}</p>
                  </TableCell>
                  <TableCell>
                    {row.is_published ? (
                      <Badge variant="success">Published</Badge>
                    ) : (
                      <Badge variant="muted">Draft</Badge>
                    )}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-muted-foreground text-xs">
                    {new Date(row.updated_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => togglePublish(row)}
                      title={row.is_published ? "Unpublish" : "Publish"}
                      className="px-2"
                    >
                      {row.is_published ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                    {row.is_published && (
                      <Button
                        size="sm"
                        variant="ghost"
                        asChild
                        title="View public page"
                        className="px-2"
                      >
                        <Link
                          href={`/pages/${row.slug}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </Link>
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => openEdit(row)}
                      title="Edit"
                      className="px-2"
                    >
                      <Edit3 className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => remove(row)}
                      title="Delete"
                      className="px-2 text-rose-600 hover:text-rose-700"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {drawerOpen && (
        <PageDrawer
          form={form}
          editing={editing !== null}
          onChange={setForm}
          onClose={() => setDrawerOpen(false)}
          onSave={save}
          saving={saving}
        />
      )}
    </AdminShell>
  );
}


function PageDrawer({
  form,
  editing,
  onChange,
  onClose,
  onSave,
  saving,
}: {
  form: PageForm;
  editing: boolean;
  onChange: (next: PageForm) => void;
  onClose: () => void;
  onSave: () => void;
  saving: boolean;
}) {
  function set<K extends keyof PageForm>(k: K, v: PageForm[K]) {
    onChange({ ...form, [k]: v });
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Edit page"
      className="fixed inset-0 z-40 flex"
    >
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="flex w-full max-w-2xl flex-col bg-background shadow-2xl">
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">
            {editing ? "Edit page" : "New page"}
          </h2>
          <Button size="icon" variant="ghost" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </header>
        <form
          className="flex flex-1 flex-col overflow-y-auto"
          onSubmit={(e) => {
            e.preventDefault();
            onSave();
          }}
        >
          <div className="flex-1 space-y-4 p-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Title" required>
                <Input
                  required
                  value={form.title}
                  onChange={(e) => set("title", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Slug" required hint="lowercase letters, digits, dashes">
                <Input
                  required
                  pattern="^[a-z0-9-]+$"
                  value={form.slug}
                  onChange={(e) => set("slug", e.target.value)}
                  disabled={saving}
                />
              </Field>
            </div>
            <Field label="Eyebrow" hint="Small uppercase tag above the title">
              <Input
                value={form.eyebrow}
                onChange={(e) => set("eyebrow", e.target.value)}
                disabled={saving}
              />
            </Field>
            <Field label="Summary" hint="Used in the page hero + meta description">
              <Textarea
                rows={2}
                value={form.summary}
                onChange={(e) => set("summary", e.target.value)}
                disabled={saving}
              />
            </Field>
            <Field label="Body" hint="Markdown is supported. Renders in a Tailwind prose container.">
              <Textarea
                rows={10}
                value={form.body}
                onChange={(e) => set("body", e.target.value)}
                disabled={saving}
              />
            </Field>

            <div className="space-y-2">
              <Label>Desktop banner image</Label>
              <ImageUpload
                value={form.banner_image_url}
                onChange={(url) => set("banner_image_url", url ?? "")}
                disabled={saving}
              />
            </div>
            <div className="space-y-2">
              <Label>Mobile banner image (optional)</Label>
              <ImageUpload
                value={form.banner_mobile_url}
                onChange={(url) => set("banner_mobile_url", url ?? "")}
                disabled={saving}
              />
            </div>

            <fieldset className="space-y-3 rounded-md border border-border/60 bg-background/40 p-3">
              <legend className="px-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                SEO
              </legend>
              <Field label="SEO title">
                <Input
                  value={form.seo_title}
                  onChange={(e) => set("seo_title", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="SEO description">
                <Textarea
                  rows={2}
                  value={form.seo_description}
                  onChange={(e) => set("seo_description", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Keywords" hint="Comma-separated">
                <Input
                  value={form.seo_keywords}
                  onChange={(e) => set("seo_keywords", e.target.value)}
                  disabled={saving}
                />
              </Field>
            </fieldset>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Display order">
                <Input
                  type="number"
                  value={form.display_order}
                  onChange={(e) =>
                    set("display_order", Number(e.target.value) || 0)
                  }
                  disabled={saving}
                />
              </Field>
              <Field label="Status">
                <label className="inline-flex items-center gap-2 pt-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                    checked={form.is_published}
                    onChange={(e) => set("is_published", e.target.checked)}
                    disabled={saving}
                  />
                  Publish on the public site
                </label>
              </Field>
            </div>
          </div>
          <footer className="flex items-center justify-end gap-2 border-t border-border/60 px-5 py-3">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Save
            </Button>
          </footer>
        </form>
      </div>
    </div>
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
