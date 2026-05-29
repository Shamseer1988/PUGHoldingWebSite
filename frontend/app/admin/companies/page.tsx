"use client";

import * as React from "react";
import {
  Building2,
  CheckCircle2,
  Edit3,
  Film,
  Loader2,
  Plus,
  Trash2,
  X,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { ImageUpload } from "@/components/admin/image-upload";
import { VideoUpload } from "@/components/admin/video-upload";
import { CompanyLogo } from "@/components/site/company-logo";
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
import type { Company, CompanyCategory } from "@/lib/admin/types";

interface CompanyFormState {
  slug: string;
  name: string;
  category: CompanyCategory;
  short_description: string;
  long_description: string;
  homepage_highlight_description: string;
  homepage_highlight_points: string;
  homepage_group_highlight: string;
  homepage_group_stat_line: string;
  homepage_group_video_url: string | null;
  homepage_group_video_poster_url: string | null;
  branches: string;
  accent: string;
  initials: string;
  brand_logo_url: string | null;
  phone: string;
  email: string;
  address: string;
  website: string;
  featured_image_url: string | null;
  cta_label: string;
  cta_url: string;
  is_highlighted: boolean;
  display_order: number;
  is_active: boolean;
  services: string;
  brand_logos: BrandLogoDraft[];
}

interface BrandLogoDraft {
  image_url: string;
  name: string;
  link_url: string;
}

const EMPTY_FORM: CompanyFormState = {
  slug: "",
  name: "",
  category: "retail",
  short_description: "",
  long_description: "",
  homepage_highlight_description: "",
  homepage_highlight_points: "",
  homepage_group_highlight: "",
  homepage_group_stat_line: "",
  homepage_group_video_url: null,
  homepage_group_video_poster_url: null,
  branches: "",
  accent: "from-pug-green-500 to-pug-gold-500",
  initials: "",
  brand_logo_url: null,
  phone: "",
  email: "",
  address: "",
  website: "",
  featured_image_url: null,
  cta_label: "",
  cta_url: "",
  is_highlighted: false,
  display_order: 0,
  is_active: true,
  services: "",
  brand_logos: [],
};

export default function CompaniesAdminPage() {
  const [items, setItems] = React.useState<Company[] | null>(null);
  const [editing, setEditing] = React.useState<Company | null>(null);
  const [form, setForm] = React.useState<CompanyFormState>(EMPTY_FORM);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  React.useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setItems(null);
    try {
      const data = await adminApi.get<Company[]>("/admin/cms/companies");
      setItems(data);
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

  function openEdit(item: Company) {
    setEditing(item);
    setForm({
      slug: item.slug,
      name: item.name,
      category: item.category,
      short_description: item.short_description ?? "",
      long_description: item.long_description ?? "",
      homepage_highlight_description: item.homepage_highlight_description ?? "",
      homepage_highlight_points: item.homepage_highlight_points ?? "",
      homepage_group_highlight: item.homepage_group_highlight ?? "",
      homepage_group_stat_line: item.homepage_group_stat_line ?? "",
      homepage_group_video_url: item.homepage_group_video_url ?? null,
      homepage_group_video_poster_url:
        item.homepage_group_video_poster_url ?? null,
      branches: item.branches ?? "",
      accent: item.accent,
      initials: item.initials,
      brand_logo_url: item.brand_logo_url ?? null,
      phone: item.phone ?? "",
      email: item.email ?? "",
      address: item.address ?? "",
      website: item.website ?? "",
      featured_image_url: item.featured_image_url ?? null,
      cta_label: item.cta_label ?? "",
      cta_url: item.cta_url ?? "",
      is_highlighted: item.is_highlighted,
      display_order: item.display_order,
      is_active: item.is_active,
      services: item.services.map((s) => s.name).join(", "),
      brand_logos: (item.brand_logos ?? []).map((logo) => ({
        image_url: logo.image_url,
        name: logo.name ?? "",
        link_url: logo.link_url ?? "",
      })),
    });
    setError(null);
    setDrawerOpen(true);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const body = {
        slug: form.slug.trim(),
        name: form.name.trim(),
        category: form.category,
        short_description: form.short_description.trim() || null,
        long_description: form.long_description.trim() || null,
        homepage_highlight_description:
          form.homepage_highlight_description.trim() || null,
        // Preserve user-entered line breaks for the points field —
        // trim leading/trailing whitespace only.
        homepage_highlight_points:
          form.homepage_highlight_points.replace(/^\s+|\s+$/g, "") || null,
        homepage_group_highlight: form.homepage_group_highlight.trim() || null,
        homepage_group_stat_line:
          form.homepage_group_stat_line.trim() || null,
        homepage_group_video_url: form.homepage_group_video_url || null,
        homepage_group_video_poster_url:
          form.homepage_group_video_poster_url || null,
        branches: form.branches.trim() || null,
        accent: form.accent.trim(),
        initials: form.initials.trim(),
        brand_logo_url: form.brand_logo_url || null,
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
        address: form.address.trim() || null,
        website: form.website.trim() || null,
        featured_image_url: form.featured_image_url || null,
        cta_label: form.cta_label.trim() || null,
        cta_url: form.cta_url.trim() || null,
        is_highlighted: form.is_highlighted,
        display_order: Number(form.display_order) || 0,
        is_active: form.is_active,
        services: form.services
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        brand_logos: form.brand_logos
          // Drop any rows the admin added then left empty.
          .filter((logo) => logo.image_url.trim())
          .map((logo, i) => ({
            image_url: logo.image_url.trim(),
            name: logo.name.trim() || null,
            link_url: logo.link_url.trim() || null,
            display_order: i,
          })),
      };
      if (editing) {
        await adminApi.patch<Company>(
          `/admin/cms/companies/${editing.id}`,
          body
        );
        setToast(`Updated “${body.name}”.`);
      } else {
        await adminApi.post<Company>("/admin/cms/companies", body);
        setToast(`Created “${body.name}”.`);
      }
      setDrawerOpen(false);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(item: Company) {
    if (!confirm(`Delete “${item.name}”? This cannot be undone.`)) return;
    try {
      await adminApi.delete(`/admin/cms/companies/${item.id}`);
      setToast(`Deleted “${item.name}”.`);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  return (
    <AdminShell
      title="Group companies"
      description="Manage the company portfolio shown on the public site."
      actions={
        <Button onClick={openNew} size="sm" aria-label="Add a new company">
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New company</span>
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

      {items === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading companies…
        </p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No companies yet"
          description="Add the first group company to populate the public website's portfolio page."
          action={<Button onClick={openNew} size="sm"><Plus className="h-4 w-4" />New company</Button>}
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead>Category</TableHead>
                <TableHead className="hidden md:table-cell">Services</TableHead>
                <TableHead className="hidden lg:table-cell w-32">Order</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead className="w-32 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <CompanyLogo
                        logoUrl={item.brand_logo_url}
                        initials={item.initials}
                        accent={item.accent}
                        name={item.name}
                        size="xs"
                      />
                      <div className="min-w-0">
                        <p className="flex items-center gap-1.5 truncate font-medium">
                          <span className="truncate">{item.name}</span>
                          {item.homepage_group_video_url && (
                            <span
                              title="Has a Group Companies homepage video"
                              aria-label="Has a Group Companies homepage video"
                              className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-pug-gold-500/15 text-pug-gold-700 dark:text-pug-gold-300"
                            >
                              <Film className="h-2.5 w-2.5" />
                            </span>
                          )}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">
                          /{item.slug}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="capitalize">{item.category}</TableCell>
                  <TableCell className="hidden md:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {item.services.slice(0, 3).map((s) => (
                        <Badge key={s.id} variant="muted" className="font-normal">
                          {s.name}
                        </Badge>
                      ))}
                      {item.services.length > 3 && (
                        <span className="text-xs text-muted-foreground">
                          +{item.services.length - 3}
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    {item.display_order}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {item.is_active ? (
                        <Badge variant="success">Active</Badge>
                      ) : (
                        <Badge variant="muted">Hidden</Badge>
                      )}
                      {item.is_highlighted && (
                        <Badge variant="warning">Featured</Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => openEdit(item)}
                      aria-label={`Edit ${item.name}`}
                    >
                      <Edit3 className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => remove(item)}
                      aria-label={`Delete ${item.name}`}
                      className="text-rose-600 hover:text-rose-700"
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

      <CompanyDrawer
        open={drawerOpen}
        title={editing ? "Edit company" : "New company"}
        form={form}
        onChange={setForm}
        onClose={() => setDrawerOpen(false)}
        onSave={save}
        saving={saving}
      />
    </AdminShell>
  );
}

function CompanyDrawer({
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
  form: CompanyFormState;
  onChange: (next: CompanyFormState) => void;
  onClose: () => void;
  onSave: () => void;
  saving: boolean;
}) {
  function set<K extends keyof CompanyFormState>(
    key: K,
    value: CompanyFormState[K]
  ) {
    onChange({ ...form, [key]: value });
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-40 flex"
    >
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div className="flex w-full max-w-xl flex-col bg-background shadow-2xl">
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">{title}</h2>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </header>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSave();
          }}
          className="flex flex-1 flex-col overflow-y-auto"
        >
          <div className="flex-1 space-y-4 p-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Name" required>
                <Input
                  required
                  value={form.name}
                  onChange={(e) => set("name", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Slug" required hint="lowercase, dashes only">
                <Input
                  required
                  pattern="^[a-z0-9-]+$"
                  value={form.slug}
                  onChange={(e) => set("slug", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Category" required>
                <Select
                  value={form.category}
                  onChange={(e) =>
                    set("category", e.target.value as CompanyCategory)
                  }
                  disabled={saving}
                >
                  <option value="distribution">Distribution</option>
                  <option value="retail">Retail</option>
                  <option value="services">Services</option>
                </Select>
              </Field>
              <Field label="Initials" required hint="Fallback when no logo">
                <Input
                  required
                  maxLength={8}
                  value={form.initials}
                  onChange={(e) => set("initials", e.target.value.toUpperCase())}
                  disabled={saving}
                />
              </Field>
            </div>

            <div className="rounded-xl border border-border/60 bg-muted/30 p-4">
              <ImageUpload
                label="Brand logo"
                value={form.brand_logo_url}
                onChange={(url) => set("brand_logo_url", url)}
                folder="companies/logos"
                disabled={saving}
              />
              <p className="mt-2 text-xs text-muted-foreground">
                Optional. When set, this logo replaces the {form.initials || "initials"} tile on the public site, the homepage Group Companies card, and the company detail page. Leave empty to keep the gradient initials tile.
              </p>
            </div>

            <Field label="Short description" hint="Shown on cards">
              <Input
                value={form.short_description}
                onChange={(e) => set("short_description", e.target.value)}
                disabled={saving}
              />
            </Field>

            <Field label="Long description">
              <Textarea
                rows={5}
                value={form.long_description}
                onChange={(e) => set("long_description", e.target.value)}
                disabled={saving}
              />
            </Field>

            <Field
              label="Homepage Highlight Description"
              hint="Short premium description used only in the homepage Group Companies section. If empty, the system will use the long description or short description as fallback."
            >
              <Textarea
                rows={3}
                value={form.homepage_highlight_description}
                onChange={(e) =>
                  set("homepage_highlight_description", e.target.value)
                }
                disabled={saving}
              />
            </Field>

            <Field
              label="Homepage Highlight Points"
              hint="One per line — e.g. FMCG wholesale and distribution. Rendered as chips below the homepage description; if empty the section falls back to the company's services."
            >
              <Textarea
                rows={4}
                value={form.homepage_highlight_points}
                onChange={(e) =>
                  set("homepage_highlight_points", e.target.value)
                }
                disabled={saving}
                placeholder={
                  "FMCG wholesale and distribution\nDepartment store retail supply\nHORECA and institutional support"
                }
              />
            </Field>

            <Field label="Services" hint="comma-separated">
              <Input
                value={form.services}
                onChange={(e) => set("services", e.target.value)}
                disabled={saving}
                placeholder="Grocery, Fresh food, Household"
              />
            </Field>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Branches" hint="Optional">
                <Input
                  value={form.branches}
                  onChange={(e) => set("branches", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field
                label="Accent gradient"
                hint="Tailwind from-… via-… to-… classes"
              >
                <Input
                  value={form.accent}
                  onChange={(e) => set("accent", e.target.value)}
                  disabled={saving}
                />
              </Field>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Phone">
                <Input
                  value={form.phone}
                  onChange={(e) => set("phone", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Email">
                <Input
                  type="email"
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Address">
                <Input
                  value={form.address}
                  onChange={(e) => set("address", e.target.value)}
                  disabled={saving}
                />
              </Field>
              <Field label="Website">
                <Input
                  value={form.website}
                  onChange={(e) => set("website", e.target.value)}
                  disabled={saving}
                />
              </Field>
            </div>

            {/* Homepage "Featured Companies" section settings */}
            <div className="space-y-3 rounded-xl border border-border/60 bg-muted/30 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Homepage showcase
              </p>

              <ImageUpload
                label="Featured image"
                value={form.featured_image_url}
                onChange={(url) => set("featured_image_url", url)}
                folder="companies"
                disabled={saving}
              />

              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="CTA label" hint="Optional · shown on the card">
                  <Input
                    value={form.cta_label}
                    onChange={(e) => set("cta_label", e.target.value)}
                    disabled={saving}
                    placeholder="Visit the brand"
                  />
                </Field>
                <Field label="CTA URL" hint="Internal or external link">
                  <Input
                    value={form.cta_url}
                    onChange={(e) => set("cta_url", e.target.value)}
                    disabled={saving}
                    placeholder="https://… or /companies/slug"
                  />
                </Field>
              </div>

              <Field label="Highlight on homepage" hint="Featured Companies section">
                <label className="inline-flex items-center gap-2 pt-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                    checked={form.is_highlighted}
                    onChange={(e) => set("is_highlighted", e.target.checked)}
                    disabled={saving}
                  />
                  Include in the scroll showcase
                </label>
              </Field>

              {/* Phase 18 follow-up — richer Group Companies card + video */}
              <div className="space-y-3 border-t border-border/40 pt-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    Group Companies card (homepage)
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Drives the left-side showcase card and the right-side
                    media frame in the public &quot;A diversified
                    portfolio&quot; section. Empty fields fall back to the
                    existing image + long/short description so removing a
                    value never breaks the section.
                  </p>
                </div>

                <Field
                  label="Group Companies highlight paragraph"
                  hint="Short polished text (160–240 chars) shown inside the left card. Falls back to long → short description when empty."
                >
                  <Textarea
                    rows={3}
                    value={form.homepage_group_highlight}
                    onChange={(e) =>
                      set("homepage_group_highlight", e.target.value)
                    }
                    disabled={saving}
                    placeholder="Paris Food International is the group's flagship FMCG distribution arm, serving wholesale, retail, department store, and HORECA channels across the region."
                  />
                </Field>

                <Field
                  label="Stat line (below card)"
                  hint="Single line of supporting stats, e.g. '500+ Brand Partners · 15,000+ SKUs'. Leave blank to hide."
                >
                  <Input
                    value={form.homepage_group_stat_line}
                    onChange={(e) =>
                      set("homepage_group_stat_line", e.target.value)
                    }
                    disabled={saving}
                    placeholder="500+ Brand Partners · 15,000+ SKUs"
                  />
                </Field>

                <VideoUpload
                  label="Group Companies Video (Optional)"
                  helperText="Upload a short 5–8 second looping video for the homepage Group Companies section. If uploaded, it will replace the image only inside the Group Companies media card on desktop. The image will still be used as preview, poster, and fallback."
                  value={form.homepage_group_video_url}
                  onChange={(url) => set("homepage_group_video_url", url)}
                  disabled={saving}
                />

                {form.homepage_group_video_url && (
                  <ImageUpload
                    label="Video poster (optional)"
                    value={form.homepage_group_video_poster_url}
                    onChange={(url) =>
                      set("homepage_group_video_poster_url", url)
                    }
                    folder="companies"
                    disabled={saving}
                  />
                )}

                <BrandLogoRepeater
                  logos={form.brand_logos}
                  onChange={(next) => set("brand_logos", next)}
                  disabled={saving}
                />
              </div>
            </div>

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
              <Field label="Active">
                <label className="inline-flex items-center gap-2 pt-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                    checked={form.is_active}
                    onChange={(e) => set("is_active", e.target.checked)}
                    disabled={saving}
                  />
                  Show on public site
                </label>
              </Field>
            </div>
          </div>

          <footer className="flex items-center justify-end gap-2 border-t border-border/60 bg-background px-5 py-3">
            <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
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

/**
 * Brand-logo repeater.
 *
 * Each row is one logo: image picker (reuses the same uploader as
 * featured_image_url), optional alt-text, optional click-through URL.
 * Order is implicit from array position — the "↑ / ↓" buttons swap
 * adjacent rows. The trash button removes a single row; the parent
 * page strips any row that ends up without an image_url at save time.
 */
function BrandLogoRepeater({
  logos,
  onChange,
  disabled,
}: {
  logos: BrandLogoDraft[];
  onChange: (next: BrandLogoDraft[]) => void;
  disabled?: boolean;
}) {
  function update(idx: number, patch: Partial<BrandLogoDraft>) {
    onChange(logos.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  }
  function add() {
    onChange([
      ...logos,
      { image_url: "", name: "", link_url: "" },
    ]);
  }
  function remove(idx: number) {
    onChange(logos.filter((_, i) => i !== idx));
  }
  function move(idx: number, delta: -1 | 1) {
    const target = idx + delta;
    if (target < 0 || target >= logos.length) return;
    const next = [...logos];
    [next[idx], next[target]] = [next[target], next[idx]];
    onChange(next);
  }

  return (
    <div className="space-y-3 rounded-xl border border-border/40 bg-background/40 p-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Group Companies brand logos
        </p>
        <p className="text-[11px] text-muted-foreground">
          Logos displayed inside the auto-scrolling marquee on the homepage
          Group Companies card. When this list is empty the marquee falls
          back to text chips using the company&rsquo;s services.
        </p>
      </div>

      {logos.length === 0 ? (
        <p className="rounded-md border border-dashed border-border/60 bg-background/50 p-4 text-center text-xs text-muted-foreground">
          No brand logos yet. Add one to swap the homepage marquee from
          text chips to real images.
        </p>
      ) : (
        <ul className="space-y-3">
          {logos.map((logo, idx) => (
            <li
              key={idx}
              className="space-y-3 rounded-lg border border-border/60 bg-card p-3"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="inline-flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  Logo #{idx + 1}
                </span>
                <div className="inline-flex items-center gap-1">
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    onClick={() => move(idx, -1)}
                    disabled={disabled || idx === 0}
                    aria-label="Move logo up"
                    title="Move up"
                  >
                    <span aria-hidden>↑</span>
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    onClick={() => move(idx, 1)}
                    disabled={disabled || idx === logos.length - 1}
                    aria-label="Move logo down"
                    title="Move down"
                  >
                    <span aria-hidden>↓</span>
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    onClick={() => remove(idx)}
                    disabled={disabled}
                    aria-label="Remove logo"
                    className="text-rose-600 hover:text-rose-700"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <ImageUpload
                label="Logo image"
                value={logo.image_url || null}
                onChange={(url) => update(idx, { image_url: url ?? "" })}
                folder="companies/logos"
                disabled={disabled}
              />

              <div className="grid gap-3 sm:grid-cols-2">
                <Field
                  label="Alt text"
                  hint="Brand or partner name — shown to screen readers and as a fallback when the image fails to load."
                >
                  <Input
                    value={logo.name}
                    onChange={(e) => update(idx, { name: e.target.value })}
                    disabled={disabled}
                    placeholder="e.g. Paris Hyper Market"
                  />
                </Field>
                <Field
                  label="Click-through URL (optional)"
                  hint="Where the logo links when clicked. Leave blank for a non-clickable logo."
                >
                  <Input
                    value={logo.link_url}
                    onChange={(e) => update(idx, { link_url: e.target.value })}
                    disabled={disabled}
                    placeholder="https://example.com"
                  />
                </Field>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={add}
        disabled={disabled}
        aria-label="Add brand logo"
      >
        <Plus className="h-4 w-4" />
        Add a logo
      </Button>
    </div>
  );
}


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
