"use client";

import * as React from "react";
import { Loader2, Save, ShieldCheck } from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import { cn } from "@/lib/utils";

interface RecruitmentSettings {
  job_approval_required: boolean;
}

/**
 * Super-Admin-only toggle for the HR job-approval workflow.
 *
 * Global on/off lives here; per-role bypass is the ``hr:jobs:post_direct``
 * permission, assigned in the Permission matrix.
 */
export default function RecruitmentSettingsPage() {
  const { user } = useAuth();
  const isSuperuser = Boolean(user?.is_superuser);

  const [required, setRequired] = React.useState<boolean | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [saved, setSaved] = React.useState(false);

  React.useEffect(() => {
    if (!isSuperuser) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await adminApi.get<RecruitmentSettings>(
          "/admin/recruitment-settings"
        );
        if (!cancelled) setRequired(data.job_approval_required);
      } catch (err) {
        if (!cancelled) setError((err as AdminApiError).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isSuperuser]);

  async function save() {
    if (required === null) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const data = await adminApi.put<RecruitmentSettings>(
        "/admin/recruitment-settings",
        { job_approval_required: required }
      );
      setRequired(data.job_approval_required);
      setSaved(true);
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  if (!isSuperuser) {
    return (
      <AdminShell
        title="Approval flow"
        description="Recruitment approval-workflow settings."
      >
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-amber-500" />
              Super Admin only
            </CardTitle>
            <CardDescription>
              These settings are restricted to Super Admin accounts.
            </CardDescription>
          </CardHeader>
        </Card>
      </AdminShell>
    );
  }

  return (
    <AdminShell
      title="Approval flow"
      description="Control whether HR job postings must be approved before they publish."
    >
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            Job approval workflow
          </CardTitle>
          <CardDescription>
            When on, new job openings go to an approver before the public site
            can show them. Turn it off to let jobs publish immediately on
            create.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {loading ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </p>
          ) : (
            <>
              <label className="flex items-start gap-3">
                <button
                  type="button"
                  role="switch"
                  aria-checked={required ?? false}
                  onClick={() => {
                    setRequired((v) => !v);
                    setSaved(false);
                  }}
                  disabled={saving}
                  className={cn(
                    "mt-0.5 inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors",
                    required ? "bg-primary" : "bg-muted"
                  )}
                >
                  <span
                    className={cn(
                      "inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform",
                      required ? "translate-x-5" : "translate-x-0.5"
                    )}
                  />
                </button>
                <span className="text-sm">
                  <span className="font-medium">
                    Require approval for job postings
                  </span>
                  <span className="block text-muted-foreground">
                    {required
                      ? "On — new jobs start as a draft and need an approver before publishing."
                      : "Off — new jobs are approved + published immediately on create."}
                  </span>
                </span>
              </label>

              <div className="rounded-md border border-border/60 bg-muted/40 p-3 text-xs text-muted-foreground">
                <p className="font-medium text-foreground">Per-role override</p>
                <p className="mt-1">
                  To let one role post directly even while approval is required
                  (e.g. HR Manager posts directly, HR Executive still needs
                  approval), grant that role the{" "}
                  <code className="text-[11px]">hr:jobs:post_direct</code>{" "}
                  permission in the{" "}
                  <a
                    href="/admin/roles"
                    className="text-primary hover:underline"
                  >
                    Permission matrix
                  </a>
                  .
                </p>
              </div>

              {error ? <p className="text-sm text-rose-600">{error}</p> : null}

              <div className="flex items-center gap-3">
                <Button type="button" onClick={save} disabled={saving}>
                  {saving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  <span className="ml-1">Save</span>
                </Button>
                {saved ? (
                  <span className="text-xs text-emerald-600">Saved.</span>
                ) : null}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </AdminShell>
  );
}
