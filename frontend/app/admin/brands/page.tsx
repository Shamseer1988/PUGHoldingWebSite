"use client";

import * as React from "react";
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  ExternalLink,
  Image as ImageIcon,
  Loader2,
  Plus,
  Save,
  Star,
  Trash2,
  Upload,
  X,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TrustedBrand {
  id: number;
  brand_name: string;
  logo_url: string;
  logo_url_alt: string | null;
  link_url: string | null;
  category: string | null;
  is_highlight: boolean;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface SectionSettings {
  home_brand_section_enabled: boolean;
  home_brand_eyebrow: string | null;
  home_brand_title: string | null;
  home_brand_subtitle: string | null;
  home_brand_animation_enabled: boolean;
  home_brand_layout_mode: "marquee" | "grid" | "carousel";
}

const LAYOUT_MODES: Array<{
  value: SectionSettings["home_brand_layout_mode"];
  label: string;
  description: string;
}> = [
  {
    value: "marquee",
    label: "Marquee (default)",
    description:
      "Two infinitely looping rows that pause on hover. Best when you curate 10+ brands.",
  },
  {
    value: "grid",
    label: "Grid wall",
    description:
      "Balanced responsive grid where every tile is visible at once. Best for 6–12 brands.",
  },
  {
    value: "carousel",
    label: "Carousel",
    description:
      "Horizontally scrollable row. Best for a handful of focused brands.",
  },
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AdminBrandsPage() {
  const [brands, setBrands] = React.useState<TrustedBrand[] | null>(null);
  const [settings, setSettings] = React.useState<SectionSettings | null>(null);
  const [bootError, setBootError] = React.useState<string | null>(null);
  const [creating, setCreating] = React.useState(false);

  const refresh = React.useCallback(async () => {
    try {
      const [b, s] = await Promise.all([
        adminApi.get<TrustedBrand[]>("/admin/cms/brands"),
        adminApi.get<SectionSettings>("/admin/cms/site-settings"),
      ]);
      setBrands(b);
      setSettings({
        home_brand_section_enabled: s.home_brand_section_enabled ?? true,
        home_brand_eyebrow: s.home_brand_eyebrow ?? null,
        home_brand_title: s.home_brand_title ?? null,
        home_brand_subtitle: s.home_brand_subtitle ?? null,
        home_brand_animation_enabled: s.home_brand_animation_enabled ?? true,
        home_brand_layout_mode:
          (s.home_brand_layout_mode as SectionSettings["home_brand_layout_mode"]) ??
          "marquee",
      });
      setBootError(null);
    } catch (err) {
      setBootError(err instanceof AdminApiError ? err.message : String(err));
    }
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <AdminShell
      title="Trusted Brands"
      description="Manage the 'Trusted Brands We Work With' showcase on the homepage. Logos here render in a premium dark luxury panel — no source-file edits needed."
    >
      <div className="space-y-6">
        {bootError && (
          <div
            role="alert"
            className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
          >
            <strong>Couldn&rsquo;t load brand data.</strong> {bootError}
          </div>
        )}

        {settings && <SectionSettingsCard settings={settings} onSaved={refresh} />}

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle className="text-base">Brand logos</CardTitle>
              <CardDescription>
                Add, reorder, or hide brands. Inactive brands are filtered out of
                the public showcase automatically.
              </CardDescription>
            </div>
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" />
              New brand
            </Button>
          </CardHeader>
          <CardContent>
            {brands === null ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading…
              </div>
            ) : brands.length === 0 ? (
              <EmptyState onCreate={() => setCreating(true)} />
            ) : (
              <BrandList brands={brands} onChanged={refresh} />
            )}
          </CardContent>
        </Card>

        {creating && (
          <BrandDialog
            onClose={() => setCreating(false)}
            onSaved={async () => {
              setCreating(false);
              await refresh();
            }}
          />
        )}
      </div>
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// Section settings
// ---------------------------------------------------------------------------

function SectionSettingsCard({
  settings,
  onSaved,
}: {
  settings: SectionSettings;
  onSaved: () => Promise<void>;
}) {
  const [form, setForm] = React.useState<SectionSettings>(settings);
  const [saving, setSaving] = React.useState(false);
  const [savedAt, setSavedAt] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => setForm(settings), [settings]);

  function set<K extends keyof SectionSettings>(
    key: K,
    value: SectionSettings[K]
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await adminApi.patch("/admin/cms/site-settings", form);
      await onSaved();
      setSavedAt(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err instanceof AdminApiError ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Section settings</CardTitle>
        <CardDescription>
          Eyebrow, title, subtitle, layout mode, and animation toggle for the
          public Trusted Brands section.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Toggle
          label="Enable section"
          value={form.home_brand_section_enabled}
          onChange={(v) => set("home_brand_section_enabled", v)}
          hint="Off → the entire section is hidden from the homepage."
        />
        <div className="grid gap-3 md:grid-cols-2">
          <Field
            label="Eyebrow"
            hint="Small uppercase label above the title."
          >
            <Input
              value={form.home_brand_eyebrow ?? ""}
              onChange={(e) => set("home_brand_eyebrow", e.target.value || null)}
              placeholder="TRUSTED BRANDS WE WORK WITH"
            />
          </Field>
          <Field label="Title">
            <Input
              value={form.home_brand_title ?? ""}
              onChange={(e) => set("home_brand_title", e.target.value || null)}
              placeholder="Trusted by strong brands"
            />
          </Field>
        </div>
        <Field label="Subtitle (optional)">
          <Textarea
            rows={2}
            value={form.home_brand_subtitle ?? ""}
            onChange={(e) => set("home_brand_subtitle", e.target.value || null)}
            placeholder="A portfolio of brands and businesses built on quality and trust."
          />
        </Field>
        <Field label="Layout mode" hint="Picks the public presentation.">
          <select
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            value={form.home_brand_layout_mode}
            onChange={(e) =>
              set(
                "home_brand_layout_mode",
                e.target.value as SectionSettings["home_brand_layout_mode"]
              )
            }
          >
            {LAYOUT_MODES.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {LAYOUT_MODES.find((m) => m.value === form.home_brand_layout_mode)
              ?.description}
          </p>
        </Field>
        <Toggle
          label="Animation enabled"
          value={form.home_brand_animation_enabled}
          onChange={(v) => set("home_brand_animation_enabled", v)}
          hint="Off → static reveal, respects users on reduced-motion settings either way."
        />
        {error && (
          <p
            role="alert"
            className="rounded-md border border-rose-500/40 bg-rose-500/10 p-2 text-xs text-rose-700 dark:text-rose-200"
          >
            {error}
          </p>
        )}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {savedAt && <>Saved {savedAt}.</>}
          </span>
          <Button size="sm" onClick={save} disabled={saving}>
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save settings
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Brand list
// ---------------------------------------------------------------------------

function BrandList({
  brands,
  onChanged,
}: {
  brands: TrustedBrand[];
  onChanged: () => Promise<void>;
}) {
  return (
    <div className="space-y-2">
      {brands.map((brand, idx) => (
        <BrandRow
          key={brand.id}
          brand={brand}
          neighbours={brands}
          index={idx}
          onChanged={onChanged}
        />
      ))}
    </div>
  );
}

function BrandRow({
  brand,
  neighbours,
  index,
  onChanged,
}: {
  brand: TrustedBrand;
  neighbours: TrustedBrand[];
  index: number;
  onChanged: () => Promise<void>;
}) {
  const [editing, setEditing] = React.useState(false);
  const [working, setWorking] = React.useState(false);

  async function toggleActive() {
    setWorking(true);
    try {
      await adminApi.patch(`/admin/cms/brands/${brand.id}`, {
        is_active: !brand.is_active,
      });
      await onChanged();
    } catch (err) {
      alert(err instanceof AdminApiError ? err.message : String(err));
    } finally {
      setWorking(false);
    }
  }

  async function move(direction: -1 | 1) {
    const target = neighbours[index + direction];
    if (!target) return;
    setWorking(true);
    try {
      await Promise.all([
        adminApi.patch(`/admin/cms/brands/${brand.id}`, {
          display_order: target.display_order,
        }),
        adminApi.patch(`/admin/cms/brands/${target.id}`, {
          display_order: brand.display_order,
        }),
      ]);
      await onChanged();
    } catch (err) {
      alert(err instanceof AdminApiError ? err.message : String(err));
    } finally {
      setWorking(false);
    }
  }

  async function remove() {
    if (!confirm(`Delete brand "${brand.brand_name}"?`)) return;
    setWorking(true);
    try {
      await adminApi.delete(`/admin/cms/brands/${brand.id}`);
      await onChanged();
    } catch (err) {
      alert(err instanceof AdminApiError ? err.message : String(err));
    } finally {
      setWorking(false);
    }
  }

  return (
    <>
      <div
        className={cn(
          "flex items-center gap-3 rounded-lg border border-border/60 bg-muted/20 p-2 sm:p-3",
          !brand.is_active && "opacity-60"
        )}
      >
        <div className="flex h-12 w-16 shrink-0 items-center justify-center overflow-hidden rounded-md border border-border/60 bg-[#0d1a14]">
          {brand.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={brand.logo_url}
              alt={brand.brand_name}
              className="max-h-9 w-auto max-w-[80%] object-contain"
            />
          ) : (
            <ImageIcon className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-medium">{brand.brand_name}</p>
            {brand.is_highlight && (
              <span className="inline-flex items-center gap-0.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-300">
                <Star className="h-2.5 w-2.5" />
                Featured
              </span>
            )}
            {!brand.is_active && (
              <span className="rounded-full border border-border/60 bg-muted/50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Hidden
              </span>
            )}
          </div>
          <p className="truncate text-xs text-muted-foreground">
            order #{brand.display_order}
            {brand.category && <> · {brand.category}</>}
            {brand.link_url && (
              <>
                {" · "}
                <span className="inline-flex items-center gap-0.5">
                  link <ExternalLink className="h-3 w-3" />
                </span>
              </>
            )}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <Button
            variant="ghost"
            size="sm"
            disabled={working || index === 0}
            onClick={() => move(-1)}
            aria-label="Move up"
          >
            <ArrowUp className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={working || index === neighbours.length - 1}
            onClick={() => move(1)}
            aria-label="Move down"
          >
            <ArrowDown className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={working}
            onClick={toggleActive}
          >
            {brand.is_active ? "Hide" : "Show"}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
            Edit
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={working}
            onClick={remove}
            className="text-rose-600 hover:text-rose-700"
            aria-label="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {editing && (
        <BrandDialog
          existing={brand}
          onClose={() => setEditing(false)}
          onSaved={async () => {
            setEditing(false);
            await onChanged();
          }}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Create / edit dialog
// ---------------------------------------------------------------------------

function BrandDialog({
  existing,
  onClose,
  onSaved,
}: {
  existing?: TrustedBrand;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [form, setForm] = React.useState({
    brand_name: existing?.brand_name ?? "",
    logo_url: existing?.logo_url ?? "",
    logo_url_alt: existing?.logo_url_alt ?? "",
    link_url: existing?.link_url ?? "",
    category: existing?.category ?? "",
    is_highlight: existing?.is_highlight ?? false,
    display_order:
      existing?.display_order ??
      Math.floor(Date.now() / 1000) % 1000, // unique-ish initial
    is_active: existing?.is_active ?? true,
  });
  const [saving, setSaving] = React.useState(false);
  const [uploading, setUploading] = React.useState<"main" | "alt" | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function uploadLogo(slot: "main" | "alt", file: File) {
    setUploading(slot);
    setError(null);
    try {
      const result = await adminApi.uploadImage(file);
      if (slot === "main") set("logo_url", result.url);
      else set("logo_url_alt", result.url);
    } catch (err) {
      setError(err instanceof AdminApiError ? err.message : String(err));
    } finally {
      setUploading(null);
    }
  }

  async function save() {
    if (!form.brand_name.trim() || !form.logo_url.trim()) {
      setError("Brand name and a logo image are both required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        brand_name: form.brand_name.trim(),
        logo_url: form.logo_url.trim(),
        logo_url_alt: form.logo_url_alt.trim() || null,
        link_url: form.link_url.trim() || null,
        category: form.category.trim() || null,
        is_highlight: form.is_highlight,
        display_order: Number(form.display_order) || 0,
        is_active: form.is_active,
      };
      if (existing) {
        await adminApi.patch(`/admin/cms/brands/${existing.id}`, payload);
      } else {
        await adminApi.post("/admin/cms/brands", payload);
      }
      await onSaved();
    } catch (err) {
      setError(err instanceof AdminApiError ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur"
    >
      <div className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-border/60 bg-background shadow-2xl">
        <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <h3 className="text-sm font-semibold">
            {existing ? `Edit "${existing.brand_name}"` : "New brand"}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[70vh] space-y-4 overflow-y-auto px-4 py-4">
          <Field label="Brand name">
            <Input
              value={form.brand_name}
              onChange={(e) => set("brand_name", e.target.value)}
              placeholder="Paris Hyper Market"
            />
          </Field>

          <LogoUpload
            label="Primary logo"
            url={form.logo_url}
            uploading={uploading === "main"}
            onUpload={(file) => uploadLogo("main", file)}
            onClear={() => set("logo_url", "")}
            onUrlChange={(v) => set("logo_url", v)}
            hint="Used on the dark luxury panel — light or transparent logos work best."
          />

          <LogoUpload
            label="Alt logo (optional)"
            url={form.logo_url_alt}
            uploading={uploading === "alt"}
            onUpload={(file) => uploadLogo("alt", file)}
            onClear={() => set("logo_url_alt", "")}
            onUrlChange={(v) => set("logo_url_alt", v)}
            hint="Optional alternate logo variant. Falls back to the primary when empty."
          />

          <div className="grid gap-3 md:grid-cols-2">
            <Field
              label="Click-through URL (optional)"
              hint="External URLs open in a new tab."
            >
              <Input
                value={form.link_url}
                onChange={(e) => set("link_url", e.target.value)}
                placeholder="https://example.com"
              />
            </Field>
            <Field label="Category (optional)">
              <Input
                value={form.category}
                onChange={(e) => set("category", e.target.value)}
                placeholder="retail / distribution / services"
              />
            </Field>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <Field
              label="Display order"
              hint="Lower numbers come first. Use the arrows in the list view to swap quickly."
            >
              <Input
                type="number"
                value={form.display_order}
                onChange={(e) =>
                  set("display_order", Number(e.target.value) || 0)
                }
              />
            </Field>
            <div className="space-y-2">
              <Toggle
                label="Active"
                value={form.is_active}
                onChange={(v) => set("is_active", v)}
                hint="Off → hidden from the public showcase."
              />
              <Toggle
                label="Featured"
                value={form.is_highlight}
                onChange={(v) => set("is_highlight", v)}
                hint="Adds a gold ring and 'Featured' badge in the public showcase."
              />
            </div>
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-md border border-rose-500/40 bg-rose-500/10 p-2 text-xs text-rose-700 dark:text-rose-200"
            >
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={save} disabled={saving || !!uploading}>
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {existing ? "Save changes" : "Create brand"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared bits
// ---------------------------------------------------------------------------

function LogoUpload({
  label,
  url,
  uploading,
  onUpload,
  onClear,
  onUrlChange,
  hint,
}: {
  label: string;
  url: string;
  uploading: boolean;
  onUpload: (file: File) => Promise<void> | void;
  onClear: () => void;
  onUrlChange: (value: string) => void;
  hint?: string;
}) {
  const fileRef = React.useRef<HTMLInputElement | null>(null);
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{label}</Label>
      <div className="flex items-center gap-3">
        <div className="flex h-16 w-24 shrink-0 items-center justify-center overflow-hidden rounded-md border border-border/60 bg-[#0d1a14]">
          {url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={url}
              alt=""
              className="max-h-12 w-auto max-w-[85%] object-contain"
            />
          ) : (
            <ImageIcon className="h-5 w-5 text-muted-foreground" />
          )}
        </div>
        <div className="flex flex-1 flex-col gap-2 sm:flex-row">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Upload className="h-3.5 w-3.5" />
            )}
            Upload
          </Button>
          <Input
            value={url}
            onChange={(e) => onUrlChange(e.target.value)}
            placeholder="https://… or /images/…"
            className="flex-1"
          />
          {url && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={onClear}
              className="text-rose-600 hover:text-rose-700"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            void onUpload(file);
            e.target.value = "";
          }
        }}
      />
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border/60 bg-muted/20 p-8 text-center">
      <CheckCircle2 className="h-6 w-6 opacity-60" />
      <p className="text-sm font-medium">No brands yet</p>
      <p className="text-xs text-muted-foreground">
        Add brand logos to power the homepage Trusted Brands showcase.
      </p>
      <Button size="sm" onClick={onCreate}>
        <Plus className="h-4 w-4" />
        Add the first brand
      </Button>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{label}</Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function Toggle({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: boolean;
  onChange: (next: boolean) => void;
  hint?: string;
}) {
  return (
    <label className="flex items-start gap-2 rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-sm">
      <input
        type="checkbox"
        checked={value}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-4 w-4 rounded border-input"
      />
      <span className="flex-1">
        <span className="font-medium">{label}</span>
        {hint && (
          <span className="block text-[11px] text-muted-foreground">{hint}</span>
        )}
      </span>
    </label>
  );
}
