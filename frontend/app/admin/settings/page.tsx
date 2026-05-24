"use client";

import * as React from "react";
import { CheckCircle2, Loader2, Save } from "lucide-react";

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
import type { SiteSettings } from "@/lib/admin/types";

type Form = Omit<SiteSettings, "id">;

const EMPTY_FORM: Form = {
  site_name: "Paris United Group Holding",
  tagline: "",
  contact_phone: "",
  contact_email: "",
  contact_address: "",
  whatsapp_number: "",
  social_linkedin: "",
  social_instagram: "",
  social_facebook: "",
  social_youtube: "",
  seo_default_title: "",
  seo_default_description: "",
  seo_keywords: "",
  featured_companies_enabled: true,
  featured_companies_eyebrow: "",
  featured_companies_title: "",
  featured_companies_subtitle: "",
  featured_companies_cta_label: "",
  featured_companies_cta_url: "",
  featured_companies_animation_enabled: true,
  about_banner_image_url: "",
  about_banner_video_url: "",
  careers_banner_image_url: "",
  careers_banner_mobile_url: "",
  contact_banner_image_url: "",
  contact_banner_mobile_url: "",
  news_banner_image_url: "",
  news_banner_mobile_url: "",
  home_about_image_url: "",
  home_about_title: "",
  home_about_body: "",
  home_founder_image_url: "",
  home_founder_name: "",
  home_founder_role: "",
  home_founder_message: "",
  // ^ legacy fields — kept in the form payload only to satisfy
  //   the TypeScript shape; the UI no longer surfaces them. They were
  //   replaced by per-leader fields managed under /admin/leadership.
  home_brand_logos: "",
  home_brand_strip_title: "",
  home_leadership_section_enabled: true,
  home_leadership_section_eyebrow: "",
  home_leadership_section_title: "",
  home_leadership_section_subtitle: "",
  home_leadership_animation_enabled: true,
};

