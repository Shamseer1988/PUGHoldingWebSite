"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Inbox,
  KeyRound,
  Loader2,
  Mail,
  PlugZap,
  Save,
  Send,
  Server,
  ShieldCheck,
  Users,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { RequireSystemScope } from "@/components/admin/require-system-scope";
import { useAuth } from "@/components/auth-provider";
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
  EmailSettings,
  EmailSettingsUpdate,
  EmailTestResult,
  ImapTestResult,
} from "@/lib/admin/types";
import { cn } from "@/lib/utils";

type Form = {
  email_enabled: boolean;
  smtp_host: string;
  smtp_port: string;
  smtp_username: string;
  smtp_password: string;
  smtp_use_tls: boolean;
  smtp_use_ssl: boolean;
  email_from: string;
  email_from_name: string;
  email_reply_to: string;
  notification_email: string;
  test_email_to: string;
  // HR Advanced module — branded HR notifications
  hr_notification_emails: string; // newline/comma-separated for the textarea
  candidate_email_enabled: boolean;
  interview_email_enabled: boolean;
  job_approval_email_enabled: boolean;
  brand_logo_url: string;
  email_footer_text: string;
  // IMAP inbox (contact-ticket poller)
  imap_enabled: boolean;
  imap_host: string;
  imap_port: string;
  imap_username: string;
  imap_password: string;
  imap_use_ssl: boolean;
  imap_folder: string;
  imap_processed_folder: string;
  imap_error_folder: string;
  imap_poll_interval_minutes: string;
  imap_create_new_tickets: boolean;
};

function blankForm(): Form {
  return {
    email_enabled: false,
    smtp_host: "",
    smtp_port: "",
    smtp_username: "",
    smtp_password: "",
    smtp_use_tls: true,
    smtp_use_ssl: false,
    email_from: "",
    email_from_name: "",
    email_reply_to: "",
    notification_email: "",
    test_email_to: "",
    hr_notification_emails: "",
    candidate_email_enabled: true,
    interview_email_enabled: true,
    job_approval_email_enabled: true,
    brand_logo_url: "",
    email_footer_text: "",
    imap_enabled: false,
    imap_host: "",
    imap_port: "993",
    imap_username: "",
    imap_password: "",
    imap_use_ssl: true,
    imap_folder: "INBOX",
    imap_processed_folder: "",
    imap_error_folder: "",
    imap_poll_interval_minutes: "5",
    imap_create_new_tickets: false,
  };
}

function formFromSettings(s: EmailSettings): Form {
  return {
    email_enabled: s.email_enabled,
    smtp_host: s.smtp_host ?? "",
    smtp_port: s.smtp_port != null ? String(s.smtp_port) : "",
    smtp_username: s.smtp_username ?? "",
    // Password field always renders empty — blank means "keep existing".
    smtp_password: "",
    smtp_use_tls: s.smtp_use_tls,
    smtp_use_ssl: s.smtp_use_ssl,
    email_from: s.email_from ?? "",
    email_from_name: s.email_from_name ?? "",
    email_reply_to: s.email_reply_to ?? "",
    notification_email: s.notification_email ?? "",
    test_email_to: s.test_email_to ?? "",
    hr_notification_emails: (s.hr_notification_emails ?? []).join("\n"),
    candidate_email_enabled: s.candidate_email_enabled,
    interview_email_enabled: s.interview_email_enabled,
    job_approval_email_enabled: s.job_approval_email_enabled,
    brand_logo_url: s.brand_logo_url ?? "",
    email_footer_text: s.email_footer_text ?? "",
    imap_enabled: s.imap_enabled ?? false,
    imap_host: s.imap_host ?? "",
    imap_port: s.imap_port != null ? String(s.imap_port) : "993",
    imap_username: s.imap_username ?? "",
    imap_password: "",
    imap_use_ssl: s.imap_use_ssl ?? true,
    imap_folder: s.imap_folder ?? "INBOX",
    imap_processed_folder: s.imap_processed_folder ?? "",
    imap_error_folder: s.imap_error_folder ?? "",
    imap_poll_interval_minutes:
      s.imap_poll_interval_minutes != null
        ? String(s.imap_poll_interval_minutes)
        : "5",
    imap_create_new_tickets: s.imap_create_new_tickets ?? false,
  };
}

