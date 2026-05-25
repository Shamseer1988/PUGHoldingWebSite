"use client";

import * as React from "react";
import Link from "next/link";
import { notFound, useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  Image as ImageIcon,
  Layers,
  Loader2,
  Save,
  Search,
  Sparkles,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { ImageUpload } from "@/components/admin/image-upload";
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
  SitePage,
  SitePageKey,
  SitePageSection,
} from "@/lib/admin/types";

import { SITE_PAGE_REGISTRY, isSitePageKey } from "../../site-pages-config";


interface FormState {
  hero_eyebrow: string;
  hero_title: string;
  hero_description: string;
  banner_image_url: string;
  banner_mobile_url: string;
  banner_video_url: string;
  sections: Record<string, SitePageSection>;
  seo_title: string;
  seo_description: string;
  seo_keywords: string;
}


function blankForm(): FormState {
  return {
    hero_eyebrow: "",
    hero_title: "",
    hero_description: "",
    banner_image_url: "",
    banner_mobile_url: "",
    banner_video_url: "",
    sections: {},
    seo_title: "",
    seo_description: "",
    seo_keywords: "",
  };
}


export default function SitePageEditor() {
  const router = useRouter();
  const params = useParams<{ key: string }>();
  const rawKey = params?.key ?? "";

  if (!isSitePageKey(rawKey)) {
    notFound();
  }
  const key = rawKey as SitePageKey;
  const config = SITE_PAGE_REGISTRY[key];

  const [form, setForm] = React.useState<FormState | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  React.useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  async function refresh() {
    setError(null);
    try {
      const data = await adminApi.get<SitePage>(
        `/admin/cms/site-pages/${key}`
      );
      setForm({
        ...blankForm(),
        hero_eyebrow: data.hero_eyebrow ?? "",
        hero_title: data.hero_title ?? "",
        hero_description: data.hero_description ?? "",
        banner_image_url: data.banner_image_url ?? "",
        banner_mobile_url: data.banner_mobile_url ?? "",
        banner_video_url: data.banner_video_url ?? "",
        sections: { ...data.sections },
        seo_title: data.seo_title ?? "",
        seo_description: data.seo_description ?? "",
        seo_keywords: data.seo_keywords ?? "",
      });
    } catch (err) {
      setError((err as AdminApiError).message);
      setForm(blankForm());
    }
  }

  function set<K extends keyof FormState>(k: K, v: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [k]: v } : prev));
  }

  function setSection(
    sectionKey: string,
    patch: Partial<SitePageSection>
  ) {
    setForm((prev) => {
      if (!prev) return prev;
      const current = prev.sections[sectionKey] ?? {};
      return {
        ...prev,
        sections: {
          ...prev.sections,
          [sectionKey]: { ...current, ...patch },
        },
      };
    });
  }

  async function save() {
    if (!form) return;
    setSaving(true);
    setError(null);
    try {
      // Strip blank strings → null so empty inputs don't pollute the DB.
      const norm = (v: string) => (v.trim() ? v.trim() : null);
      const sectionsPayload: Record<string, SitePageSection> = {};
      for (const [k, v] of Object.entries(form.sections)) {
        const cleaned: SitePageSection = {};
        if (v.eyebrow?.trim()) cleaned.eyebrow = v.eyebrow.trim();
        if (v.title?.trim()) cleaned.title = v.title.trim();
        if (v.body?.trim()) cleaned.body = v.body.trim();
        if (cleaned.eyebrow || cleaned.title || cleaned.body) {
          sectionsPayload[k] = cleaned;
        }
      }
      const body = {
        hero_eyebrow: norm(form.hero_eyebrow),
        hero_title: norm(form.hero_title),
        hero_description: norm(form.hero_description),
        banner_image_url: norm(form.banner_image_url),
        banner_mobile_url: norm(form.banner_mobile_url),
        banner_video_url: norm(form.banner_video_url),
        sections: sectionsPayload,
        seo_title: norm(form.seo_title),
        seo_description: norm(form.seo_description),
        seo_keywords: norm(form.seo_keywords),
      };
      await adminApi.put<SitePage>(`/admin/cms/site-pages/${key}`, body);
      setToast("Page saved.");
      router.refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <AdminShell
      title={config.label}
      description={config.description}
      actions={
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link href="/admin/pages" aria-label="Back to pages">
              <ArrowLeft className="h-4 w-4" />
              <span className="hidden sm:inline">Back</span>
            </Link>
          </Button>
          <Button
            onClick={save}
            disabled={!form || saving}
            size="sm"
            aria-label="Save page"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            <span className="hidden sm:inline">Save changes</span>
          </Button>
        </div>
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

      <p className="mb-6 text-xs text-muted-foreground">
        Public route:{" "}
        <code className="rounded bg-muted px-1.5 py-0.5">{config.route}</code>
      </p>

      {form === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading…
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Hero card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="h-4 w-4 text-pug-gold-600" />
                Hero
              </CardTitle>
              <CardDescription>
                The eyebrow, headline, and description shown at the top of
                the page.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Eyebrow">
                <Input
                  value={form.hero_eyebrow}
                  onChange={(e) => set("hero_eyebrow", e.target.value)}
                  placeholder={config.placeholders.heroEyebrow ?? ""}
                  maxLength={120}
                  disabled={saving}
                />
              </Field>
              <Field label="Headline">
                <Textarea
                  rows={2}
                  value={form.hero_title}
                  onChange={(e) => set("hero_title", e.target.value)}
                  placeholder={config.placeholders.heroTitle ?? ""}
                  maxLength={255}
                  disabled={saving}
                />
              </Field>
              <Field label="Description">
                <Textarea
                  rows={3}
                  value={form.hero_description}
                  onChange={(e) => set("hero_description", e.target.value)}
                  placeholder={config.placeholders.heroDescription ?? ""}
                  disabled={saving}
                />
              </Field>
            </CardContent>
          </Card>

          {/* Banner card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ImageIcon className="h-4 w-4 text-pug-gold-600" />
                Banner
              </CardTitle>
              <CardDescription>
                Leave empty to fall back to the brand gradient. Mobile banner
                shows under sm; video overrides both when set.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label>Desktop banner image</Label>
                <ImageUpload
                  value={form.banner_image_url}
                  onChange={(url) => set("banner_image_url", url ?? "")}
                  disabled={saving}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Mobile banner image</Label>
                <ImageUpload
                  value={form.banner_mobile_url}
                  onChange={(url) => set("banner_mobile_url", url ?? "")}
                  disabled={saving}
                />
              </div>
              <Field label="Banner video URL (optional, overrides images)">
                <Input
                  value={form.banner_video_url}
                  onChange={(e) => set("banner_video_url", e.target.value)}
                  placeholder="https://… .mp4"
                  maxLength={500}
                  disabled={saving}
                />
              </Field>
            </CardContent>
          </Card>

          {/* Sections card — only rendered when this page has any */}
          {config.sections.length > 0 && (
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Layers className="h-4 w-4 text-pug-gold-600" />
                  Page sections
                </CardTitle>
                <CardDescription>
                  Additional editable copy that appears below the hero on
                  this page.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {config.sections.map((section) => {
                  const current = form.sections[section.key] ?? {};
                  return (
                    <section
                      key={section.key}
                      className="rounded-xl border border-border/60 bg-background/40 p-4"
                    >
                      <header className="mb-3">
                        <h3 className="text-sm font-semibold">{section.label}</h3>
                        {section.hint && (
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            {section.hint}
                          </p>
                        )}
                      </header>
                      <div className="grid gap-3 md:grid-cols-2">
                        {section.fields.includes("eyebrow") && (
                          <Field label="Eyebrow">
                            <Input
                              value={current.eyebrow ?? ""}
                              onChange={(e) =>
                                setSection(section.key, {
                                  eyebrow: e.target.value,
                                })
                              }
                              maxLength={120}
                              disabled={saving}
                              placeholder={section.placeholders?.eyebrow}
                            />
                          </Field>
                        )}
                        {section.fields.includes("title") && (
                          <Field label="Title">
                            <Input
                              value={current.title ?? ""}
                              onChange={(e) =>
                                setSection(section.key, {
                                  title: e.target.value,
                                })
                              }
                              maxLength={255}
                              disabled={saving}
                              placeholder={section.placeholders?.title}
                            />
                          </Field>
                        )}
                      </div>
                      {section.fields.includes("body") && (
                        <Field label="Body" className="mt-3">
                          <Textarea
                            rows={4}
                            value={current.body ?? ""}
                            onChange={(e) =>
                              setSection(section.key, { body: e.target.value })
                            }
                            disabled={saving}
                            placeholder={section.placeholders?.body}
                          />
                        </Field>
                      )}
                    </section>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {/* SEO card */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Search className="h-4 w-4 text-pug-gold-600" />
                SEO
              </CardTitle>
              <CardDescription>
                Overrides for this page's <code>&lt;title&gt;</code> + meta
                description. Leave blank to fall back to the site defaults
                in <em>Site settings</em>.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <Field label="SEO title">
                <Input
                  value={form.seo_title}
                  onChange={(e) => set("seo_title", e.target.value)}
                  maxLength={255}
                  disabled={saving}
                />
              </Field>
              <Field label="SEO keywords (comma-separated)">
                <Input
                  value={form.seo_keywords}
                  onChange={(e) => set("seo_keywords", e.target.value)}
                  maxLength={500}
                  disabled={saving}
                />
              </Field>
              <Field label="SEO description" className="md:col-span-2">
                <Textarea
                  rows={2}
                  value={form.seo_description}
                  onChange={(e) => set("seo_description", e.target.value)}
                  maxLength={500}
                  disabled={saving}
                />
              </Field>
            </CardContent>
          </Card>
        </div>
      )}
    </AdminShell>
  );
}


function Field({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`space-y-1.5 ${className ?? ""}`}>
      <Label>{label}</Label>
      {children}
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
