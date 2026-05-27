"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  CheckCircle2,
  Download,
  ExternalLink,
  Eye,
  FileUp,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
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
import type {
  Catalogue,
  CatalogueAnalytics,
  CatalogueDetail,
  CatalogueProcessingStatus,
  CatalogueUpdate,
  OfferCampaign,
} from "@/lib/admin/marketing-types";
import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";


const BASE = "/admin/marketing/catalogues";
const CAMPAIGNS = "/admin/marketing/campaigns";


// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function CataloguesPage() {
  const [rows, setRows] = React.useState<Catalogue[] | null>(null);
  const [campaigns, setCampaigns] = React.useState<OfferCampaign[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  const [search, setSearch] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState<
    "" | CatalogueProcessingStatus
  >("");
  const [campaignFilter, setCampaignFilter] = React.useState<string>("");

  const [uploading, setUploading] = React.useState(false);
  const [editing, setEditing] = React.useState<Catalogue | null>(null);
  const [viewing, setViewing] = React.useState<Catalogue | null>(null);

  React.useEffect(() => {
    void refresh();
    void loadCampaigns();
  }, []);

  async function refresh() {
    setError(null);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (statusFilter) params.set("status", statusFilter);
      if (campaignFilter) params.set("campaign_id", campaignFilter);
      const data = await adminApi.get<Catalogue[]>(
        `${BASE}?${params.toString()}`
      );
      setRows(data);
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function loadCampaigns() {
    try {
      const list = await adminApi.get<OfferCampaign[]>(
        `${CAMPAIGNS}?include_inactive=true`
      );
      setCampaigns(list);
    } catch (err) {
      // Non-fatal — the dropdown is empty but the page still loads.
      setError((err as AdminApiError).message);
    }
  }

  async function reprocess(row: Catalogue) {
    if (
      !confirm(
        `Re-render "${row.title}"? Existing page images are replaced; the source PDF on disk is reused.`
      )
    ) {
      return;
    }
    try {
      await adminApi.post(`${BASE}/${row.id}/reprocess`);
      setToast(`Re-processed "${row.title}".`);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function remove(row: Catalogue) {
    if (
      !confirm(
        `Delete catalogue "${row.title}"? All rendered pages + the source PDF will be removed from disk.`
      )
    ) {
      return;
    }
    try {
      await adminApi.delete(`${BASE}/${row.id}`);
      setToast(`Deleted "${row.title}".`);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  const campaignTitle = (id: number | null): string => {
    if (id === null) return "—";
    const found = campaigns.find((c) => c.id === id);
    return found ? found.title : `#${id}`;
  };

  return (
    <AdminShell
      title="Catalogues"
      description="Upload a PDF — we render every page to WebP and surface the catalogue inside campaigns."
      actions={
        <Button size="sm" onClick={() => setUploading(true)}>
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">Upload catalogue</span>
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

      {/* Filter bar */}
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border/60 bg-background/60 p-4 backdrop-blur">
        <div className="flex-1 min-w-[180px] space-y-1.5">
          <Label htmlFor="cat-search">Search</Label>
          <Input
            id="cat-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void refresh()}
            placeholder="Title or slug"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="cat-status">Status</Label>
          <Select
            id="cat-status"
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(e.target.value as "" | CatalogueProcessingStatus)
            }
          >
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="ready">Ready</option>
            <option value="failed">Failed</option>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="cat-campaign">Campaign</Label>
          <Select
            id="cat-campaign"
            value={campaignFilter}
            onChange={(e) => setCampaignFilter(e.target.value)}
          >
            <option value="">All</option>
            {campaigns.map((c) => (
              <option key={c.id} value={String(c.id)}>
                {c.title}
              </option>
            ))}
          </Select>
        </div>
        <Button size="sm" variant="outline" onClick={() => void refresh()}>
          Apply
        </Button>
      </div>

      {/* List */}
      {rows === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading catalogues…
        </p>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/60 p-10 text-center text-sm text-muted-foreground">
          <BookOpen className="mx-auto mb-3 h-8 w-8 opacity-50" />
          No catalogues yet. Upload a PDF to render its pages and make
          it browsable on the public site.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Catalogue</TableHead>
                <TableHead className="hidden md:table-cell">Campaign</TableHead>
                <TableHead className="w-32">Status</TableHead>
                <TableHead className="hidden lg:table-cell w-20 text-right">
                  Pages
                </TableHead>
                <TableHead className="hidden lg:table-cell w-24 text-right">
                  Views
                </TableHead>
                <TableHead className="w-44 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <div className="flex items-start gap-3">
                      {row.cover_image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={resolveAssetUrl(row.cover_image_url) ?? ""}
                          alt=""
                          className="h-14 w-10 shrink-0 rounded object-cover shadow-sm"
                        />
                      ) : (
                        <div className="flex h-14 w-10 shrink-0 items-center justify-center rounded bg-muted text-muted-foreground">
                          <BookOpen className="h-4 w-4" />
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="flex items-center gap-1.5 font-medium leading-tight">
                          {row.title}
                          {!row.is_active && (
                            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-300">
                              Inactive
                            </span>
                          )}
                        </p>
                        <p className="font-mono text-[11px] text-muted-foreground">
                          {row.slug}
                        </p>
                        {row.processing_error && (
                          <p className="line-clamp-1 text-[11px] text-rose-600 dark:text-rose-300">
                            {row.processing_error}
                          </p>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-xs">
                    {campaignTitle(row.campaign_id)}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={row.processing_status} />
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-right text-xs">
                    {row.page_count}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-right text-xs text-muted-foreground">
                    {row.view_count.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => setViewing(row)}
                        aria-label="Preview pages"
                        title="Preview"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => reprocess(row)}
                        aria-label="Re-process"
                        title="Re-render pages"
                      >
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => setEditing(row)}
                        aria-label={`Edit ${row.title}`}
                        title="Edit metadata"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => remove(row)}
                        className="text-rose-600 hover:text-rose-700"
                        aria-label={`Delete ${row.title}`}
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {uploading && (
        <UploadDialog
          campaigns={campaigns}
          onClose={() => setUploading(false)}
          onUploaded={(title) => {
            setUploading(false);
            setToast(`Uploaded "${title}".`);
            void refresh();
          }}
          onError={setError}
        />
      )}

      {editing && (
        <EditMetadataDialog
          row={editing}
          campaigns={campaigns}
          onClose={() => setEditing(null)}
          onSaved={(title) => {
            setEditing(null);
            setToast(`Updated "${title}".`);
            void refresh();
          }}
          onError={setError}
        />
      )}

      {viewing && (
        <CatalogueDetailDrawer
          row={viewing}
          onClose={() => setViewing(null)}
          onError={setError}
        />
      )}
    </AdminShell>
  );
}


// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: CatalogueProcessingStatus }) {
  const map: Record<
    CatalogueProcessingStatus,
    { label: string; cls: string; icon: React.ComponentType<{ className?: string }> }
  > = {
    pending: {
      label: "Pending",
      cls: "border-slate-500/30 bg-slate-500/10 text-slate-700 dark:text-slate-300",
      icon: Loader2,
    },
    processing: {
      label: "Processing",
      cls: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300",
      icon: Loader2,
    },
    ready: {
      label: "Ready",
      cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
      icon: CheckCircle2,
    },
    failed: {
      label: "Failed",
      cls: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
      icon: AlertTriangle,
    },
  };
  const { label, cls, icon: Icon } = map[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        cls
      )}
    >
      <Icon
        className={cn(
          "h-3 w-3",
          status === "processing" && "animate-spin"
        )}
      />
      {label}
    </span>
  );
}


// ---------------------------------------------------------------------------
// Upload dialog
// ---------------------------------------------------------------------------

function UploadDialog({
  campaigns,
  onClose,
  onUploaded,
  onError,
}: {
  campaigns: OfferCampaign[];
  onClose: () => void;
  onUploaded: (title: string) => void;
  onError: (msg: string) => void;
}) {
  const [file, setFile] = React.useState<File | null>(null);
  const [slug, setSlug] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [campaignId, setCampaignId] = React.useState<string>("");
  const [isActive, setIsActive] = React.useState(true);
  const [isFeatured, setIsFeatured] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);

  React.useEffect(() => {
    if (!title) return;
    if (slug.length > 0) return;
    setSlug(slugify(title));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title]);

  const sizeMb = file ? (file.size / (1024 * 1024)).toFixed(1) : null;
  const oversized = file !== null && file.size > 50 * 1024 * 1024;
  const canSubmit =
    !!file &&
    !oversized &&
    title.trim().length > 0 &&
    /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(slug.trim().toLowerCase()) &&
    !uploading;

  async function submit() {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("slug", slug.trim().toLowerCase());
      fd.append("title", title.trim());
      if (description.trim()) fd.append("description", description.trim());
      if (campaignId) fd.append("campaign_id", campaignId);
      fd.append("is_active", String(isActive));
      fd.append("is_featured", String(isFeatured));
      await adminApi.postMultipart<CatalogueDetail>(BASE, fd);
      onUploaded(title.trim());
    } catch (err) {
      onError((err as AdminApiError).message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Upload catalogue"
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
          if (canSubmit) submit();
        }}
        className="flex w-full max-w-lg flex-col bg-background shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">Upload catalogue</h2>
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
          {/* File picker */}
          <div className="space-y-1.5">
            <Label htmlFor="up-pdf">PDF file *</Label>
            <label
              htmlFor="up-pdf"
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-md border border-dashed px-3 py-4 text-sm",
                file
                  ? "border-emerald-500/40 bg-emerald-500/5 text-foreground"
                  : "border-input bg-background/40 text-muted-foreground hover:border-primary/40"
              )}
            >
              <FileUp className="h-4 w-4 text-primary" />
              <span className="truncate">
                {file
                  ? `${file.name} — ${sizeMb} MB`
                  : "Click to choose a PDF (max 50 MB)"}
              </span>
            </label>
            <input
              id="up-pdf"
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              disabled={uploading}
            />
            {oversized && (
              <p className="text-[11px] text-rose-600">
                Above the 50 MB cap. Compress the PDF before upload.
              </p>
            )}
            <p className="text-[11px] text-muted-foreground">
              Rendering runs synchronously — expect 5–15 seconds for a
              typical flyer. Don't close this dialog until it finishes.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="up-title">Title *</Label>
            <Input
              id="up-title"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={uploading}
              placeholder="Summer Flyer 2026"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="up-slug">URL slug *</Label>
            <Input
              id="up-slug"
              required
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              disabled={uploading}
              className="font-mono text-sm"
              placeholder="summer-flyer-2026"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="up-desc">Description</Label>
            <Textarea
              id="up-desc"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={uploading}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="up-campaign">Attach to campaign</Label>
            <Select
              id="up-campaign"
              value={campaignId}
              onChange={(e) => setCampaignId(e.target.value)}
              disabled={uploading}
            >
              <option value="">— None (standalone catalogue) —</option>
              {campaigns.map((c) => (
                <option key={c.id} value={String(c.id)}>
                  {c.title}
                </option>
              ))}
            </Select>
          </div>

          <div className="flex gap-4">
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                disabled={uploading}
              />
              Active
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                checked={isFeatured}
                onChange={(e) => setIsFeatured(e.target.checked)}
                disabled={uploading}
              />
              Featured
            </label>
          </div>
        </div>
        <footer className="flex items-center justify-end gap-2 border-t border-border/60 px-5 py-3">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={uploading}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={!canSubmit}>
            {uploading && <Loader2 className="h-4 w-4 animate-spin" />}
            {uploading ? "Rendering pages…" : "Upload + render"}
          </Button>
        </footer>
      </form>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Edit metadata dialog
// ---------------------------------------------------------------------------

function EditMetadataDialog({
  row,
  campaigns,
  onClose,
  onSaved,
  onError,
}: {
  row: Catalogue;
  campaigns: OfferCampaign[];
  onClose: () => void;
  onSaved: (title: string) => void;
  onError: (msg: string) => void;
}) {
  const [slug, setSlug] = React.useState(row.slug);
  const [title, setTitle] = React.useState(row.title);
  const [description, setDescription] = React.useState(row.description ?? "");
  const [campaignId, setCampaignId] = React.useState<string>(
    row.campaign_id != null ? String(row.campaign_id) : ""
  );
  const [isActive, setIsActive] = React.useState(row.is_active);
  const [isFeatured, setIsFeatured] = React.useState(row.is_featured);
  const [sortOrder, setSortOrder] = React.useState(row.sort_order);
  const [metaTitle, setMetaTitle] = React.useState(row.meta_title ?? "");
  const [metaDescription, setMetaDescription] = React.useState(
    row.meta_description ?? ""
  );
  const [saving, setSaving] = React.useState(false);

  async function submit() {
    setSaving(true);
    try {
      const payload: CatalogueUpdate = {
        slug: slug.trim().toLowerCase(),
        title: title.trim(),
        description: description.trim() || null,
        campaign_id: campaignId ? Number(campaignId) : null,
        is_active: isActive,
        is_featured: isFeatured,
        sort_order: Number(sortOrder) || 0,
        meta_title: metaTitle.trim() || null,
        meta_description: metaDescription.trim() || null,
      };
      await adminApi.patch(`${BASE}/${row.id}`, payload);
      onSaved(title.trim());
    } catch (err) {
      onError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" className="fixed inset-0 z-40 flex">
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!saving) submit();
        }}
        className="flex w-full max-w-lg flex-col bg-background shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">
            Edit &ldquo;{row.title}&rdquo;
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
        <div className="flex-1 space-y-3 overflow-y-auto p-5">
          <div className="space-y-1.5">
            <Label>Title</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Slug</Label>
            <Input
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              disabled={saving}
              className="font-mono text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Description</Label>
            <Textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Campaign</Label>
            <Select
              value={campaignId}
              onChange={(e) => setCampaignId(e.target.value)}
              disabled={saving}
            >
              <option value="">— None —</option>
              {campaigns.map((c) => (
                <option key={c.id} value={String(c.id)}>
                  {c.title}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Sort order</Label>
            <Input
              type="number"
              value={sortOrder}
              onChange={(e) => setSortOrder(Number(e.target.value))}
              disabled={saving}
            />
          </div>
          <div className="flex gap-4">
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                disabled={saving}
              />
              Active
            </label>
            <label className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                checked={isFeatured}
                onChange={(e) => setIsFeatured(e.target.checked)}
                disabled={saving}
              />
              Featured
            </label>
          </div>
          <div className="space-y-1.5">
            <Label>Meta title</Label>
            <Input
              value={metaTitle}
              onChange={(e) => setMetaTitle(e.target.value)}
              disabled={saving}
              maxLength={200}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Meta description</Label>
            <Textarea
              rows={2}
              value={metaDescription}
              onChange={(e) => setMetaDescription(e.target.value)}
              disabled={saving}
              maxLength={500}
            />
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
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </footer>
      </form>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Detail drawer — page thumbnails + analytics
// ---------------------------------------------------------------------------

function CatalogueDetailDrawer({
  row,
  onClose,
  onError,
}: {
  row: Catalogue;
  onClose: () => void;
  onError: (msg: string) => void;
}) {
  const [detail, setDetail] = React.useState<CatalogueDetail | null>(null);
  const [analytics, setAnalytics] = React.useState<CatalogueAnalytics | null>(
    null
  );

  React.useEffect(() => {
    async function load() {
      try {
        const [d, a] = await Promise.all([
          adminApi.get<CatalogueDetail>(`${BASE}/${row.id}`),
          adminApi.get<CatalogueAnalytics>(`${BASE}/${row.id}/analytics`),
        ]);
        setDetail(d);
        setAnalytics(a);
      } catch (err) {
        onError((err as AdminApiError).message);
      }
    }
    void load();
  }, [row.id, onError]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Preview ${row.title}`}
      className="fixed inset-0 z-40 flex"
    >
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="flex w-full max-w-3xl flex-col bg-background shadow-2xl">
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold">{row.title}</h2>
            <p className="font-mono text-[11px] text-muted-foreground">
              {row.slug}
            </p>
          </div>
          <div className="inline-flex items-center gap-2">
            {row.pdf_url && (
              <Button asChild size="sm" variant="outline">
                <Link
                  href={`/api/v1/offers/catalogues/${row.id}/download`}
                  target="_blank"
                >
                  <Download className="h-3.5 w-3.5" />
                  Source PDF
                </Link>
              </Button>
            )}
            <Button asChild size="sm" variant="outline">
              <Link href={`/offers/catalogues/${row.slug}`} target="_blank">
                <ExternalLink className="h-3.5 w-3.5" />
                Public viewer
              </Link>
            </Button>
            <Button
              size="icon"
              variant="ghost"
              onClick={onClose}
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          {/* Analytics row */}
          {analytics && (
            <section>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Analytics
              </p>
              <div className="grid grid-cols-3 gap-3">
                <Metric
                  icon={Eye}
                  label="Total views"
                  value={analytics.total_views.toLocaleString()}
                />
                <Metric
                  icon={BarChart3}
                  label="Unique sessions"
                  value={analytics.unique_sessions.toLocaleString()}
                />
                <Metric
                  icon={Download}
                  label="Downloads"
                  value={row.download_count.toLocaleString()}
                />
              </div>
              {Object.keys(analytics.by_device).length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                  {Object.entries(analytics.by_device).map(([d, n]) => (
                    <span
                      key={d}
                      className="rounded-full border border-border/60 bg-muted/30 px-2 py-0.5"
                    >
                      {d}: {n}
                    </span>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Page thumbnails */}
          <section>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Pages ({row.page_count})
            </p>
            {detail === null ? (
              <p className="text-sm text-muted-foreground">
                <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
                Loading pages…
              </p>
            ) : detail.pages.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No rendered pages yet — re-process the catalogue from the
                list view.
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                {detail.pages.map((p) => (
                  <a
                    key={p.page_number}
                    href={resolveAssetUrl(p.image_url) ?? p.image_url}
                    target="_blank"
                    rel="noreferrer"
                    className="group block overflow-hidden rounded-md border border-border/60 bg-background"
                    title={`Open page ${p.page_number} full-size`}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={resolveAssetUrl(p.thumbnail_url) ?? ""}
                      alt={`Page ${p.page_number}`}
                      className="aspect-[2/3] w-full object-cover transition-transform group-hover:scale-[1.02]"
                    />
                    <p className="px-2 py-1 text-center text-[11px] text-muted-foreground">
                      Page {p.page_number}
                    </p>
                  </a>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md border border-border/60 bg-background/40 p-3">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3 w-3" />
        {label}
      </div>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Reusable bits
// ---------------------------------------------------------------------------

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

function slugify(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
