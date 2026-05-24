"use client";

import * as React from "react";
import { CheckCircle2, Edit3, Loader2, Megaphone, Plus, Trash2, X } from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { ImageUpload } from "@/components/admin/image-upload";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
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
import type { NewsCategory, NewsItem } from "@/lib/admin/types";

interface NewsForm {
  slug: string;
  title: string;
  summary: string;
  body: string;
  category: NewsCategory;
  author: string;
  cover: string;
  cover_image_url: string;
  published_at: string; // yyyy-mm-dd
  is_featured: boolean;
  is_published: boolean;
}

const EMPTY: NewsForm = {
  slug: "",
  title: "",
  summary: "",
  body: "",
  category: "company",
  author: "",
  cover: "from-pug-green-600 to-pug-gold-500",
  cover_image_url: "",
  published_at: new Date().toISOString().slice(0, 10),
  is_featured: false,
  is_published: true,
};

export default function NewsAdminPage() {
  const [items, setItems] = React.useState<NewsItem[] | null>(null);
  const [editing, setEditing] = React.useState<NewsItem | null>(null);
  const [form, setForm] = React.useState<NewsForm>(EMPTY);
  const [open, setOpen] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  React.useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setItems(null);
    try {
      setItems(await adminApi.get<NewsItem[]>("/admin/cms/news"));
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

  function openEdit(item: NewsItem) {
    setEditing(item);
    setForm({
      slug: item.slug,
      title: item.title,
      summary: item.summary ?? "",
      body: item.body ?? "",
      category: item.category,
      author: item.author ?? "",
      cover: item.cover,
      cover_image_url: item.cover_image_url ?? "",
      published_at: item.published_at.slice(0, 10),
      is_featured: item.is_featured,
      is_published: item.is_published,
    });
    setError(null);
    setOpen(true);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const body = {
        slug: form.slug.trim(),
        title: form.title.trim(),
        summary: form.summary.trim() || null,
        body: form.body.trim() || null,
        category: form.category,
        author: form.author.trim() || null,
        cover: form.cover.trim(),
        cover_image_url: form.cover_image_url.trim() || null,
        published_at: new Date(form.published_at).toISOString(),
        is_featured: form.is_featured,
        is_published: form.is_published,
      };
      if (editing) {
        await adminApi.patch(`/admin/cms/news/${editing.id}`, body);
        setToast(`Updated “${body.title}”.`);
      } else {
        await adminApi.post("/admin/cms/news", body);
        setToast(`Created “${body.title}”.`);
      }
      setOpen(false);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(item: NewsItem) {
    if (!confirm(`Delete “${item.title}”?`)) return;
    try {
      await adminApi.delete(`/admin/cms/news/${item.id}`);
      setToast(`Deleted.`);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  return (
    <AdminShell
      title="News & events"
      description="Manage articles, announcements, and CSR updates."
      actions={
        <Button onClick={openNew} size="sm">
          <Plus className="h-4 w-4" />
          New article
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
          Loading articles…
        </p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={Megaphone}
          title="No articles yet"
          description="Publish news, events, press releases, and CSR updates from here."
          action={<Button onClick={openNew} size="sm"><Plus className="h-4 w-4" />New article</Button>}
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead className="w-32">Category</TableHead>
                <TableHead className="hidden md:table-cell w-32">Published</TableHead>
                <TableHead className="w-32">Status</TableHead>
                <TableHead className="w-24 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <p className="font-medium leading-tight">{item.title}</p>
                    <p className="text-xs text-muted-foreground">/{item.slug}</p>
                  </TableCell>
                  <TableCell>
                    <Badge variant="soft" className="capitalize">{item.category}</Badge>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-muted-foreground">
                    {new Date(item.published_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    {item.is_published ? (
                      item.is_featured ? (
                        <Badge variant="warning">Featured</Badge>
                      ) : (
                        <Badge variant="success">Published</Badge>
                      )
                    ) : (
                      <Badge variant="muted">Draft</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button size="icon" variant="ghost" onClick={() => openEdit(item)} aria-label={`Edit ${item.title}`}>
                      <Edit3 className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => remove(item)} aria-label={`Delete ${item.title}`} className="text-rose-600 hover:text-rose-700">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <NewsDrawer
        open={open}
        title={editing ? "Edit article" : "New article"}
        form={form}
        onChange={setForm}
        onClose={() => setOpen(false)}
        onSave={save}
        saving={saving}
      />
    </AdminShell>
  );
}

function NewsDrawer({
  open,
  title,
  form,
  onChange,
  onClose,
  onSave,
  saving,
}: {
  open: boolean;
  title: string;
  form: NewsForm;
  onChange: (next: NewsForm) => void;
  onClose: () => void;
  onSave: () => void;
  saving: boolean;
}) {
  if (!open) return null;
  function set<K extends keyof NewsForm>(k: K, v: NewsForm[K]) {
    onChange({ ...form, [k]: v });
  }
  return (
    <div role="dialog" aria-modal="true" className="fixed inset-0 z-40 flex">
      <div className="flex-1 bg-background/50 backdrop-blur-sm" onClick={onClose} aria-hidden />
      <div className="flex w-full max-w-xl flex-col bg-background shadow-2xl">
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">{title}</h2>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close">
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
              <Labeled label="Title" required>
                <Input required value={form.title} onChange={(e) => set("title", e.target.value)} disabled={saving} />
              </Labeled>
              <Labeled label="Slug" required hint="lowercase, dashes only">
                <Input required pattern="^[a-z0-9-]+$" value={form.slug} onChange={(e) => set("slug", e.target.value)} disabled={saving} />
              </Labeled>
              <Labeled label="Category" required>
                <Select value={form.category} onChange={(e) => set("category", e.target.value as NewsCategory)} disabled={saving}>
                  <option value="company">Company</option>
                  <option value="event">Event</option>
                  <option value="press">Press</option>
                  <option value="csr">CSR</option>
                </Select>
              </Labeled>
              <Labeled label="Author">
                <Input value={form.author} onChange={(e) => set("author", e.target.value)} disabled={saving} />
              </Labeled>
              <Labeled label="Cover gradient" hint="Tailwind from-… to-…">
                <Input value={form.cover} onChange={(e) => set("cover", e.target.value)} disabled={saving} />
              </Labeled>
              <Labeled label="Published on">
                <Input type="date" value={form.published_at} onChange={(e) => set("published_at", e.target.value)} disabled={saving} />
              </Labeled>
            </div>
            <div className="space-y-1.5">
              <Label>Cover image</Label>
              <ImageUpload
                value={form.cover_image_url}
                onChange={(url) => set("cover_image_url", url ?? "")}
                disabled={saving}
              />
              <p className="text-[11px] text-muted-foreground">
                Used on the news card and article hero. The gradient is shown
                only when no image is set.
              </p>
            </div>
            <Labeled label="Summary" hint="One-line preview">
              <Input value={form.summary} onChange={(e) => set("summary", e.target.value)} disabled={saving} />
            </Labeled>
            <Labeled label="Body">
              <Textarea rows={8} value={form.body} onChange={(e) => set("body", e.target.value)} disabled={saving} />
            </Labeled>
            <div className="flex flex-wrap gap-4">
              <label className="inline-flex items-center gap-2 text-sm">
                <input type="checkbox" className="h-4 w-4 rounded border-border text-primary focus:ring-ring" checked={form.is_published} onChange={(e) => set("is_published", e.target.checked)} disabled={saving} />
                Published
              </label>
              <label className="inline-flex items-center gap-2 text-sm">
                <input type="checkbox" className="h-4 w-4 rounded border-border text-primary focus:ring-ring" checked={form.is_featured} onChange={(e) => set("is_featured", e.target.checked)} disabled={saving} />
                Featured
              </label>
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
