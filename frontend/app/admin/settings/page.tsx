"use client";

import * as React from "react";
import { CheckCircle2, Loader2, Save } from "lucide-react";

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
        <Button onClick={save} disabled={!form || saving} size="sm">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save changes
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
