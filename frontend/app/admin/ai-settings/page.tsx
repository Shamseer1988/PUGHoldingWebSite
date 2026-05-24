"use client";

import * as React from "react";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  KeyRound,
  Loader2,
  Save,
  Server,
  Sparkles,
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
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import type { AISettings } from "@/lib/hr/types";

type Form = Pick<
  AISettings,
  | "mode"
  | "azure_endpoint"
  | "azure_deployment"
  | "azure_api_version"
  | "model_name"
  | "temperature"
  | "max_output_tokens"
  | "request_timeout_seconds"
  | "extra_system_prompt"
>;

export default function AISettingsAdminPage() {
  const [data, setData] = React.useState<AISettings | null>(null);
  const [form, setForm] = React.useState<Form | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);

  React.useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    try {
      const fresh = await adminApi.get<AISettings>("/admin/ai/settings");
      setData(fresh);
      setForm({
        mode: fresh.mode,
        azure_endpoint: fresh.azure_endpoint ?? "",
        azure_deployment: fresh.azure_deployment ?? "",
        azure_api_version: fresh.azure_api_version ?? "",
        model_name: fresh.model_name ?? "",
        temperature: fresh.temperature,
        max_output_tokens: fresh.max_output_tokens,
        request_timeout_seconds: fresh.request_timeout_seconds,
        extra_system_prompt: fresh.extra_system_prompt ?? "",
      });
    } catch (err) {
      setError((err as AdminApiError).message);
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
      const body = {
        mode: form.mode,
        azure_endpoint:
          typeof form.azure_endpoint === "string" && form.azure_endpoint.trim()
            ? form.azure_endpoint.trim()
            : null,
        azure_deployment:
          typeof form.azure_deployment === "string" && form.azure_deployment.trim()
            ? form.azure_deployment.trim()
            : null,
        azure_api_version:
          typeof form.azure_api_version === "string" && form.azure_api_version.trim()
            ? form.azure_api_version.trim()
            : null,
        model_name:
          typeof form.model_name === "string" && form.model_name.trim()
            ? form.model_name.trim()
            : null,
        temperature: Number(form.temperature),
        max_output_tokens: Number(form.max_output_tokens),
        request_timeout_seconds: Number(form.request_timeout_seconds),
        extra_system_prompt:
          typeof form.extra_system_prompt === "string" &&
          form.extra_system_prompt.trim()
            ? form.extra_system_prompt.trim()
            : null,
      };
      const fresh = await adminApi.patch<AISettings>(
        "/admin/ai/settings",
        body
      );
      setData(fresh);
      setToast("AI settings saved.");
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <AdminShell
      title="AI settings"
      description="Configure the Azure OpenAI integration used by HR for advisory candidate reviews."
      actions={
        <Button onClick={save} disabled={!form || saving} size="sm">
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save changes
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

      {/* Safety callout */}
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
        <Brain className="mt-0.5 h-5 w-5 text-amber-600" />
        <div>
          <p className="font-semibold text-amber-700 dark:text-amber-300">
            AI is advisory only
          </p>
          <p className="text-xs text-amber-700/90 dark:text-amber-200/90">
            The HR AI review never selects, rejects, hires, or blacklists a
            candidate. The model is constrained to one of four recommendations
            (<em>strong fit</em>, <em>possible fit</em>, <em>weak fit</em>,{" "}
            <em>needs more info</em>) and the final hiring decision is always
            made manually by an HR user.
          </p>
        </div>
      </div>

      {!form ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading…
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Mode</CardTitle>
              <CardDescription>
                Choose how candidate reviews are generated.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="AI mode">
                <Select
                  value={form.mode}
                  onChange={(e) => set("mode", e.target.value as Form["mode"])}
                  disabled={saving}
                >
                  <option value="disabled">Disabled — never call AI</option>
                  <option value="mock">Mock — deterministic test reviews</option>
                  <option value="live">Live — call Azure OpenAI</option>
                </Select>
              </Field>

              {data && (
                <div className="rounded-md border border-border/60 bg-background/40 p-3 text-xs">
                  <p className="font-semibold">Resolved configuration</p>
                  <ul className="mt-2 space-y-1 text-muted-foreground">
                    <li className="flex items-center gap-2">
                      <Sparkles className="h-3.5 w-3.5" />
                      Effective mode:{" "}
                      <span className="font-medium text-foreground">
                        {data.effective_mode ?? data.mode}
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <KeyRound className="h-3.5 w-3.5" />
                      Azure API key in .env:{" "}
                      {data.has_azure_api_key ? (
                        <span className="inline-flex items-center gap-1 font-medium text-emerald-700 dark:text-emerald-300">
                          <CheckCircle2 className="h-3 w-3" />
                          Detected
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 font-medium text-rose-700 dark:text-rose-300">
                          <AlertTriangle className="h-3 w-3" />
                          Missing — live mode will fail
                        </span>
                      )}
                    </li>
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Model</CardTitle>
              <CardDescription>
                Tuning parameters applied to every call.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Model / deployment label">
                <Input
                  value={form.model_name ?? ""}
                  onChange={(e) => set("model_name", e.target.value)}
                  placeholder="e.g. gpt-4o-mini"
                  disabled={saving}
                />
              </Field>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Field label="Temperature">
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    value={form.temperature}
                    onChange={(e) =>
                      set("temperature", Number(e.target.value))
                    }
                    disabled={saving}
                  />
                </Field>
                <Field label="Max output tokens">
                  <Input
                    type="number"
                    step="50"
                    min="64"
                    max="8000"
                    value={form.max_output_tokens}
                    onChange={(e) =>
                      set("max_output_tokens", Number(e.target.value))
                    }
                    disabled={saving}
                  />
                </Field>
                <Field label="Timeout (s)">
                  <Input
                    type="number"
                    step="5"
                    min="5"
                    max="300"
                    value={form.request_timeout_seconds}
                    onChange={(e) =>
                      set("request_timeout_seconds", Number(e.target.value))
                    }
                    disabled={saving}
                  />
                </Field>
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">Azure OpenAI</CardTitle>
              <CardDescription>
                Endpoint and deployment for live mode. Leave blank to fall back
                to the .env defaults. The API key always lives in .env — never
                in the database.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Azure endpoint URL">
                <Input
                  value={form.azure_endpoint ?? ""}
                  onChange={(e) => set("azure_endpoint", e.target.value)}
                  placeholder="https://<your-resource>.openai.azure.com"
                  disabled={saving}
                />
              </Field>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field label="Deployment name">
                  <Input
                    value={form.azure_deployment ?? ""}
                    onChange={(e) => set("azure_deployment", e.target.value)}
                    placeholder="gpt-4o-mini"
                    disabled={saving}
                  />
                </Field>
                <Field label="API version">
                  <Input
                    value={form.azure_api_version ?? ""}
                    onChange={(e) => set("azure_api_version", e.target.value)}
                    placeholder="2024-08-01-preview"
                    disabled={saving}
                  />
                </Field>
              </div>
              <Field label="Extra system prompt (optional)">
                <Textarea
                  rows={4}
                  value={form.extra_system_prompt ?? ""}
                  onChange={(e) => set("extra_system_prompt", e.target.value)}
                  placeholder="Append company values, locale conventions, or compliance notes to the system prompt."
                  disabled={saving}
                />
              </Field>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">How it works</CardTitle>
              <CardDescription className="space-y-2">
                <p>
                  <strong>Disabled:</strong> any HR Generate-Review action
                  returns a 409 with a clear message — no AI calls are ever
                  made.
                </p>
                <p>
                  <strong>Mock:</strong> deterministic synthetic reviews based
                  on the candidate's stored data. No network. Perfect for
                  dev/CI or running the product without Azure credentials.
                </p>
                <p>
                  <strong>Live:</strong> calls Azure OpenAI Chat Completions
                  with a JSON-schema prompt; the response is parsed,
                  rule-checked, and stored alongside the raw provider payload.
                </p>
              </CardDescription>
            </CardHeader>
          </Card>
        </div>
      )}
    </AdminShell>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
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