export default function SiteSettingsAdminPage() {
  const [form, setForm] = React.useState<Form | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  React.useEffect(() => { refresh(); }, []);

  async function refresh() {
    try {
      const data = await adminApi.get<SiteSettings>("/admin/cms/site-settings");
      setForm({
        ...EMPTY_FORM,
        ...Object.fromEntries(
          Object.entries(data).filter(([k]) => k !== "id")
        ),
      } as Form);
    } catch (err) {
      setError((err as AdminApiError).message);
      setForm(EMPTY_FORM);
    }
  }

  function set<K extends keyof Form>(k: K, v: Form[K]) {
    setForm((prev) => (prev ? { ...prev, [k]: v } : prev));
  }

  async function save() {
    if (!form) return;
    setSaving(true);
    setError(null);
    try {
      const body = Object.fromEntries(
        Object.entries(form).map(([k, v]) => [k, typeof v === "string" && !v.trim() ? null : v])
      );
      const updated = await adminApi.patch<SiteSettings>(
        "/admin/cms/site-settings",
        body
      );
      setForm({ ...EMPTY_FORM, ...Object.fromEntries(Object.entries(updated).filter(([k]) => k !== "id")) } as Form);
      setToast("Settings saved.");
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <AdminShell
      title="Site settings"
      description="Brand name, contact details, social links, and default SEO metadata."
      actions={
        <Button
          onClick={save}
          disabled={!form || saving}
          size="sm"
          aria-label="Save site settings"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          <span className="hidden sm:inline">Save changes</span>
        </Button>
      }
    >
      <Toast message={toast} onClose={() => setToast(null)} />
      {error && (
        <div role="alert" className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">
          {error}
        </div>
      )}

      {form === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading…
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Brand</CardTitle>
              <CardDescription>Shown in metadata and the navbar wordmark.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Site name" required>
                <Input value={form.site_name} onChange={(e) => set("site_name", e.target.value)} disabled={saving} />
              </Field>
              <Field label="Tagline">
                <Input value={form.tagline ?? ""} onChange={(e) => set("tagline", e.target.value)} disabled={saving} />
              </Field>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Contact</CardTitle>
              <CardDescription>Shown in the footer and contact page.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Phone">
                <Input value={form.contact_phone ?? ""} onChange={(e) => set("contact_phone", e.target.value)} disabled={saving} />
              </Field>
              <Field label="Email">
                <Input type="email" value={form.contact_email ?? ""} onChange={(e) => set("contact_email", e.target.value)} disabled={saving} />
              </Field>
              <Field label="Address">
                <Textarea rows={2} value={form.contact_address ?? ""} onChange={(e) => set("contact_address", e.target.value)} disabled={saving} />
              </Field>
              <Field label="WhatsApp number">
                <Input value={form.whatsapp_number ?? ""} onChange={(e) => set("whatsapp_number", e.target.value)} disabled={saving} />
              </Field>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Social</CardTitle>
              <CardDescription>Full URLs for each network.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="LinkedIn"><Input value={form.social_linkedin ?? ""} onChange={(e) => set("social_linkedin", e.target.value)} disabled={saving} /></Field>
              <Field label="Instagram"><Input value={form.social_instagram ?? ""} onChange={(e) => set("social_instagram", e.target.value)} disabled={saving} /></Field>
              <Field label="Facebook"><Input value={form.social_facebook ?? ""} onChange={(e) => set("social_facebook", e.target.value)} disabled={saving} /></Field>
              <Field label="YouTube"><Input value={form.social_youtube ?? ""} onChange={(e) => set("social_youtube", e.target.value)} disabled={saving} /></Field>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Default SEO</CardTitle>
              <CardDescription>Fallback metadata if a page doesn't define its own.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Default title"><Input value={form.seo_default_title ?? ""} onChange={(e) => set("seo_default_title", e.target.value)} disabled={saving} /></Field>
              <Field label="Default description"><Textarea rows={3} value={form.seo_default_description ?? ""} onChange={(e) => set("seo_default_description", e.target.value)} disabled={saving} /></Field>
              <Field label="Keywords"><Input value={form.seo_keywords ?? ""} onChange={(e) => set("seo_keywords", e.target.value)} disabled={saving} placeholder="comma, separated" /></Field>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">Homepage · Featured companies showcase</CardTitle>
              <CardDescription>
                Controls the dark pinned scroll section on the homepage. Companies are picked
                by flipping the "Highlight on homepage" toggle inside each company.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Show the section">
                  <label className="inline-flex items-center gap-2 pt-2 text-sm">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                      checked={form.featured_companies_enabled}
                      onChange={(e) =>
                        set("featured_companies_enabled", e.target.checked)
                      }
                      disabled={saving}
                    />
                    Render on the homepage
                  </label>
                </Field>
                <Field label="Scroll animation">
                  <label className="inline-flex items-center gap-2 pt-2 text-sm">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                      checked={form.featured_companies_animation_enabled}
                      onChange={(e) =>
                        set("featured_companies_animation_enabled", e.target.checked)
                      }
                      disabled={saving}
                    />
                    Enable GSAP scroll pin
                  </label>
                </Field>
              </div>

              <Field label="Eyebrow">
                <Input
                  value={form.featured_companies_eyebrow ?? ""}
                  onChange={(e) => set("featured_companies_eyebrow", e.target.value)}
                  disabled={saving}
                  placeholder="Group companies"
                />
              </Field>

              <Field label="Title">
                <Input
                  value={form.featured_companies_title ?? ""}
                  onChange={(e) => set("featured_companies_title", e.target.value)}
                  disabled={saving}
                  placeholder="A diversified portfolio, one trusted group."
                />
              </Field>

              <Field label="Subtitle">
                <Textarea
                  rows={2}
                  value={form.featured_companies_subtitle ?? ""}
                  onChange={(e) => set("featured_companies_subtitle", e.target.value)}
                  disabled={saving}
                  placeholder="Scroll to explore the businesses…"
                />
              </Field>

              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="CTA label">
                  <Input
                    value={form.featured_companies_cta_label ?? ""}
                    onChange={(e) =>
                      set("featured_companies_cta_label", e.target.value)
                    }
                    disabled={saving}
                    placeholder="View all companies"
                  />
                </Field>
                <Field label="CTA URL">
                  <Input
                    value={form.featured_companies_cta_url ?? ""}
                    onChange={(e) =>
                      set("featured_companies_cta_url", e.target.value)
                    }
                    disabled={saving}
                    placeholder="/companies"
                  />
                </Field>
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">Page banners</CardTitle>
              <CardDescription>
                Background imagery and video for each top-level page banner.
                Mobile variants replace the desktop image below the sm
                breakpoint.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <section className="space-y-3">
                <h3 className="text-sm font-semibold">About page</h3>
                <div className="space-y-1.5">
                  <Label>Background image</Label>
                  <ImageUpload
                    value={form.about_banner_image_url}
                    onChange={(url) => set("about_banner_image_url", url ?? "")}
                    disabled={saving}
                  />
                </div>
                <Field label="Background video URL">
                  <Input
                    value={form.about_banner_video_url ?? ""}
                    onChange={(e) => set("about_banner_video_url", e.target.value)}
                    disabled={saving}
                    placeholder="/video/our-company/about_banner.mp4"
                  />
                </Field>
              </section>

              <section className="space-y-3 border-t border-border/60 pt-5">
                <h3 className="text-sm font-semibold">Careers page</h3>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label>Desktop banner</Label>
                    <ImageUpload
                      value={form.careers_banner_image_url}
                      onChange={(url) => set("careers_banner_image_url", url ?? "")}
                      disabled={saving}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Mobile banner</Label>
                    <ImageUpload
                      value={form.careers_banner_mobile_url}
                      onChange={(url) => set("careers_banner_mobile_url", url ?? "")}
                      disabled={saving}
                    />
                  </div>
                </div>
              </section>

              <section className="space-y-3 border-t border-border/60 pt-5">
                <h3 className="text-sm font-semibold">Contact page</h3>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label>Desktop banner</Label>
                    <ImageUpload
                      value={form.contact_banner_image_url}
                      onChange={(url) => set("contact_banner_image_url", url ?? "")}
                      disabled={saving}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Mobile banner</Label>
                    <ImageUpload
                      value={form.contact_banner_mobile_url}
                      onChange={(url) => set("contact_banner_mobile_url", url ?? "")}
                      disabled={saving}
                    />
                  </div>
                </div>
              </section>

              <section className="space-y-3 border-t border-border/60 pt-5">
                <h3 className="text-sm font-semibold">News page</h3>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label>Desktop banner</Label>
                    <ImageUpload
                      value={form.news_banner_image_url}
                      onChange={(url) => set("news_banner_image_url", url ?? "")}
                      disabled={saving}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Mobile banner</Label>
                    <ImageUpload
                      value={form.news_banner_mobile_url}
                      onChange={(url) => set("news_banner_mobile_url", url ?? "")}
                      disabled={saving}
                    />
                  </div>
                </div>
              </section>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">Homepage · About the group</CardTitle>
              <CardDescription>
                The intro panel rendered between the business snapshot and
                the featured companies showcase. The Chairman + MD messages
                that used to live below this card are now managed from the{" "}
                <strong>Leadership</strong> sidebar entry — each leader
                carries their own photo, role label, quote, and paragraphs.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label>Image</Label>
                <ImageUpload
                  value={form.home_about_image_url}
                  onChange={(url) => set("home_about_image_url", url ?? "")}
                  disabled={saving}
                />
              </div>
              <Field label="Title">
                <Input
                  value={form.home_about_title ?? ""}
                  onChange={(e) => set("home_about_title", e.target.value)}
                  disabled={saving}
                  placeholder="Building everyday life across the GCC"
                />
              </Field>
              <Field label="Body">
                <Textarea
                  rows={4}
                  value={form.home_about_body ?? ""}
                  onChange={(e) => set("home_about_body", e.target.value)}
                  disabled={saving}
                />
              </Field>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">Homepage · Trusted brands strip</CardTitle>
              <CardDescription>
                A horizontal logo wall rendered above the leadership section.
                Paste one logo URL per line — either uploaded
                <code className="mx-1 rounded bg-muted px-1 py-0.5 text-[11px]">/api/v1/uploads/…</code>
                paths or public assets like
                <code className="mx-1 rounded bg-muted px-1 py-0.5 text-[11px]">/images/home/brands/brand_01.png</code>.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Section title">
                <Input
                  value={form.home_brand_strip_title ?? ""}
                  onChange={(e) => set("home_brand_strip_title", e.target.value)}
                  disabled={saving}
                  placeholder="Trusted brands we work with"
                />
              </Field>
              <Field label="Logo URLs (one per line)">
                <Textarea
                  rows={6}
                  value={form.home_brand_logos ?? ""}
                  onChange={(e) => set("home_brand_logos", e.target.value)}
                  disabled={saving}
                  placeholder={"/images/home/brands/brand_01.png\n/images/home/brands/brand_02.png"}
                />
              </Field>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">
                Homepage · Leadership Messages section
              </CardTitle>
              <CardDescription>
                Section copy + master toggles for the unified Chairman + MD
                Leadership Messages card on the homepage. Each leader's body
                copy (quote, message paragraphs, photo, signature) lives on
                the leader row itself — open <strong>Leadership</strong> in
                the sidebar and toggle "Feature on homepage Leadership
                Messages section" for each one.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Show the section">
                  <label className="inline-flex items-center gap-2 pt-2 text-sm">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                      checked={form.home_leadership_section_enabled}
                      onChange={(e) =>
                        set("home_leadership_section_enabled", e.target.checked)
                      }
                      disabled={saving}
                    />
                    Render on the homepage
                  </label>
                </Field>
                <Field label="Scroll animation">
                  <label className="inline-flex items-center gap-2 pt-2 text-sm">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                      checked={form.home_leadership_animation_enabled}
                      onChange={(e) =>
                        set("home_leadership_animation_enabled", e.target.checked)
                      }
                      disabled={saving}
                    />
                    Enable GSAP reveal animation
                  </label>
                </Field>
              </div>
              <Field label="Eyebrow">
                <Input
                  value={form.home_leadership_section_eyebrow ?? ""}
                  onChange={(e) =>
                    set("home_leadership_section_eyebrow", e.target.value)
                  }
                  disabled={saving}
                  placeholder="Leadership messages"
                />
              </Field>
              <Field label="Title">
                <Input
                  value={form.home_leadership_section_title ?? ""}
                  onChange={(e) =>
                    set("home_leadership_section_title", e.target.value)
                  }
                  disabled={saving}
                  placeholder="Guided by vision, driven by excellence"
                />
              </Field>
              <Field label="Subtitle">
                <Textarea
                  rows={2}
                  value={form.home_leadership_section_subtitle ?? ""}
                  onChange={(e) =>
                    set("home_leadership_section_subtitle", e.target.value)
                  }
                  disabled={saving}
                  placeholder="A message from the leadership of Paris United Group Holding."
                />
              </Field>
            </CardContent>
          </Card>
        </div>
      )}
    </AdminShell>
  );
}

function Field({ label, children, required }: { label: string; children: React.ReactNode; required?: boolean }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}{required && <span className="ml-0.5 text-rose-500">*</span>}</Label>
      {children}
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
      <CheckCircle2 className="h-4 w-4" />{message}
    </div>
  );
}
