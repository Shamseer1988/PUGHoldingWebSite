"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertCircle,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  ExternalLink,
  FileWarning,
  Info,
  Loader2,
  Plus,
  Save,
  ShieldCheck,
  Trash2,
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
import type {
  SeoDashboard,
  SeoSettings,
  SeoVerification,
  ScriptPlacement,
  TrackingIntegration,
  TrackingProvider,
  VerificationProvider,
  VerificationType,
} from "@/lib/admin/seo-types";
import { cn } from "@/lib/utils";

const TABS = [
  { key: "dashboard", label: "Dashboard" },
  { key: "general", label: "General SEO" },
  { key: "verifications", label: "Domain Verification" },
  { key: "gtm", label: "Google Tag Manager" },
  { key: "analytics", label: "Analytics & Tracking" },
  { key: "sitemap", label: "Sitemap" },
  { key: "robots", label: "Robots.txt" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

// ---------------------------------------------------------------------------
// Top-level page
// ---------------------------------------------------------------------------

export default function SeoConfigurationPage() {
  // useSearchParams must sit inside a Suspense boundary so Next can
  // statically generate the surrounding shell. The inner component
  // does the real work.
  return (
    <React.Suspense fallback={null}>
      <SeoConfigurationBody />
    </React.Suspense>
  );
}

function SeoConfigurationBody() {
  const params = useSearchParams();
  const initial = (params.get("tab") as TabKey) ?? "dashboard";
  const [tab, setTab] = React.useState<TabKey>(
    TABS.some((t) => t.key === initial) ? initial : "dashboard"
  );

  // Shared state lives at the top so a save in one tab can refresh
  // others (e.g. saving a GTM ID should refresh the Dashboard pills).
  const [settings, setSettings] = React.useState<SeoSettings | null>(null);
  const [verifications, setVerifications] = React.useState<SeoVerification[] | null>(
    null
  );
  const [integrations, setIntegrations] = React.useState<TrackingIntegration[] | null>(
    null
  );
  const [dashboard, setDashboard] = React.useState<SeoDashboard | null>(null);
  const [bootError, setBootError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    try {
      const [s, v, i, d] = await Promise.all([
        adminApi.get<SeoSettings>("/admin/seo/settings"),
        adminApi.get<SeoVerification[]>("/admin/seo/verifications"),
        adminApi.get<TrackingIntegration[]>("/admin/seo/integrations"),
        adminApi.get<SeoDashboard>("/admin/seo/dashboard"),
      ]);
      setSettings(s);
      setVerifications(v);
      setIntegrations(i);
      setDashboard(d);
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
      title="SEO Configuration"
      description="Control verification tags, tracking integrations, sitemap and robots.txt — all from the admin panel. No source-file edits required."
    >
      <div className="space-y-6">
        {/* Tabs */}
        <div className="flex flex-wrap gap-1 rounded-xl border border-border/60 bg-background/70 p-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                tab === t.key
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
              aria-pressed={tab === t.key}
            >
              {t.label}
            </button>
          ))}
        </div>

        {bootError && (
          <div
            role="alert"
            className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
          >
            <strong>Couldn&rsquo;t load SEO settings.</strong> {bootError}
          </div>
        )}

        {tab === "dashboard" && (
          <DashboardTab dashboard={dashboard} settings={settings} />
        )}
        {tab === "general" && (
          <GeneralTab
            settings={settings}
            onSaved={(next) => {
              setSettings(next);
              refresh();
            }}
          />
        )}
        {tab === "verifications" && (
          <VerificationsTab
            rows={verifications ?? []}
            onChanged={refresh}
          />
        )}
        {tab === "gtm" && (
          <GtmTab
            integrations={integrations ?? []}
            warning={dashboard?.duplicate_tracking_warning ?? null}
            onChanged={refresh}
          />
        )}
        {tab === "analytics" && (
          <AnalyticsTab
            integrations={integrations ?? []}
            gtmActive={dashboard?.gtm_active ?? false}
            onChanged={refresh}
          />
        )}
        {tab === "sitemap" && (
          <SitemapTab
            settings={settings}
            onSaved={(next) => {
              setSettings(next);
              refresh();
            }}
          />
        )}
        {tab === "robots" && (
          <RobotsTab
            settings={settings}
            onSaved={(next) => {
              setSettings(next);
              refresh();
            }}
          />
        )}
      </div>
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

function DashboardTab({
  dashboard,
  settings,
}: {
  dashboard: SeoDashboard | null;
  settings: SeoSettings | null;
}) {
  if (!dashboard || !settings) {
    return <LoadingCard label="Loading SEO dashboard…" />;
  }

  const items: Array<{
    label: string;
    active: boolean;
    detail?: string;
  }> = [
    {
      label: "Sitemap",
      active: dashboard.sitemap_enabled,
      detail: dashboard.sitemap_enabled ? "Enabled" : "Disabled",
    },
    {
      label: "Robots.txt",
      active: dashboard.robots_enabled,
      detail: dashboard.robots_enabled ? "Enabled" : "Disabled",
    },
    {
      label: "Google Search Console",
      active: dashboard.google_verification_active,
      detail: dashboard.google_verification_active
        ? "Verification active"
        : "Needs setup",
    },
    {
      label: "Bing Webmaster",
      active: dashboard.bing_verification_active,
      detail: dashboard.bing_verification_active
        ? "Verification active"
        : "Needs setup",
    },
    {
      label: "Meta Business",
      active: dashboard.meta_verification_active,
      detail: dashboard.meta_verification_active
        ? "Verification active"
        : "Needs setup",
    },
    {
      label: "Google Tag Manager",
      active: dashboard.gtm_active,
      detail: dashboard.gtm_id ?? "Not configured",
    },
    {
      label: "Google Analytics 4",
      active: dashboard.ga4_active,
      detail: dashboard.ga4_id ?? "Not configured",
    },
    {
      label: "Meta Pixel",
      active: dashboard.meta_pixel_active,
      detail: dashboard.meta_pixel_id ?? "Not configured",
    },
    {
      label: "Microsoft Clarity",
      active: dashboard.clarity_active,
      detail: dashboard.clarity_id ?? "Not configured",
    },
  ];

  return (
    <div className="space-y-4">
      {dashboard.duplicate_tracking_warning && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-amber-400/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-200"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-semibold">Duplicate tracking detected</p>
            <p>{dashboard.duplicate_tracking_warning}</p>
          </div>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">SEO health overview</CardTitle>
          <CardDescription>
            Live status of the SEO surface. Toggles you flip below appear
            here within a minute.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => (
              <div
                key={item.label}
                className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-muted/30 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{item.label}</p>
                  {item.detail && (
                    <p className="truncate text-xs text-muted-foreground">
                      {item.detail}
                    </p>
                  )}
                </div>
                <StatusBadge active={item.active} />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Quick actions</CardTitle>
          <CardDescription>
            Useful links — opens in a new tab.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            <QuickLink href="/sitemap.xml" label="Open /sitemap.xml" />
            <QuickLink href="/robots.txt" label="Open /robots.txt" />
            <QuickLink
              href="https://search.google.com/search-console"
              label="Google Search Console"
              external
            />
            <QuickLink
              href="https://analytics.google.com/analytics/web/"
              label="Google Analytics"
              external
            />
            <QuickLink
              href="https://tagmanager.google.com/"
              label="Google Tag Manager"
              external
            />
            <QuickLink
              href="https://business.facebook.com/events_manager"
              label="Meta Events Manager"
              external
            />
            <QuickLink
              href="https://www.bing.com/webmasters/"
              label="Bing Webmaster"
              external
            />
            <QuickLink
              href="https://search.google.com/test/rich-results"
              label="Rich Results Test"
              external
            />
            <QuickLink
              href="https://pagespeed.web.dev/"
              label="PageSpeed Insights"
              external
            />
          </div>
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Canonical base URL:{" "}
        <code className="rounded bg-muted px-1">
          {dashboard.canonical_base_url ?? "— not configured —"}
        </code>
        {dashboard.last_updated_at && (
          <>
            {" "}
            · last updated {new Date(dashboard.last_updated_at).toLocaleString()}
          </>
        )}
      </p>
    </div>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        active
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
          : "border-border/60 bg-muted/50 text-muted-foreground"
      )}
    >
      {active ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <AlertCircle className="h-3 w-3" />
      )}
      {active ? "Active" : "Needs setup"}
    </span>
  );
}

function QuickLink({
  href,
  label,
  external,
}: {
  href: string;
  label: string;
  external?: boolean;
}) {
  return (
    <Button asChild variant="outline" size="sm">
      <Link
        href={href}
        target={external ? "_blank" : undefined}
        rel={external ? "noopener noreferrer" : undefined}
      >
        {label}
        {external ? (
          <ExternalLink className="h-3.5 w-3.5" />
        ) : (
          <ArrowUpRight className="h-3.5 w-3.5" />
        )}
      </Link>
    </Button>
  );
}

// ---------------------------------------------------------------------------
// General SEO
// ---------------------------------------------------------------------------

function GeneralTab({
  settings,
  onSaved,
}: {
  settings: SeoSettings | null;
  onSaved: (next: SeoSettings) => void;
}) {
  if (!settings) return <LoadingCard label="Loading SEO settings…" />;
  return (
    <SaveCard<SeoSettings>
      title="General SEO settings"
      description="Site-wide defaults consumed by every public page. Individual pages can override these under Pages → Site pages → SEO."
      initial={settings}
      onSubmit={(form) => adminApi.patch<SeoSettings>("/admin/seo/settings", form)}
      onSaved={onSaved}
    >
      {(form, set) => (
        <>
          <Field label="Site name" hint="Falls back to the .env NEXT_PUBLIC_SITE_NAME when empty.">
            <Input
              value={form.site_name ?? ""}
              onChange={(e) => set("site_name", e.target.value || null)}
            />
          </Field>
          <Field
            label="Default meta title"
            hint={lengthHint(form.default_meta_title, 60)}
          >
            <Input
              value={form.default_meta_title ?? ""}
              onChange={(e) => set("default_meta_title", e.target.value || null)}
            />
          </Field>
          <Field
            label="Default meta description"
            hint={lengthHint(form.default_meta_description, 160)}
          >
            <Textarea
              rows={3}
              value={form.default_meta_description ?? ""}
              onChange={(e) =>
                set("default_meta_description", e.target.value || null)
              }
            />
          </Field>
          <Field label="Default meta keywords (comma-separated)">
            <Input
              value={form.default_meta_keywords ?? ""}
              onChange={(e) =>
                set("default_meta_keywords", e.target.value || null)
              }
              placeholder="paris united group, qatar, holding"
            />
          </Field>
          <Field
            label="Canonical base URL"
            hint="Must start with https://. Used as the prefix for every canonical link + the Sitemap line in robots.txt."
          >
            <Input
              value={form.canonical_base_url ?? ""}
              onChange={(e) =>
                set("canonical_base_url", e.target.value || null)
              }
              placeholder="https://www.pugholding.com"
            />
          </Field>
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Default language">
              <Input
                value={form.default_language ?? ""}
                onChange={(e) =>
                  set("default_language", e.target.value || null)
                }
                placeholder="en"
              />
            </Field>
            <Field label="Default country">
              <Input
                value={form.default_country ?? ""}
                onChange={(e) =>
                  set("default_country", e.target.value || null)
                }
                placeholder="QA"
              />
            </Field>
          </div>
          <Field
            label="Default OG image URL"
            hint="Recommended 1200x630. Used by social shares without an explicit image."
          >
            <Input
              value={form.default_og_image ?? ""}
              onChange={(e) => set("default_og_image", e.target.value || null)}
            />
          </Field>
          <Field
            label="Default Twitter image URL"
            hint="Recommended 1200x630."
          >
            <Input
              value={form.default_twitter_image ?? ""}
              onChange={(e) =>
                set("default_twitter_image", e.target.value || null)
              }
            />
          </Field>

          <div className="space-y-2 rounded-lg border border-border/60 bg-muted/30 p-3">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Feature toggles
            </p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <Toggle
                label="Enable Open Graph tags"
                value={form.enable_open_graph}
                onChange={(v) => set("enable_open_graph", v)}
              />
              <Toggle
                label="Enable Twitter Card tags"
                value={form.enable_twitter_cards}
                onChange={(v) => set("enable_twitter_cards", v)}
              />
              <Toggle
                label="Enable JSON-LD Schema"
                value={form.enable_json_ld}
                onChange={(v) => set("enable_json_ld", v)}
              />
              <Toggle
                label="Enable canonical URLs"
                value={form.enable_canonical}
                onChange={(v) => set("enable_canonical", v)}
              />
              <Toggle
                label="Enable breadcrumb schema"
                value={form.enable_breadcrumb_schema}
                onChange={(v) => set("enable_breadcrumb_schema", v)}
              />
              <Toggle
                label="Enable hreflang (multilingual)"
                value={form.enable_hreflang}
                onChange={(v) => set("enable_hreflang", v)}
                hint="Future-ready toggle — full multilingual wiring arrives later."
              />
            </div>
          </div>
        </>
      )}
    </SaveCard>
  );
}

// ---------------------------------------------------------------------------
// Verifications
// ---------------------------------------------------------------------------

const VERIFICATION_PROVIDERS: Array<{
  value: VerificationProvider;
  label: string;
}> = [
  { value: "google", label: "Google Search Console" },
  { value: "bing", label: "Bing Webmaster Tools" },
  { value: "meta", label: "Meta Business / Facebook" },
  { value: "pinterest", label: "Pinterest" },
  { value: "yandex", label: "Yandex" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "tiktok", label: "TikTok Business" },
  { value: "microsoft_ads", label: "Microsoft Advertising" },
  { value: "custom", label: "Custom" },
];

const VERIFICATION_TYPES: Array<{ value: VerificationType; label: string }> = [
  { value: "meta_tag", label: "Meta tag (name + content)" },
  { value: "full_meta_tag", label: "Full <meta> snippet paste" },
  { value: "html_file", label: "HTML verification file" },
  { value: "dns_txt", label: "DNS TXT (reference only)" },
];

function VerificationsTab({
  rows,
  onChanged,
}: {
  rows: SeoVerification[];
  onChanged: () => Promise<void>;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-base">Domain verification</CardTitle>
            <CardDescription>
              Meta tags, full snippets, HTML files, and DNS TXT references.
              Active rows render in the public <code>{`<head>`}</code> or, for
              HTML files, are served at the site root.
            </CardDescription>
          </div>
          <Button onClick={() => setOpen(true)} size="sm">
            <Plus className="h-4 w-4" />
            New verification
          </Button>
        </CardHeader>
        <CardContent>
          {rows.length === 0 ? (
            <EmptyState
              icon={<ShieldCheck className="h-6 w-6 opacity-60" />}
              title="No verifications yet"
              description="Add one to surface a Google / Bing / Meta verification meta tag or HTML file."
            />
          ) : (
            <div className="space-y-2">
              {rows.map((row) => (
                <VerificationRow
                  key={row.id}
                  row={row}
                  onChanged={onChanged}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {open && (
        <VerificationDialog
          onClose={() => setOpen(false)}
          onSaved={async () => {
            setOpen(false);
            await onChanged();
          }}
        />
      )}
    </div>
  );
}

function VerificationRow({
  row,
  onChanged,
}: {
  row: SeoVerification;
  onChanged: () => Promise<void>;
}) {
  const [editing, setEditing] = React.useState(false);
  const [working, setWorking] = React.useState(false);

  async function toggleActive() {
    setWorking(true);
    try {
      await adminApi.patch(`/admin/seo/verifications/${row.id}`, {
        is_active: !row.is_active,
      });
      await onChanged();
    } catch (err) {
      alert(err instanceof AdminApiError ? err.message : String(err));
    } finally {
      setWorking(false);
    }
  }

  async function remove() {
    if (!confirm(`Delete verification for ${row.provider}?`)) return;
    setWorking(true);
    try {
      await adminApi.delete(`/admin/seo/verifications/${row.id}`);
      await onChanged();
    } catch (err) {
      alert(err instanceof AdminApiError ? err.message : String(err));
    } finally {
      setWorking(false);
    }
  }

  const label = VERIFICATION_PROVIDERS.find((p) => p.value === row.provider)
    ?.label ?? row.provider;
  const typeLabel = VERIFICATION_TYPES.find(
    (t) => t.value === row.verification_type
  )?.label ?? row.verification_type;

  return (
    <>
      <div className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-muted/20 p-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-medium">{label}</p>
            <StatusBadge active={row.is_active} />
          </div>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {typeLabel}
            {row.verification_type === "html_file" && row.html_filename
              ? ` · /${row.html_filename}`
              : ""}
            {row.verification_type === "meta_tag" && row.verification_name
              ? ` · ${row.verification_name}`
              : ""}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            disabled={working}
            onClick={toggleActive}
          >
            {row.is_active ? "Disable" : "Enable"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
            Edit
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-rose-600 hover:text-rose-700"
            disabled={working}
            onClick={remove}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {editing && (
        <VerificationDialog
          existing={row}
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

function VerificationDialog({
  existing,
  onClose,
  onSaved,
}: {
  existing?: SeoVerification;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [form, setForm] = React.useState({
    provider: existing?.provider ?? ("google" as VerificationProvider),
    verification_type:
      existing?.verification_type ?? ("meta_tag" as VerificationType),
    verification_name: existing?.verification_name ?? "google-site-verification",
    verification_content: existing?.verification_content ?? "",
    full_meta_tag: existing?.full_meta_tag ?? "",
    html_filename: existing?.html_filename ?? "",
    html_file_content: existing?.html_file_content ?? "",
    dns_txt_value: existing?.dns_txt_value ?? "",
    is_active: existing?.is_active ?? true,
    notes: existing?.notes ?? "",
  });
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...form,
        verification_name: form.verification_name || null,
        verification_content: form.verification_content || null,
        full_meta_tag: form.full_meta_tag || null,
        html_filename: form.html_filename || null,
        html_file_content: form.html_file_content || null,
        dns_txt_value: form.dns_txt_value || null,
        notes: form.notes || null,
      };
      if (existing) {
        await adminApi.patch(
          `/admin/seo/verifications/${existing.id}`,
          payload
        );
      } else {
        await adminApi.post("/admin/seo/verifications", payload);
      }
      await onSaved();
    } catch (err) {
      setError(err instanceof AdminApiError ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      title={existing ? "Edit verification" : "New verification"}
      onClose={onClose}
    >
      <div className="space-y-3">
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Provider">
            <select
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={form.provider}
              onChange={(e) =>
                set("provider", e.target.value as VerificationProvider)
              }
            >
              {VERIFICATION_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Verification type">
            <select
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={form.verification_type}
              onChange={(e) =>
                set("verification_type", e.target.value as VerificationType)
              }
            >
              {VERIFICATION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>
        </div>

        {form.verification_type === "meta_tag" && (
          <>
            <Field label="Meta name" hint="e.g. google-site-verification">
              <Input
                value={form.verification_name}
                onChange={(e) =>
                  set("verification_name", e.target.value)
                }
              />
            </Field>
            <Field label="Content value">
              <Input
                value={form.verification_content}
                onChange={(e) =>
                  set("verification_content", e.target.value)
                }
              />
            </Field>
          </>
        )}

        {form.verification_type === "full_meta_tag" && (
          <Field
            label="Full <meta> snippet"
            hint="Paste the entire tag — we sanitise it and rebuild with safe attributes."
          >
            <Textarea
              rows={3}
              className="font-mono text-xs"
              value={form.full_meta_tag}
              onChange={(e) => set("full_meta_tag", e.target.value)}
              placeholder='<meta name="facebook-domain-verification" content="..." />'
            />
          </Field>
        )}

        {form.verification_type === "html_file" && (
          <>
            <Field
              label="Filename"
              hint="Must match a known pattern, e.g. googleXXXX.html, BingSiteAuth.xml, pinterest-XXXX.html"
            >
              <Input
                value={form.html_filename}
                onChange={(e) => set("html_filename", e.target.value)}
                placeholder="google1234567890abcd.html"
              />
            </Field>
            <Field label="File content">
              <Textarea
                rows={4}
                className="font-mono text-xs"
                value={form.html_file_content}
                onChange={(e) => set("html_file_content", e.target.value)}
                placeholder="google-site-verification: google1234567890abcd.html"
              />
            </Field>
            {existing && form.html_filename && (
              <p className="text-[11px] text-muted-foreground">
                File URL:{" "}
                <code className="rounded bg-muted px-1">
                  /{form.html_filename}
                </code>
              </p>
            )}
          </>
        )}

        {form.verification_type === "dns_txt" && (
          <Field
            label="DNS TXT record value"
            hint="Stored for reference only. The site never serves DNS data publicly — add the record manually with your DNS provider."
          >
            <Input
              value={form.dns_txt_value}
              onChange={(e) => set("dns_txt_value", e.target.value)}
            />
          </Field>
        )}

        <Field label="Notes (optional)">
          <Textarea
            rows={2}
            value={form.notes}
            onChange={(e) => set("notes", e.target.value)}
          />
        </Field>

        <Toggle
          label="Active"
          value={form.is_active}
          onChange={(v) => set("is_active", v)}
        />

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
          <Button onClick={save} disabled={saving}>
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// GTM
// ---------------------------------------------------------------------------

function GtmTab({
  integrations,
  warning,
  onChanged,
}: {
  integrations: TrackingIntegration[];
  warning: string | null;
  onChanged: () => Promise<void>;
}) {
  const existing = integrations.find((i) => i.provider === "google_tag_manager");
  return (
    <div className="space-y-4">
      {warning && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-amber-400/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-200"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>{warning}</div>
        </div>
      )}
      <IntegrationCard
        provider="google_tag_manager"
        title="Google Tag Manager (preferred hub)"
        description="Enter your GTM Container ID — we render the head loader and the noscript iframe automatically. No source-file edits required."
        existing={existing}
        idLabel="GTM Container ID"
        idPlaceholder="GTM-XXXXXXX"
        showDataLayer
        showNoscript
        onSaved={onChanged}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Analytics (everything that isn't GTM)
// ---------------------------------------------------------------------------

function AnalyticsTab({
  integrations,
  gtmActive,
  onChanged,
}: {
  integrations: TrackingIntegration[];
  gtmActive: boolean;
  onChanged: () => Promise<void>;
}) {
  const lookup = (provider: TrackingProvider) =>
    integrations.find((i) => i.provider === provider);

  return (
    <div className="space-y-4">
      {gtmActive && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-lg border border-amber-400/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-200"
        >
          <Info className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            GTM is active. Prefer running GA4 / Meta Pixel <em>inside</em> GTM
            rather than enabling these direct scripts — otherwise events fire
            twice.
          </div>
        </div>
      )}
      <IntegrationCard
        provider="google_analytics_ga4"
        title="Google Analytics 4"
        existing={lookup("google_analytics_ga4")}
        idLabel="Measurement ID"
        idPlaceholder="G-XXXXXXXXXX"
        showDebug
        onSaved={onChanged}
      />
      <IntegrationCard
        provider="meta_pixel"
        title="Meta / Facebook Pixel"
        existing={lookup("meta_pixel")}
        idLabel="Pixel ID"
        idPlaceholder="123456789012345"
        showNoscript
        onSaved={onChanged}
      />
      <IntegrationCard
        provider="microsoft_clarity"
        title="Microsoft Clarity"
        existing={lookup("microsoft_clarity")}
        idLabel="Clarity Project ID"
        idPlaceholder="abc123xyz"
        onSaved={onChanged}
      />
      <IntegrationCard
        provider="linkedin_insight"
        title="LinkedIn Insight Tag"
        existing={lookup("linkedin_insight")}
        idLabel="Partner ID"
        idPlaceholder="1234567"
        onSaved={onChanged}
      />
      <IntegrationCard
        provider="tiktok_pixel"
        title="TikTok Pixel"
        existing={lookup("tiktok_pixel")}
        idLabel="Pixel ID"
        idPlaceholder="C0XXXXXXXXXXXXXXXXXX"
        onSaved={onChanged}
      />
      <IntegrationCard
        provider="twitter_pixel"
        title="X (Twitter) Pixel"
        existing={lookup("twitter_pixel")}
        idLabel="Pixel ID"
        idPlaceholder="abc123"
        onSaved={onChanged}
      />
    </div>
  );
}

function IntegrationCard({
  provider,
  title,
  description,
  existing,
  idLabel,
  idPlaceholder,
  showDataLayer,
  showNoscript,
  showDebug,
  onSaved,
}: {
  provider: TrackingProvider;
  title: string;
  description?: string;
  existing?: TrackingIntegration;
  idLabel: string;
  idPlaceholder?: string;
  showDataLayer?: boolean;
  showNoscript?: boolean;
  showDebug?: boolean;
  onSaved: () => Promise<void>;
}) {
  const [form, setForm] = React.useState({
    tracking_id: existing?.tracking_id ?? "",
    data_layer_name: existing?.data_layer_name ?? "dataLayer",
    placement: (existing?.placement ?? "head") as ScriptPlacement,
    enable_noscript: existing?.enable_noscript ?? true,
    consent_mode_enabled: existing?.consent_mode_enabled ?? false,
    debug_mode: existing?.debug_mode ?? false,
    is_active: existing?.is_active ?? true,
    notes: existing?.notes ?? "",
  });
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [savedAt, setSavedAt] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (existing) {
      setForm({
        tracking_id: existing.tracking_id ?? "",
        data_layer_name: existing.data_layer_name ?? "dataLayer",
        placement: existing.placement,
        enable_noscript: existing.enable_noscript,
        consent_mode_enabled: existing.consent_mode_enabled,
        debug_mode: existing.debug_mode,
        is_active: existing.is_active,
        notes: existing.notes ?? "",
      });
    }
  }, [existing]);

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        provider,
        tracking_id: form.tracking_id.trim() || null,
        placement: form.placement,
        enable_noscript: form.enable_noscript,
        consent_mode_enabled: form.consent_mode_enabled,
        debug_mode: form.debug_mode,
        is_active: form.is_active,
        notes: form.notes || null,
      };
      if (showDataLayer) {
        payload.data_layer_name = form.data_layer_name || "dataLayer";
      }
      await adminApi.put("/admin/seo/integrations", payload);
      await onSaved();
      setSavedAt(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err instanceof AdminApiError ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function clearAll() {
    if (!existing) {
      // Nothing to clear server-side; just reset form.
      setForm({
        tracking_id: "",
        data_layer_name: "dataLayer",
        placement: "head",
        enable_noscript: true,
        consent_mode_enabled: false,
        debug_mode: false,
        is_active: true,
        notes: "",
      });
      return;
    }
    if (!confirm(`Delete the ${title} integration?`)) return;
    setSaving(true);
    try {
      await adminApi.delete(`/admin/seo/integrations/${provider}`);
      await onSaved();
    } catch (err) {
      setError(err instanceof AdminApiError ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </div>
          <StatusBadge
            active={!!existing && existing.is_active && !!(existing.tracking_id ?? "").trim()}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <Field label={idLabel}>
          <Input
            value={form.tracking_id}
            onChange={(e) => set("tracking_id", e.target.value)}
            placeholder={idPlaceholder}
          />
        </Field>
        {showDataLayer && (
          <Field
            label="Data Layer name"
            hint="Defaults to dataLayer. Change only if your GTM container expects a different global."
          >
            <Input
              value={form.data_layer_name}
              onChange={(e) => set("data_layer_name", e.target.value)}
            />
          </Field>
        )}
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Toggle
            label="Active"
            value={form.is_active}
            onChange={(v) => set("is_active", v)}
          />
          {showNoscript && (
            <Toggle
              label="Enable noscript fallback"
              value={form.enable_noscript}
              onChange={(v) => set("enable_noscript", v)}
              hint="GTM iframe / Meta Pixel image beacon for visitors without JS."
            />
          )}
          {showDebug && (
            <Toggle
              label="Debug mode"
              value={form.debug_mode}
              onChange={(v) => set("debug_mode", v)}
              hint="Adds debug_mode=true to gtag config. Use in staging only."
            />
          )}
          <Toggle
            label="Consent mode"
            value={form.consent_mode_enabled}
            onChange={(v) => set("consent_mode_enabled", v)}
            hint="Reserved for the future consent-mode wiring (Phase 3)."
          />
        </div>
        <Field label="Notes (optional)">
          <Textarea
            rows={2}
            value={form.notes}
            onChange={(e) => set("notes", e.target.value)}
          />
        </Field>
        {error && (
          <p
            role="alert"
            className="rounded-md border border-rose-500/40 bg-rose-500/10 p-2 text-xs text-rose-700 dark:text-rose-200"
          >
            {error}
          </p>
        )}
        <div className="flex items-center justify-between gap-2 pt-2">
          <div className="text-xs text-muted-foreground">
            {savedAt && <>Saved {savedAt}.</>}
          </div>
          <div className="flex gap-2">
            {existing && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearAll}
                disabled={saving}
                className="text-rose-600 hover:text-rose-700"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Remove
              </Button>
            )}
            <Button size="sm" onClick={save} disabled={saving}>
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Save
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sitemap
// ---------------------------------------------------------------------------

function SitemapTab({
  settings,
  onSaved,
}: {
  settings: SeoSettings | null;
  onSaved: (next: SeoSettings) => void;
}) {
  if (!settings) return <LoadingCard label="Loading sitemap settings…" />;
  return (
    <SaveCard<SeoSettings>
      title="Sitemap settings"
      description="The dynamic /sitemap.xml route honours these toggles. Use the per-page SEO panel under Pages to override an individual page."
      initial={settings}
      onSubmit={(form) => adminApi.patch<SeoSettings>("/admin/seo/settings", form)}
      onSaved={onSaved}
    >
      {(form, set) => (
        <>
          <Toggle
            label="Enable sitemap.xml"
            value={form.enable_sitemap}
            onChange={(v) => set("enable_sitemap", v)}
            hint="Off → /sitemap.xml still responds but with zero URLs."
          />
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Toggle
              label="Include static pages"
              value={form.sitemap_include_static}
              onChange={(v) => set("sitemap_include_static", v)}
            />
            <Toggle
              label="Include company pages"
              value={form.sitemap_include_companies}
              onChange={(v) => set("sitemap_include_companies", v)}
            />
            <Toggle
              label="Include CMS pages"
              value={form.sitemap_include_cms_pages}
              onChange={(v) => set("sitemap_include_cms_pages", v)}
            />
            <Toggle
              label="Include news pages"
              value={form.sitemap_include_news}
              onChange={(v) => set("sitemap_include_news", v)}
            />
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field
              label="Default change frequency"
              hint="Per-entry defaults are used when left blank."
            >
              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={form.sitemap_default_changefreq ?? ""}
                onChange={(e) =>
                  set("sitemap_default_changefreq", e.target.value || null)
                }
              >
                <option value="">— per-entry default —</option>
                {["always", "hourly", "daily", "weekly", "monthly", "yearly", "never"].map(
                  (v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  )
                )}
              </select>
            </Field>
            <Field label="Default priority (0.0 – 1.0)">
              <Input
                type="number"
                step="0.1"
                min={0}
                max={1}
                value={form.sitemap_default_priority ?? ""}
                onChange={(e) =>
                  set(
                    "sitemap_default_priority",
                    e.target.value === "" ? null : Number(e.target.value)
                  )
                }
              />
            </Field>
          </div>
          <p className="text-xs text-muted-foreground">
            View the rendered sitemap at{" "}
            <Link href="/sitemap.xml" target="_blank" className="underline">
              /sitemap.xml
            </Link>
            .
          </p>
        </>
      )}
    </SaveCard>
  );
}

// ---------------------------------------------------------------------------
// Robots
// ---------------------------------------------------------------------------

function RobotsTab({
  settings,
  onSaved,
}: {
  settings: SeoSettings | null;
  onSaved: (next: SeoSettings) => void;
}) {
  if (!settings) return <LoadingCard label="Loading robots settings…" />;

  return (
    <SaveCard<SeoSettings>
      title="Robots.txt"
      description="The dynamic /robots.txt route renders these settings. Custom content always wins when enabled."
      initial={settings}
      onSubmit={(form) => adminApi.patch<SeoSettings>("/admin/seo/settings", form)}
      onSaved={onSaved}
    >
      {(form, set) => (
        <>
          <div className="rounded-lg border border-amber-400/40 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-200">
            <FileWarning className="mr-1 inline h-3.5 w-3.5" />
            robots.txt is crawler guidance, not security. Admin / API routes
            still require authentication regardless of what you put here.
          </div>
          <Toggle
            label="Enable robots.txt"
            value={form.enable_robots}
            onChange={(v) => set("enable_robots", v)}
            hint="Off → returns 'User-agent: * / Disallow: /' (closed for indexing)."
          />
          <Toggle
            label="Use default robots template"
            value={form.robots_use_default}
            onChange={(v) => set("robots_use_default", v)}
            hint="On → blocks /admin /api /hr by default. Off → use custom content below."
          />
          <Field
            label="Extra disallow paths (one per line)"
            hint="Only used when 'Use default' is on."
          >
            <Textarea
              rows={3}
              className="font-mono text-xs"
              value={form.robots_extra_disallows ?? ""}
              onChange={(e) =>
                set("robots_extra_disallows", e.target.value || null)
              }
              placeholder="/search?\n/?utm="
            />
          </Field>
          <Field
            label="Custom robots.txt content"
            hint="Only used when 'Use default' is off. Sitemap line is appended automatically when missing."
          >
            <Textarea
              rows={6}
              className="font-mono text-xs"
              value={form.robots_custom_content ?? ""}
              onChange={(e) =>
                set("robots_custom_content", e.target.value || null)
              }
              placeholder="User-agent: Googlebot
Allow: /

User-agent: *
Disallow: /private/"
            />
          </Field>
          <p className="text-xs text-muted-foreground">
            View the rendered output at{" "}
            <Link href="/robots.txt" target="_blank" className="underline">
              /robots.txt
            </Link>
            .
          </p>
        </>
      )}
    </SaveCard>
  );
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function LoadingCard({ label }: { label: string }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-6 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {label}
      </CardContent>
    </Card>
  );
}

function EmptyState({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border/60 bg-muted/20 p-6 text-center">
      {icon}
      <p className="text-sm font-medium">{title}</p>
      <p className="text-xs text-muted-foreground">{description}</p>
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
          <span className="block text-[11px] text-muted-foreground">
            {hint}
          </span>
        )}
      </span>
    </label>
  );
}

function lengthHint(value: string | null, max: number): string {
  const len = (value ?? "").length;
  if (len === 0) return `Recommended length: under ${max} characters.`;
  if (len > max)
    return `${len}/${max} characters — over recommended limit, search engines may truncate.`;
  return `${len}/${max} characters.`;
}

function Dialog({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur"
    >
      <div className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-border/60 bg-background shadow-2xl">
        <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <h3 className="text-sm font-semibold">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-4 py-4">
          {children}
        </div>
      </div>
    </div>
  );
}

/**
 * Save-card wrapper used by the General, Sitemap, and Robots tabs.
 *
 * Tracks dirty state, runs the supplied submit fn, shows a toast on
 * success, and surfaces validation errors inline.
 */
function SaveCard<T extends object>({
  title,
  description,
  initial,
  onSubmit,
  onSaved,
  children,
}: {
  title: string;
  description?: string;
  initial: T;
  onSubmit: (form: T) => Promise<T>;
  onSaved: (next: T) => void;
  children: (form: T, set: <K extends keyof T>(key: K, value: T[K]) => void) => React.ReactNode;
}) {
  const [form, setForm] = React.useState<T>(initial);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [savedAt, setSavedAt] = React.useState<string | null>(null);

  React.useEffect(() => {
    setForm(initial);
  }, [initial]);

  function set<K extends keyof T>(key: K, value: T[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const next = await onSubmit(form);
      onSaved(next);
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
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-3">
        {children(form, set)}
        {error && (
          <p
            role="alert"
            className="rounded-md border border-rose-500/40 bg-rose-500/10 p-2 text-xs text-rose-700 dark:text-rose-200"
          >
            {error}
          </p>
        )}
        <div className="flex items-center justify-between pt-2">
          <div className="text-xs text-muted-foreground">
            {savedAt && <>Saved {savedAt}.</>}
          </div>
          <Button size="sm" onClick={save} disabled={saving}>
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save changes
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
