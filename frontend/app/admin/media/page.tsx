"use client";

import * as React from "react";
import Image from "next/image";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Copy,
  Filter,
  Image as ImageIcon,
  Loader2,
  Pencil,
  Search,
  Trash2,
  Upload,
  Video,
  X,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";
import type { MediaAsset, MediaUploadResult } from "@/lib/admin/types";


export default function MediaAdminPage() {
  const [items, setItems] = React.useState<MediaAsset[] | null>(null);
  const [query, setQuery] = React.useState("");
  const [kind, setKind] = React.useState<"" | "image" | "video">("");
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [editing, setEditing] = React.useState<MediaAsset | null>(null);
  const fileRef = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  async function refresh() {
    setItems(null);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (kind) params.set("kind", kind);
      if (query.trim()) params.set("q", query.trim());
      const url = `/admin/cms/media${params.toString() ? `?${params}` : ""}`;
      const list = await adminApi.get<MediaAsset[]>(url);
      setItems(list);
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setError(null);
    setUploading(true);
    let dedupes = 0;
    let uploads = 0;
    for (const file of Array.from(files)) {
      try {
        const result = await adminApi.uploadMedia<MediaUploadResult>(file);
        if (result.deduped) dedupes++;
        else uploads++;
      } catch (err) {
        setError((err as AdminApiError).message);
        break;
      }
    }
    setUploading(false);
    if (uploads || dedupes) {
      setToast(
        `${uploads} new file${uploads === 1 ? "" : "s"} uploaded` +
          (dedupes ? `, ${dedupes} already in the library` : "") +
          "."
      );
      await refresh();
    }
  }

  async function remove(asset: MediaAsset) {
    if (
      !confirm(
        `Delete "${asset.title ?? asset.original_name ?? asset.filename}"? This cannot be undone.`
      )
    ) {
      return;
    }
    try {
      await adminApi.delete(`/admin/cms/media/${asset.id}`);
      setToast("Deleted.");
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  return (
    <AdminShell
      title="Media gallery"
      description="Every image and video uploaded through the CMS, in one place."
      actions={
        <>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept="image/*,video/*"
            className="hidden"
            onChange={(e) => {
              void handleFiles(e.target.files);
              e.target.value = "";
            }}
          />
          <Button
            size="sm"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            Upload
          </Button>
        </>
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

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void refresh();
        }}
        className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border/60 bg-background/60 p-4 backdrop-blur"
      >
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="media-search" className="text-xs uppercase tracking-wider text-muted-foreground">
            Search
          </Label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="media-search"
              placeholder="Filename, title, alt text, or tags"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs uppercase tracking-wider text-muted-foreground">
            <Filter className="mr-1 inline h-3 w-3" />
            Type
          </Label>
          <Select
            value={kind}
            onChange={(e) => setKind(e.target.value as "" | "image" | "video")}
            className="w-32"
          >
            <option value="">All</option>
            <option value="image">Images</option>
            <option value="video">Videos</option>
          </Select>
        </div>
        <Button type="submit" variant="outline">Apply</Button>
      </form>

      {items === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading…
        </p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={ImageIcon}
          title="No media yet"
          description="Drop images here or use the Upload button to populate the gallery."
        />
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {items.map((asset) => (
            <MediaCard
              key={asset.id}
              asset={asset}
              onEdit={() => setEditing(asset)}
              onDelete={() => remove(asset)}
              onCopied={() => setToast("URL copied to clipboard.")}
            />
          ))}
        </div>
      )}

      {editing && (
        <EditDialog
          asset={editing}
          onClose={() => setEditing(null)}
          onSaved={(updated) => {
            setEditing(null);
            setToast("Metadata saved.");
            setItems(
              (prev) =>
                prev?.map((a) => (a.id === updated.id ? updated : a)) ?? prev
            );
          }}
        />
      )}
    </AdminShell>
  );
}