/** Split a textarea into a clean email list (newline OR comma separated). */
function parseEmailList(raw: string): string[] {
  return raw
    .split(/[\n,;]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function EmailSettingsAdminPage() {
  const { user } = useAuth();
  const hasSystem = Boolean(
    user?.is_superuser || user?.scopes?.includes("system")
  );
  if (!hasSystem) {
    return (
      <AdminShell
        title="Email configuration"
        description="System-only configuration."
      >
        <RequireSystemScope area="Email configuration">{null}</RequireSystemScope>
      </AdminShell>
    );
  }
  return <EmailSettingsBody />;
}

function EmailSettingsBody() {
  const [data, setData] = React.useState<EmailSettings | null>(null);
  const [form, setForm] = React.useState<Form>(blankForm);
  const [saving, setSaving] = React.useState(false);
  const [testing, setTesting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [testResult, setTestResult] = React.useState<EmailTestResult | null>(null);
  const [imapTesting, setImapTesting] = React.useState(false);
  const [imapTestResult, setImapTestResult] =
    React.useState<ImapTestResult | null>(null);

  React.useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    try {
      const fresh = await adminApi.get<EmailSettings>("/admin/email-settings");
      setData(fresh);
      setForm(formFromSettings(fresh));
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  function set<K extends keyof Form>(k: K, v: Form[K]) {
    setForm((prev) => ({ ...prev, [k]: v }));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const body: EmailSettingsUpdate = {
        email_enabled: form.email_enabled,
        smtp_host: form.smtp_host.trim() || null,
        smtp_port: form.smtp_port.trim() ? Number(form.smtp_port) : null,
        smtp_username: form.smtp_username.trim() || null,
        smtp_use_tls: form.smtp_use_tls,
        smtp_use_ssl: form.smtp_use_ssl,
        email_from: form.email_from.trim() || null,
        email_from_name: form.email_from_name.trim() || null,
        email_reply_to: form.email_reply_to.trim() || null,
        notification_email: form.notification_email.trim() || null,
        test_email_to: form.test_email_to.trim() || null,
        hr_notification_emails: parseEmailList(form.hr_notification_emails),
        candidate_email_enabled: form.candidate_email_enabled,
        interview_email_enabled: form.interview_email_enabled,
        job_approval_email_enabled: form.job_approval_email_enabled,
        brand_logo_url: form.brand_logo_url.trim() || null,
        email_footer_text: form.email_footer_text.trim() || null,
        imap_enabled: form.imap_enabled,
        imap_host: form.imap_host.trim() || null,
        imap_port: form.imap_port.trim() ? Number(form.imap_port) : null,
        imap_username: form.imap_username.trim() || null,
        imap_use_ssl: form.imap_use_ssl,
        imap_folder: form.imap_folder.trim() || null,
        imap_processed_folder: form.imap_processed_folder.trim() || null,
        imap_error_folder: form.imap_error_folder.trim() || null,
        imap_poll_interval_minutes: form.imap_poll_interval_minutes.trim()
          ? Number(form.imap_poll_interval_minutes)
          : null,
        imap_create_new_tickets: form.imap_create_new_tickets,
      };
      // Only send passwords when the admin actually typed one.
      if (form.smtp_password.length > 0) {
        body.smtp_password = form.smtp_password;
      }
      if (form.imap_password.length > 0) {
        body.imap_password = form.imap_password;
      }
      const fresh = await adminApi.put<EmailSettings>(
        "/admin/email-settings",
        body
      );
      setData(fresh);
      setForm(formFromSettings(fresh));
      setToast("Email configuration saved.");
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function sendTest() {
    const target = form.test_email_to.trim();
    if (!target) {
      setError("Enter a test recipient email first.");
      return;
    }
    setTesting(true);
    setError(null);
    setTestResult(null);
    try {
      const result = await adminApi.post<EmailTestResult>(
        "/admin/email-settings/test",
        { to_email: target }
      );
      setTestResult(result);
      if (result.success) {
        setToast(`Test email sent to ${target}.`);
      }
      // Reload row so the last_test_* badge updates.
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setTesting(false);
    }
  }

  async function testImap() {
    setImapTesting(true);
    setError(null);
    setImapTestResult(null);
    try {
      // Send the just-typed password (if any) so the admin can
      // verify creds without saving them first.
      const body: { imap_password?: string } = {};
      if (form.imap_password.length > 0) {
        body.imap_password = form.imap_password;
      }
      const result = await adminApi.post<ImapTestResult>(
        "/admin/email-settings/imap-test",
        body
      );
      setImapTestResult(result);
      if (result.success) {
        setToast("IMAP connection succeeded.");
      }
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setImapTesting(false);
    }
  }

  return (
    <AdminShell
      title="Email configuration"
      description="SMTP server and outbound sender identity used by every system email — admin replies, test sends, contact-form notifications."
      actions={
        <Button
          onClick={save}
          disabled={saving}
          size="sm"
          aria-label="Save email configuration"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          <span className="hidden sm:inline">Save configuration</span>
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

      {/* Status banner — at-a-glance state of the SMTP config */}
      {data && <StatusBanner data={data} />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 1. SMTP Server */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Server className="h-4 w-4 text-pug-green-600" />
              SMTP server
            </CardTitle>
            <CardDescription>
              Hostname, port, and credentials used to connect to the outbound
              mail server.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Host">
              <Input
                value={form.smtp_host}
                onChange={(e) => set("smtp_host", e.target.value)}
                placeholder="smtp.example.com"
                disabled={saving}
              />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Port">
                <Input
                  type="number"
                  min="1"
                  max="65535"
                  value={form.smtp_port}
                  onChange={(e) => set("smtp_port", e.target.value)}
                  placeholder="587"
                  disabled={saving}
                />
              </Field>
              <Field label="Username">
                <Input
                  value={form.smtp_username}
                  onChange={(e) => set("smtp_username", e.target.value)}
                  placeholder="noreply@example.com"
                  autoComplete="off"
                  disabled={saving}
                />
              </Field>
            </div>
            <Field
              label={
                data?.has_smtp_password
                  ? "Password (leave blank to keep existing)"
                  : "Password"
              }
            >
              <Input
                type="password"
                value={form.smtp_password}
                onChange={(e) => set("smtp_password", e.target.value)}
                placeholder={
                  data?.has_smtp_password
                    ? "•••••••••• (already set)"
                    : "Enter SMTP password"
                }
                autoComplete="new-password"
                disabled={saving}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Encrypted at rest. Never returned through the API.
              </p>
            </Field>
          </CardContent>
        </Card>

        {/* 2. Sender Details */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Mail className="h-4 w-4 text-pug-green-600" />
              Sender details
            </CardTitle>
            <CardDescription>
              Who outbound emails appear to come from, and where replies are
              routed.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="From email">
              <Input
                type="email"
                value={form.email_from}
                onChange={(e) => set("email_from", e.target.value)}
                placeholder="noreply@parisunitedgroup.com"
                disabled={saving}
              />
            </Field>
            <Field label="From name">
              <Input
                value={form.email_from_name}
                onChange={(e) => set("email_from_name", e.target.value)}
                placeholder="Paris United Group"
                disabled={saving}
              />
            </Field>
            <Field label="Reply-to (optional)">
              <Input
                type="email"
                value={form.email_reply_to}
                onChange={(e) => set("email_reply_to", e.target.value)}
                placeholder="support@parisunitedgroup.com"
                disabled={saving}
              />
            </Field>
            <Field label="Admin notification email (optional)">
              <Input
                type="email"
                value={form.notification_email}
                onChange={(e) => set("notification_email", e.target.value)}
                placeholder="inbox@parisunitedgroup.com"
                disabled={saving}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                When set, a short notification is sent here every time the
                public contact form is submitted. Delivery is best-effort —
                visitor submissions are never blocked by send failures.
              </p>
            </Field>
          </CardContent>
        </Card>

        {/* 3. Security */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-pug-green-600" />
              Security
            </CardTitle>
            <CardDescription>
              Connection encryption. Most providers want either STARTTLS on
              port 587 or implicit SSL on port 465 — not both.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Toggle
              label="Email enabled"
              hint="Master switch. When off, no outbound email is sent regardless of the other settings."
              checked={form.email_enabled}
              onChange={(v) => set("email_enabled", v)}
              disabled={saving}
            />
            <Toggle
              label="Use STARTTLS (recommended for port 587)"
              checked={form.smtp_use_tls}
              onChange={(v) => set("smtp_use_tls", v)}
              disabled={saving}
            />
            <Toggle
              label="Use implicit SSL (port 465)"
              hint="Turn on only if your provider requires implicit TLS instead of STARTTLS."
              checked={form.smtp_use_ssl}
              onChange={(v) => set("smtp_use_ssl", v)}
              disabled={saving}
            />
          </CardContent>
        </Card>

        {/* 4. Test Email */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Send className="h-4 w-4 text-pug-green-600" />
              Send test email
            </CardTitle>
            <CardDescription>
              Sends a real message using the saved configuration so you can
              verify deliverability before going live.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Test recipient">
              <Input
                type="email"
                value={form.test_email_to}
                onChange={(e) => set("test_email_to", e.target.value)}
                placeholder="you@example.com"
                disabled={saving || testing}
              />
            </Field>
            <Button
              type="button"
              variant="outline"
              onClick={sendTest}
              disabled={testing || saving || !form.test_email_to.trim()}
            >
              {testing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              Send test email
            </Button>

            {testResult && (
              <div
                className={
                  testResult.success
                    ? "rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-200"
                    : "rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
                }
                role="status"
              >
                <p className="font-semibold">
                  {testResult.success ? "Test sent." : "Test failed."}
                </p>
                <p className="mt-0.5 text-xs">{testResult.message}</p>
              </div>
            )}

            {data && data.last_test_at && (
              <p className="text-xs text-muted-foreground">
                Last attempt: {new Date(data.last_test_at).toLocaleString()} —{" "}
                {data.last_test_status === "success" ? "succeeded" : "failed"}
                {data.last_test_message ? `: ${data.last_test_message}` : "."}
              </p>
            )}
          </CardContent>
        </Card>

        {/* 5. HR notifications + branded templates (advanced module) */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Users className="h-4 w-4 text-pug-green-600" />
              HR notifications &amp; branded templates
            </CardTitle>
            <CardDescription>
              Configures the recipient list, per-event mute switches, and the
              header/footer chrome used by every HR-side email (job approval,
              candidate status, interview invitations).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <Field label="HR notification recipients">
              <Textarea
                value={form.hr_notification_emails}
                onChange={(e) =>
                  set("hr_notification_emails", e.target.value)
                }
                placeholder={
                  "hr-manager@parisunitedgroup.com\nrecruitment@parisunitedgroup.com"
                }
                rows={3}
                disabled={saving}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                One email per line (commas also work). These addresses are
                CC&apos;d on every job approval-workflow event — submitted,
                approved, rejected, revision-requested, published.
              </p>
            </Field>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Toggle
                label="Job approval emails"
                hint="Job submitted / approved / rejected / revision requested / published."
                checked={form.job_approval_email_enabled}
                onChange={(v) => set("job_approval_email_enabled", v)}
                disabled={saving}
              />
              <Toggle
                label="Candidate emails"
                hint="Application received, shortlisted, rejected, selected."
                checked={form.candidate_email_enabled}
                onChange={(v) => set("candidate_email_enabled", v)}
                disabled={saving}
              />
              <Toggle
                label="Interview emails"
                hint="Interview scheduled / rescheduled / cancelled invitations."
                checked={form.interview_email_enabled}
                onChange={(v) => set("interview_email_enabled", v)}
                disabled={saving}
              />
            </div>

            <Field label="Brand logo URL (optional)">
              <Input
                type="url"
                value={form.brand_logo_url}
                onChange={(e) => set("brand_logo_url", e.target.value)}
                placeholder="https://parisunitedgroup.com/logo.png"
                disabled={saving}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Shown at the top of every branded HR email. Use a full HTTPS
                URL — most email clients block relative paths and many block
                HTTP.
              </p>
            </Field>

            <Field label="Email footer text (optional)">
              <Textarea
                value={form.email_footer_text}
                onChange={(e) => set("email_footer_text", e.target.value)}
                placeholder="© Paris United Group Holding. This is an automated notification — please do not reply."
                rows={2}
                disabled={saving}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Appears in the muted footer band of every HR email. Leave
                blank to use the default copy.
              </p>
            </Field>
          </CardContent>
        </Card>

        {/* 6. IMAP inbox (contact-ticket poller) — admin replies use
            the SMTP block above; this block pulls customer replies
            in so the inbox stays live. Configured here so credentials
            can be rotated without restarting the API. */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Inbox className="h-4 w-4 text-pug-green-600" />
              IMAP inbox
              <ImapStatusPill data={data} />
            </CardTitle>
            <CardDescription>
              Mailbox the contact-ticket reply poller reads from. Customer
              replies land back on their existing ticket. Microsoft 365
              mailboxes require an App Password (Basic Auth) or OAuth.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Behaviour callout — the user explicitly asked for this:
                only ticket replies show up in the contact center, all
                other mail must behave exactly like Outlook normally
                would (unread, in INBOX, untouched). */}
            <div className="rounded-lg border border-pug-green-600/30 bg-pug-green-600/5 p-3 text-xs text-pug-green-800 dark:border-pug-green-500/40 dark:bg-pug-green-500/10 dark:text-pug-green-100">
              <p className="font-semibold">How non-ticket mail is handled</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[11px] leading-snug">
                <li>
                  Customer replies that match an existing ticket are
                  pulled into the admin Contact Center as chat bubbles
                  and marked <span className="font-medium">read</span> in
                  this mailbox.
                </li>
                <li>
                  Every other email — newsletters, vendor pings, anything
                  unrelated — is <span className="font-medium">left
                  completely untouched</span>. It stays unread in your
                  Outlook inbox.
                </li>
                <li>
                  We use an invisible IMAP keyword
                  (<code className="rounded bg-muted px-1">$PUG-Inspected</code>)
                  to remember which UIDs we&apos;ve already looked at, so
                  the same message isn&apos;t re-fetched on every poll.
                </li>
              </ul>
            </div>

            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 rounded border-border accent-primary"
                checked={form.imap_enabled}
                onChange={(e) => set("imap_enabled", e.target.checked)}
                disabled={saving}
              />
              <span>
                Enable IMAP inbound polling.{" "}
                <span className="text-xs text-muted-foreground">
                  When off, no scheduled or manual poll fires — admin
                  replies still go out via SMTP above.
                </span>
              </span>
            </label>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field label="Host">
                <Input
                  value={form.imap_host}
                  onChange={(e) => set("imap_host", e.target.value)}
                  placeholder="imap.example.com"
                  disabled={saving}
                />
              </Field>
              <Field label="Port">
                <Input
                  type="number"
                  min="1"
                  max="65535"
                  value={form.imap_port}
                  onChange={(e) => set("imap_port", e.target.value)}
                  placeholder="993"
                  disabled={saving}
                />
              </Field>
              <Field label="Folder">
                <Input
                  value={form.imap_folder}
                  onChange={(e) => set("imap_folder", e.target.value)}
                  placeholder="INBOX"
                  disabled={saving}
                />
              </Field>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Username">
                <Input
                  value={form.imap_username}
                  onChange={(e) => set("imap_username", e.target.value)}
                  placeholder="support@example.com"
                  autoComplete="off"
                  disabled={saving}
                />
              </Field>
              <Field
                label={
                  data?.has_imap_password
                    ? "Password (leave blank to keep existing)"
                    : "Password"
                }
              >
                <Input
                  type="password"
                  value={form.imap_password}
                  onChange={(e) => set("imap_password", e.target.value)}
                  placeholder={
                    data?.has_imap_password
                      ? "•••••••••• (already set)"
                      : "App password or mailbox password"
                  }
                  autoComplete="new-password"
                  disabled={saving}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  Encrypted at rest. M365/Outlook needs a 16-char App
                  Password — your normal sign-in password will fail.
                </p>
              </Field>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border accent-primary"
                  checked={form.imap_use_ssl}
                  onChange={(e) => set("imap_use_ssl", e.target.checked)}
                  disabled={saving}
                />
                Use SSL (port 993)
              </label>
              <Field label="Poll interval (minutes)">
                <Input
                  type="number"
                  min="1"
                  max="1440"
                  value={form.imap_poll_interval_minutes}
                  onChange={(e) =>
                    set("imap_poll_interval_minutes", e.target.value)
                  }
                  placeholder="5"
                  disabled={saving}
                />
              </Field>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 rounded border-border accent-primary"
                  checked={form.imap_create_new_tickets}
                  onChange={(e) =>
                    set("imap_create_new_tickets", e.target.checked)
                  }
                  disabled={saving}
                />
                <span>
                  Open new tickets from unrecognised mail
                  <span className="block text-[11px] text-muted-foreground">
                    Off by default — leave off unless this mailbox
                    is dedicated to ticket intake.
                  </span>
                </span>
              </label>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Processed folder (optional)">
                <Input
                  value={form.imap_processed_folder}
                  onChange={(e) =>
                    set("imap_processed_folder", e.target.value)
                  }
                  placeholder="Processed"
                  disabled={saving}
                />
              </Field>
              <Field label="Error folder (optional)">
                <Input
                  value={form.imap_error_folder}
                  onChange={(e) =>
                    set("imap_error_folder", e.target.value)
                  }
                  placeholder="Errors"
                  disabled={saving}
                />
              </Field>
            </div>

            <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium">Test connection</p>
                  <p className="text-xs text-muted-foreground">
                    Opens a real IMAP session, logs in, lists folders,
                    and selects the chosen one. Nothing is sent or
                    moved.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={testImap}
                  disabled={imapTesting || saving}
                >
                  {imapTesting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <PlugZap className="h-4 w-4" />
                  )}
                  Test IMAP
                </Button>
              </div>

              {imapTestResult && (
                <div
                  className={cn(
                    "mt-3 rounded-md border p-2.5 text-xs",
                    imapTestResult.success
                      ? "border-emerald-500/40 bg-emerald-500/5 text-emerald-900 dark:text-emerald-200"
                      : "border-rose-500/40 bg-rose-500/5 text-rose-900 dark:text-rose-200"
                  )}
                  role="status"
                >
                  <div className="flex items-start gap-2">
                    {imapTestResult.success ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                    ) : (
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    )}
                    <div className="min-w-0 space-y-1">
                      <p className="leading-snug">
                        {imapTestResult.message}
                      </p>
                      {imapTestResult.server_greeting && (
                        <p className="font-mono text-[10px] opacity-70">
                          {imapTestResult.server_greeting}
                        </p>
                      )}
                      {imapTestResult.folders_sampled.length > 0 && (
                        <p className="text-[11px] opacity-80">
                          Folders seen:{" "}
                          {imapTestResult.folders_sampled
                            .slice(0, 8)
                            .join(", ")}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {!imapTestResult && data?.last_imap_test_status &&
                data.last_imap_test_status !== "never" && (
                  <p className="mt-2 text-[11px] text-muted-foreground">
                    Last test:{" "}
                    <span
                      className={cn(
                        "font-medium",
                        data.last_imap_test_status === "success"
                          ? "text-emerald-700 dark:text-emerald-300"
                          : "text-rose-700 dark:text-rose-300"
                      )}
                    >
                      {data.last_imap_test_status}
                    </span>
                    {data.last_imap_test_at &&
                      ` · ${new Date(data.last_imap_test_at).toLocaleString()}`}
                    {data.last_imap_test_message && (
                      <span className="ml-2 italic">
                        {data.last_imap_test_message}
                      </span>
                    )}
                  </p>
                )}
            </div>
          </CardContent>
        </Card>
      </div>
    </AdminShell>
  );
}


function ImapStatusPill({ data }: { data: EmailSettings | null }) {
  if (!data) return null;
  const enabled = data.imap_enabled;
  const last = data.last_imap_test_status;
  let label = enabled ? "Enabled" : "Disabled";
  let tone = enabled
    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200"
    : "border-zinc-400/40 bg-zinc-500/10 text-zinc-700 dark:text-zinc-300";
  if (enabled && last === "failed") {
    label = "Test failed";
    tone = "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-200";
  }
  return (
    <span
      className={cn(
        "ml-2 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider",
        tone
      )}
    >
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function StatusBanner({ data }: { data: EmailSettings }) {
  const enabled = data.email_enabled;
  const passOk = data.has_smtp_password;
  const lastTest = data.last_test_status;

  const items: { label: string; tone: "good" | "warn" | "bad" }[] = [
    {
      label: enabled ? "Email enabled" : "Email disabled",
      tone: enabled ? "good" : "warn",
    },
    {
      label: passOk ? "Password set" : "No password configured",
      tone: passOk ? "good" : "warn",
    },
    {
      label:
        lastTest === "success"
          ? "Last test succeeded"
          : lastTest === "failed"
            ? "Last test failed"
            : "No test yet",
      tone:
        lastTest === "success"
          ? "good"
          : lastTest === "failed"
            ? "bad"
            : "warn",
    },
  ];

  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      {items.map((it) => (
        <Pill key={it.label} tone={it.tone}>
          {it.tone === "good" ? (
            <CheckCircle2 className="h-3 w-3" />
          ) : it.tone === "bad" ? (
            <AlertTriangle className="h-3 w-3" />
          ) : (
            <KeyRound className="h-3 w-3" />
          )}
          {it.label}
        </Pill>
      ))}
      {data.env_fallback_active && (
        <Pill tone="warn">
          <KeyRound className="h-3 w-3" />
          Using .env fallback
        </Pill>
      )}
    </div>
  );
}

function Pill({
  tone,
  children,
}: {
  tone: "good" | "warn" | "bad";
  children: React.ReactNode;
}) {
  const styles =
    tone === "good"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200"
      : tone === "bad"
        ? "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-200"
        : "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-200";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${styles}`}
    >
      {children}
    </span>
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

function Toggle({
  label,
  hint,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex items-start gap-3 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className="mt-0.5 h-4 w-4 accent-pug-green-600"
      />
      <span className="flex-1">
        <span className="font-medium">{label}</span>
        {hint && (
          <span className="block text-xs text-muted-foreground">{hint}</span>
        )}
      </span>
    </label>
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
