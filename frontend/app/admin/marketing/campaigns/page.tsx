"use client";

import * as React from "react";
import Link from "next/link";
import {
  CheckCircle2,
  ExternalLink,
  Eye,
  EyeOff,
  Flame,
  Image as ImageIcon,
  Loader2,
  Pencil,
  Plus,
  Star,
  Tag,
  Trash2,
  X,
  Zap,
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
  OfferCampaign,
  OfferCampaignCreate,
  OfferCampaignUpdate,
} from "@/lib/admin/marketing-types";
import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";


const BASE = "/admin/marketing/campaigns";


// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function CampaignsPage() {
  const [rows, setRows] = React.useState<OfferCampaign[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  const [search, setSearch] = React.useState("");
  const [branch, setBranch] = React.useState("");
  const [includeInactive, setIncludeInactive] = React.useState(true);

  const [creating, setCreating] = React.useState(false);
  const [editing, setEditing] = React.useState<OfferCampaign | null>(null);

  React.useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  async function refresh() {
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("include_inactive", String(includeInactive));
      if (branch.trim()) params.set("branch", branch.trim());
      if (search.trim()) params.set("search", search.trim());
      const data = await adminApi.get<OfferCampaign[]>(
        `${BASE}?${params.toString()}`
      );
      setRows(data);
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function togglePublished(row: OfferCampaign) {
    try {
      await adminApi.patch(`${BASE}/${row.id}`, {
        is_active: !row.is_active,
      });
      setToast(
        row.is_active
          ? `Unpublished "${row.title}".`
          : `Published "${row.title}".`
      );
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function remove(row: OfferCampaign) {
    if (
      !confirm(
        `Delete campaign "${row.title}"? Its catalogues stay (campaign_id is set to NULL) so the content isn't lost.`
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

  // The 4 boolean flags surface in tiny chips so the operator can see at
  // a glance whether each campaign is active/featured/killer/flash.
  const branchOptions = React.useMemo(() => {
    if (rows === null) return [];
    return Array.from(
      new Set(rows.map((r) => r.branch).filter(Boolean) as string[])
    ).sort();
  }, [rows]);

  return (
    <AdminShell
      title="Offer campaigns"
      description="Marketing campaigns that group one or more catalogues for the public /offers page."
      actions={
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New campaign</span>
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
          <Label htmlFor="c-search">Search</Label>
          <Input
            id="c-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void refresh()}
            placeholder="Title, slug, description"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="c-branch">Branch</Label>
          <Select
            id="c-branch"
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
          >
            <option value="">All branches</option>
            {branchOptions.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </Select>
        </div>
        <label className="inline-flex items-center gap-2 pt-1 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
          />
          Include inactive
        </label>
        <Button size="sm" variant="outline" onClick={() => void refresh()}>
          Apply
        </Button>
      </div>

      {/* List */}
      {rows === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading campaigns…
        </p>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/60 p-10 text-center text-sm text-muted-foreground">
          <Tag className="mx-auto mb-3 h-8 w-8 opacity-50" />
          No campaigns match those filters.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campaign</TableHead>
                <TableHead className="hidden md:table-cell">Window</TableHead>
                <TableHead className="hidden md:table-cell">Branch</TableHead>
                <TableHead className="w-32">Flags</TableHead>
                <TableHead className="hidden lg:table-cell w-24 text-right">
                  Views
                </TableHead>
                <TableHead className="w-40 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <div className="flex items-start gap-3">
                      {row.banner_image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={resolveAssetUrl(row.banner_image_url) ?? ""}
                          alt=""
                          className="h-10 w-16 shrink-0 rounded object-cover"
                        />
                      ) : (
                        <div
                          className="flex h-10 w-16 shrink-0 items-center justify-center rounded text-muted-foreground"
                          style={{
                            background:
                              row.theme_color
                                ? `${row.theme_color}22`
                                : "rgba(0,0,0,0.06)",
                            color: row.theme_color || undefined,
                          }}
                        >
                          <ImageIcon className="h-4 w-4" />
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
                        <p className="text-[11px] text-muted-foreground">
                          {row.catalogue_count} catalogue
                          {row.catalogue_count === 1 ? "" : "s"}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-xs">
                    {row.start_date || row.end_date ? (
                      <span>
                        {row.start_date || "—"} → {row.end_date || "—"}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">Always</span>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-xs">
                    {row.branch || "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {row.is_featured && (
                        <FlagChip
                          icon={Star}
                          label="Featured"
                          color="text-pug-gold-700 bg-pug-gold-500/15 border-pug-gold-500/40"
                        />
                      )}
                      {row.is_killer_offer && (
                        <FlagChip
                          icon={Flame}
                          label="Killer"
                          color="text-rose-700 bg-rose-500/15 border-rose-500/40"
                        />
                      )}
                      {row.is_flash_sale && (
                        <FlagChip
                          icon={Zap}
                          label="Flash"
                          color="text-sky-700 bg-sky-500/15 border-sky-500/40"
                        />
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-right text-xs text-muted-foreground">
                    {row.view_count.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => togglePublished(row)}
                        aria-label={
                          row.is_active
                            ? `Unpublish ${row.title}`
                            : `Publish ${row.title}`
                        }
                        title={
                          row.is_active
                            ? "Unpublish (hide from /offers)"
                            : "Publish (show on /offers)"
                        }
                        className={cn(
                          row.is_active
                            ? "text-emerald-700 hover:text-emerald-800"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {row.is_active ? (
                          <Eye className="h-4 w-4" />
                        ) : (
                          <EyeOff className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        asChild
                        title="Open public page"
                      >
                        <Link
                          href={`/offers/${row.slug}`}
                          target="_blank"
                          aria-label={`View ${row.title} public page`}
                        >
                          <ExternalLink className="h-4 w-4" />
                        </Link>
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => setEditing(row)}
                        aria-label={`Edit ${row.title}`}
                        title="Edit"
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

      {(creating || editing) && (
        <CampaignDrawer
          editing={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={(title, mode) => {
            setCreating(false);
            setEditing(null);
            setToast(
              mode === "create"
                ? `Created "${title}".`
                : `Updated "${title}".`
            );
            void refresh();
          }}
          onError={setError}
        />
      )}
    </AdminShell>
  );
}


// ---------------------------------------------------------------------------
// Drawer (create / edit)
// ---------------------------------------------------------------------------

function CampaignDrawer({
  editing,
  onClose,
  onSaved,
  onError,
}: {
  editing: OfferCampaign | null;
  onClose: () => void;
  onSaved: (title: string, mode: "create" | "edit") => void;
  onError: (msg: string) => void;
}) {
  const [slug, setSlug] = React.useState(() => editing?.slug ?? "");
  const [title, setTitle] = React.useState(() => editing?.title ?? "");
  const [description, setDescription] = React.useState(
    () => editing?.description ?? ""
  );
  const [branch, setBranch] = React.useState(() => editing?.branch ?? "");
  const [themeColor, setThemeColor] = React.useState(
    () => editing?.theme_color ?? "#17382f"
  );
  const [bannerUrl, setBannerUrl] = React.useState(
    () => editing?.banner_image_url ?? ""
  );
  const [startDate, setStartDate] = React.useState(
    () => editing?.start_date ?? ""
  );
  const [endDate, setEndDate] = React.useState(() => editing?.end_date ?? "");
  const [isActive, setIsActive] = React.useState(
    () => editing?.is_active ?? true
  );
  const [isFeatured, setIsFeatured] = React.useState(
    () => editing?.is_featured ?? false
  );
  const [isKiller, setIsKiller] = React.useState(
    () => editing?.is_killer_offer ?? false
  );
  const [isFlash, setIsFlash] = React.useState(
    () => editing?.is_flash_sale ?? false
  );
  const [sortOrder, setSortOrder] = React.useState(
    () => editing?.sort_order ?? 0
  );
  const [metaTitle, setMetaTitle] = React.useState(
    () => editing?.meta_title ?? ""
  );
  const [metaDescription, setMetaDescription] = React.useState(
    () => editing?.meta_description ?? ""
  );

  const [saving, setSaving] = React.useState(false);
  const [uploadingBanner, setUploadingBanner] = React.useState(false);

  // Auto-fill slug from title in CREATE mode only (don't clobber a
  // saved slug on edit).
  React.useEffect(() => {
    if (editing) return;
    if (!title) return;
    if (slug.length > 0) return;
    setSlug(slugify(title));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title]);

  async function uploadBanner(file: File) {
    setUploadingBanner(true);
    try {
      const uploaded = await adminApi.uploadImage(file);
      setBannerUrl(uploaded.url);
    } catch (err) {
      onError((err as AdminApiError).message);
    } finally {
      setUploadingBanner(false);
    }
  }

  async function submit() {
    setSaving(true);
    try {
      const payload: OfferCampaignCreate = {
        slug: slug.trim().toLowerCase(),
        title: title.trim(),
        description: description.trim() || null,
        banner_image_url: bannerUrl.trim() || null,
        theme_color: themeColor.trim() || null,
        branch: branch.trim() || null,
        start_date: startDate || null,
        end_date: endDate || null,
        is_active: isActive,
        is_featured: isFeatured,
        is_killer_offer: isKiller,
        is_flash_sale: isFlash,
        sort_order: Number(sortOrder) || 0,
        meta_title: metaTitle.trim() || null,
        meta_description: metaDescription.trim() || null,
      };
      if (editing) {
        await adminApi.patch(`${BASE}/${editing.id}`, payload as OfferCampaignUpdate);
        onSaved(title.trim(), "edit");
      } else {
        await adminApi.post(BASE, payload);
        onSaved(title.trim(), "create");
      }
    } catch (err) {
      onError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  const canSubmit =
    slug.trim().length > 0 &&
    title.trim().length > 0 &&
    /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(slug.trim().toLowerCase()) &&
    !saving;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={editing ? "Edit campaign" : "Create campaign"}
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
        className="flex w-full max-w-2xl flex-col bg-background shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">
            {editing ? `Edit "${editing.title}"` : "New campaign"}
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

        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          <Section title="Identity">
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2 space-y-1.5">
                <Label htmlFor="c-title">Title *</Label>
                <Input
                  id="c-title"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  disabled={saving}
                  placeholder="Summer Mega Deals 2026"
                />
              </div>
              <div className="col-span-2 space-y-1.5">
                <Label htmlFor="c-slug">URL slug *</Label>
                <Input
                  id="c-slug"
                  required
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  disabled={saving}
                  className="font-mono text-sm"
                  placeholder="summer-mega-deals-2026"
                />
                <p className="text-[11px] text-muted-foreground">
                  Lowercase letters / digits / hyphens. Public URL becomes{" "}
                  <code>/offers/{slug || "<slug>"}</code>.
                </p>
              </div>
              <div className="col-span-2 space-y-1.5">
                <Label htmlFor="c-desc">Description</Label>
                <Textarea
                  id="c-desc"
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={saving}
                />
              </div>
            </div>
          </Section>

          <Section title="Visual chrome">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="c-color">Theme colour</Label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={themeColor || "#17382f"}
                    onChange={(e) => setThemeColor(e.target.value)}
                    disabled={saving}
                    className="h-10 w-12 cursor-pointer rounded border border-input bg-transparent"
                    aria-label="Theme color picker"
                  />
                  <Input
                    value={themeColor}
                    onChange={(e) => setThemeColor(e.target.value)}
                    disabled={saving}
                    placeholder="#17382f"
                    className="font-mono text-sm"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="c-sort">Sort order</Label>
                <Input
                  id="c-sort"
                  type="number"
                  value={sortOrder}
                  onChange={(e) => setSortOrder(Number(e.target.value))}
                  disabled={saving}
                />
                <p className="text-[11px] text-muted-foreground">
                  Lower numbers appear first.
                </p>
              </div>
              <div className="col-span-2 space-y-1.5">
                <Label htmlFor="c-banner">Banner image</Label>
                {bannerUrl ? (
                  <div className="flex items-center gap-3 rounded-md border border-border/60 p-2">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={resolveAssetUrl(bannerUrl) ?? bannerUrl}
                      alt="Banner"
                      className="h-16 w-32 rounded object-cover"
                    />
                    <div className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                      {bannerUrl}
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => setBannerUrl("")}
                      disabled={saving}
                    >
                      Remove
                    </Button>
                  </div>
                ) : (
                  <label
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-md border border-dashed border-input bg-background/40 px-3 py-3 text-sm",
                      uploadingBanner
                        ? "text-muted-foreground"
                        : "hover:border-primary/40"
                    )}
                  >
                    {uploadingBanner ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <ImageIcon className="h-4 w-4 text-primary" />
                    )}
                    <span>
                      {uploadingBanner
                        ? "Uploading…"
                        : "Click to upload a banner image"}
                    </span>
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void uploadBanner(f);
                      }}
                      disabled={saving || uploadingBanner}
                    />
                  </label>
                )}
              </div>
            </div>
          </Section>

          <Section title="Targeting + window">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="c-branch">Branch</Label>
                <Input
                  id="c-branch"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  disabled={saving}
                  placeholder="Doha / Lusail / All"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="c-start">Start date</Label>
                <Input
                  id="c-start"
                  type="date"
                  value={startDate || ""}
                  onChange={(e) => setStartDate(e.target.value)}
                  disabled={saving}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="c-end">End date</Label>
                <Input
                  id="c-end"
                  type="date"
                  value={endDate || ""}
                  onChange={(e) => setEndDate(e.target.value)}
                  disabled={saving}
                />
              </div>
            </div>
          </Section>

          <Section title="Flags">
            <div className="grid grid-cols-2 gap-2">
              <Toggle
                label="Active"
                description="Visible on the public /offers page."
                checked={isActive}
                onChange={setIsActive}
                disabled={saving}
              />
              <Toggle
                label="Featured"
                description="Appears in the featured grid on the homepage."
                checked={isFeatured}
                onChange={setIsFeatured}
                disabled={saving}
              />
              <Toggle
                label="Killer offer"
                description="Appears in the killer-offers carousel."
                checked={isKiller}
                onChange={setIsKiller}
                disabled={saving}
              />
              <Toggle
                label="Flash sale"
                description="Appears in the flash-sale strip."
                checked={isFlash}
                onChange={setIsFlash}
                disabled={saving}
              />
            </div>
          </Section>

          <Section title="SEO">
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="c-meta-title">Meta title</Label>
                <Input
                  id="c-meta-title"
                  value={metaTitle}
                  onChange={(e) => setMetaTitle(e.target.value)}
                  disabled={saving}
                  maxLength={200}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="c-meta-desc">Meta description</Label>
                <Textarea
                  id="c-meta-desc"
                  rows={2}
                  value={metaDescription}
                  onChange={(e) => setMetaDescription(e.target.value)}
                  disabled={saving}
                  maxLength={500}
                />
              </div>
            </div>
          </Section>
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
          <Button type="submit" disabled={!canSubmit}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {saving ? "Saving…" : editing ? "Save changes" : "Create campaign"}
          </Button>
        </footer>
      </form>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Reusable bits
// ---------------------------------------------------------------------------

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        {title}
      </p>
      {children}
    </section>
  );
}

function Toggle({
  label,
  description,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-start gap-2.5 rounded-md border border-border/60 p-3 text-sm transition-colors",
        checked
          ? "border-primary/40 bg-primary/[0.06]"
          : "hover:border-primary/30"
      )}
    >
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-ring"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
      />
      <span className="min-w-0 flex-1">
        <span className="block font-medium leading-tight">{label}</span>
        <span className="block text-[11px] text-muted-foreground">
          {description}
        </span>
      </span>
    </label>
  );
}

function FlagChip({
  icon: Icon,
  label,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  color: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
        color
      )}
    >
      <Icon className="h-2.5 w-2.5" />
      {label}
    </span>
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

function slugify(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