function MediaCard({
  asset,
  onEdit,
  onDelete,
  onCopied,
}: {
  asset: MediaAsset;
  onEdit: () => void;
  onDelete: () => void;
  onCopied: () => void;
}) {
  const resolved = resolveAssetUrl(asset.url) ?? asset.url;

  function copyUrl() {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      void navigator.clipboard.writeText(resolved);
      onCopied();
    }
  }

  return (
    <div className="group overflow-hidden rounded-xl border border-border/60 bg-card transition-shadow hover:shadow-md">
      <div className="relative aspect-video w-full overflow-hidden bg-muted">
        {asset.kind === "video" ? (
          <video
            src={resolved}
            controls
            preload="metadata"
            className="h-full w-full object-cover"
          />
        ) : (
          <Image
            src={resolved}
            alt={asset.alt_text ?? asset.original_name ?? asset.filename}
            fill
            sizes="(min-width: 1280px) 20vw, (min-width: 768px) 33vw, 50vw"
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            unoptimized
          />
        )}
        <span
          className={cn(
            "absolute right-2 top-2 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider backdrop-blur",
            asset.kind === "video"
              ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
              : "border-primary/30 bg-primary/10 text-primary"
          )}
        >
          {asset.kind === "video" ? (
            <Video className="h-3 w-3" />
          ) : (
            <ImageIcon className="h-3 w-3" />
          )}
          {asset.kind}
        </span>
      </div>
      <div className="space-y-1 p-3">
        <p className="truncate text-sm font-medium">
          {asset.title ?? asset.original_name ?? asset.filename}
        </p>
        <p className="truncate text-[11px] text-muted-foreground">
          {formatBytes(asset.file_size)} · {asset.mime_type ?? "—"}
        </p>
        {asset.tags && (
          <p className="flex flex-wrap gap-1 pt-1 text-[10px]">
            {asset.tags
              .split(",")
              .map((t) => t.trim())
              .filter(Boolean)
              .slice(0, 4)
              .map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-muted px-1.5 py-0.5 font-medium uppercase tracking-wider"
                >
                  {tag}
                </span>
              ))}
          </p>
        )}
      </div>
      <div className="flex justify-end gap-1 border-t border-border/60 bg-background/40 px-2 py-1.5">
        <Button
          size="sm"
          variant="ghost"
          onClick={copyUrl}
          className="px-2 text-xs"
        >
          <Copy className="h-3 w-3" />
          Copy URL
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onEdit}
          className="px-2 text-xs"
        >
          <Pencil className="h-3 w-3" />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onDelete}
          className="px-2 text-xs text-rose-600 hover:text-rose-700"
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}


function EditDialog({
  asset,
  onClose,
  onSaved,
}: {
  asset: MediaAsset;
  onClose: () => void;
  onSaved: (updated: MediaAsset) => void;
}) {
  const [title, setTitle] = React.useState(asset.title ?? "");
  const [altText, setAltText] = React.useState(asset.alt_text ?? "");
  const [tags, setTags] = React.useState(asset.tags ?? "");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await adminApi.patch<MediaAsset>(
        `/admin/cms/media/${asset.id}`,
        {
          title: title.trim() || null,
          alt_text: altText.trim() || null,
          tags: tags.trim() || null,
        }
      );
      onSaved(updated);
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
      aria-label="Edit media asset"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 backdrop-blur-sm p-4"
    >
      <form
        onSubmit={save}
        className="w-full max-w-md space-y-4 rounded-xl border border-border/60 bg-background p-5 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Edit metadata</h3>
            <p className="truncate text-xs text-muted-foreground">
              {asset.original_name ?? asset.filename}
            </p>
          </div>
          <Button type="button" size="icon" variant="ghost" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="space-y-1.5">
          <Label>Title</Label>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Hypermarket hero shot"
            disabled={saving}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Alt text (for accessibility)</Label>
          <Textarea
            rows={2}
            value={altText}
            onChange={(e) => setAltText(e.target.value)}
            placeholder="A short description of what's in the image."
            disabled={saving}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Tags (comma-separated)</Label>
          <Input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="brand, hero, retail"
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

        <footer className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Save
          </Button>
        </footer>
      </form>
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


function formatBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
