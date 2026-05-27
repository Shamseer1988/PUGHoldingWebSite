"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  DatabaseBackup,
  Download,
  FileWarning,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Upload,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { RequireSuperuser } from "@/components/admin/require-superuser";
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
import { adminApi, AdminApiError } from "@/lib/admin/api";

// ---------------------------------------------------------------------------
// Types — local to this page (the backup endpoints are not used elsewhere)
// ---------------------------------------------------------------------------

interface BackupInfo {
  is_postgres: boolean;
  tools_available: boolean;
  database_name: string | null;
  host: string | null;
  port: number | null;
  max_restore_mb: number;
}

interface SafetyBackup {
  filename: string;
  size_bytes: number;
  created_at: string;
}

interface RestoreResponse {
  ok: boolean;
  database_name: string;
  uploaded_size_bytes: number;
  safety_backup_filename: string;
  message: string;
}

// ---------------------------------------------------------------------------
// Page entry — wraps the body in the superuser guard
// ---------------------------------------------------------------------------

export default function DatabaseBackupPage() {
  const { user } = useAuth();
  if (!user?.is_superuser) {
    return (
      <AdminShell
        title="Database backup"
        description="Superuser-only system action."
      >
        <RequireSuperuser area="Database backup">{null}</RequireSuperuser>
      </AdminShell>
    );
  }
  return <BackupPageBody />;
}

// ---------------------------------------------------------------------------
// Body
// ---------------------------------------------------------------------------

function BackupPageBody() {
  const [info, setInfo] = React.useState<BackupInfo | null>(null);
  const [safety, setSafety] = React.useState<SafetyBackup[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [downloading, setDownloading] = React.useState(false);

  React.useEffect(() => {
    void refresh();
  }, []);

  async function refresh() {
    setError(null);
    try {
      const [i, s] = await Promise.all([
        adminApi.get<BackupInfo>("/admin/backup/info"),
        adminApi.get<{ backups: SafetyBackup[] }>("/admin/backup/safety"),
      ]);
      setInfo(i);
      setSafety(s.backups);
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function handleDownload() {
    setDownloading(true);
    setError(null);
    try {
      // The server stamps a sensible filename in Content-Disposition;
      // the fallback is only used if the response is malformed.
      await adminApi.downloadFile(
        "/admin/backup/download",
        `pug_backup_${Date.now()}.dump`
      );
      setToast(
        "Backup download started. Verify the file in your downloads folder before relying on it."
      );
      // Refresh after a moment in case a new safety backup landed
      // (download itself doesn't create one, but a future feature might).
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <AdminShell
      title="Database backup"
      description="Download a snapshot of the live database or restore from a previous .dump file. Superuser-only."
      actions={
        <Button
          variant="ghost"
          size="sm"
          onClick={refresh}
          aria-label="Refresh status"
        >
          <RefreshCw className="h-4 w-4" />
          <span className="hidden sm:inline">Refresh</span>
        </Button>
      }
    >
      <Toast message={toast} onClose={() => setToast(null)} />
      {error && (
        <div
          role="alert"
          className="mb-4 flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <EnvironmentCard info={info} />

      {/* Render action cards only when info has loaded. If the backend
          says we're not on Postgres or tools are missing, suppress the
          dangerous buttons but keep the explainer visible. */}
      {info && info.is_postgres && info.tools_available && (
        <>
          <DownloadCard
            info={info}
            downloading={downloading}
            onDownload={handleDownload}
          />
          <RestoreCard
            info={info}
            onSuccess={(msg) => {
              setToast(msg);
              void refresh();
            }}
            onError={(msg) => setError(msg)}
          />
          <SafetyList
            backups={safety}
            onDeleted={(name) => {
              setToast(`Deleted ${name}.`);
              void refresh();
            }}
            onError={(msg) => setError(msg)}
          />
        </>
      )}
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// Environment card — DB name, host, tooling check
// ---------------------------------------------------------------------------

function EnvironmentCard({ info }: { info: BackupInfo | null }) {
  if (!info) {
    return (
      <Card className="mb-4">
        <CardContent className="p-4 text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Checking database environment…
        </CardContent>
      </Card>
    );
  }

  const ready = info.is_postgres && info.tools_available;

  return (
    <Card className="mb-4">
      <CardHeader>
        <div className="flex items-start gap-3">
          <div
            className={
              ready
                ? "inline-flex h-9 w-9 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                : "inline-flex h-9 w-9 items-center justify-center rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-300"
            }
          >
            <Database className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle className="text-base">
              {ready ? "Database backup is available" : "Backup unavailable"}
            </CardTitle>
            <CardDescription className="mt-1">
              {ready
                ? "The server has the PostgreSQL client utilities installed and a Postgres database to act on."
                : !info.is_postgres
                  ? "The active database is not a PostgreSQL instance — backup and restore only work against Postgres."
                  : "PostgreSQL client utilities (pg_dump / pg_restore) are not installed on the application server."}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      {info.is_postgres && (
        <CardContent className="pt-0">
          <dl className="grid gap-3 text-sm sm:grid-cols-3">
            <Detail label="Database" value={info.database_name ?? "—"} mono />
            <Detail label="Host" value={info.host ?? "—"} mono />
            <Detail
              label="Port"
              value={info.port?.toString() ?? "—"}
              mono
            />
          </dl>
          {!info.tools_available && (
            <p className="mt-3 text-xs text-amber-700 dark:text-amber-300">
              Install the <code>postgresql-client</code> package on the
              application server, then refresh.
            </p>
          )}
        </CardContent>
      )}
    </Card>
  );
}

function Detail({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd className={mono ? "font-mono text-sm" : "text-sm"}>{value}</dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Download card
// ---------------------------------------------------------------------------

function DownloadCard({
  info,
  downloading,
  onDownload,
}: {
  info: BackupInfo;
  downloading: boolean;
  onDownload: () => void;
}) {
  return (
    <Card className="mb-4">
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-primary/15 text-primary">
            <Download className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle className="text-base">Download a backup</CardTitle>
            <CardDescription className="mt-1">
              Runs <code>pg_dump --format=custom</code> against{" "}
              <span className="font-mono">{info.database_name}</span> and
              streams the resulting <code>.dump</code> file to your
              browser. Nothing is kept server-side.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <Button onClick={onDownload} disabled={downloading}>
          {downloading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <DatabaseBackup className="h-4 w-4" />
          )}
          {downloading ? "Preparing backup…" : "Download backup"}
        </Button>
        <p className="mt-3 text-[11px] text-muted-foreground">
          Tip: download a fresh backup <strong>before</strong> running a
          restore — that file becomes your rollback if the restore goes
          sideways.
        </p>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Restore card — strict confirmation gate
// ---------------------------------------------------------------------------

function RestoreCard({
  info,
  onSuccess,
  onError,
}: {
  info: BackupInfo;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const [file, setFile] = React.useState<File | null>(null);
  const [confirm, setConfirm] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  const expected = info.database_name ?? "";
  const sizeMb = file ? (file.size / (1024 * 1024)).toFixed(1) : null;
  const overSize =
    file !== null && file.size > info.max_restore_mb * 1024 * 1024;
  const nameMatches = confirm.trim() === expected && expected.length > 0;
  const canSubmit = !!file && nameMatches && !overSize && !busy;

  async function submit() {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("confirm_db_name", confirm.trim());
      const res = await adminApi.postMultipart<RestoreResponse>(
        "/admin/backup/restore",
        fd
      );
      onSuccess(res.message);
      // Reset the form so a repeat restore needs explicit re-confirmation.
      setFile(null);
      setConfirm("");
      const input = document.getElementById(
        "restore-file"
      ) as HTMLInputElement | null;
      if (input) input.value = "";
    } catch (err) {
      onError((err as AdminApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mb-4 border-rose-500/30">
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-rose-500/15 text-rose-700 dark:text-rose-300">
            <Upload className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle className="text-base">
              Restore from a backup file
            </CardTitle>
            <CardDescription className="mt-1">
              Overwrites <span className="font-mono">{expected}</span>{" "}
              with the contents of a <code>pg_dump</code> custom-format{" "}
              <code>.dump</code> file. <strong>This cannot be undone</strong>
              {" "}without a prior backup.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        {/* Warning callout */}
        <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-700 dark:text-rose-200">
          <FileWarning className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            Restoring <em>replaces</em> every table in the live database.
            We&apos;ll automatically take a pre-restore safety backup
            first; even so, download a fresh backup from the card above
            before proceeding. Maximum upload size:{" "}
            <strong>{info.max_restore_mb} MB</strong>.
          </p>
        </div>

        {/* File picker */}
        <div className="space-y-1.5">
          <Label htmlFor="restore-file">
            Backup file (<code>.dump</code>)
          </Label>
          <Input
            id="restore-file"
            type="file"
            accept=".dump,application/octet-stream"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            disabled={busy}
          />
          {file && (
            <p
              className={
                overSize
                  ? "text-[11px] text-rose-600"
                  : "text-[11px] text-muted-foreground"
              }
            >
              {file.name} — {sizeMb} MB
              {overSize && ` (exceeds ${info.max_restore_mb} MB cap)`}
            </p>
          )}
        </div>

        {/* Confirm-by-typing gate */}
        <div className="space-y-1.5">
          <Label htmlFor="confirm-db-name">
            Type <code className="font-mono">{expected}</code> to confirm
          </Label>
          <Input
            id="confirm-db-name"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder={expected}
            autoComplete="off"
            disabled={busy}
          />
          {confirm.length > 0 && !nameMatches && (
            <p className="text-[11px] text-rose-600">
              Doesn&apos;t match the live database name yet.
            </p>
          )}
        </div>

        <Button
          variant="destructive"
          onClick={submit}
          disabled={!canSubmit}
          aria-disabled={!canSubmit}
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Upload className="h-4 w-4" />
          )}
          {busy ? "Restoring database…" : "Restore database"}
        </Button>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Safety backups list — show recent auto-created files
// ---------------------------------------------------------------------------

function SafetyList({
  backups,
  onDeleted,
  onError,
}: {
  backups: SafetyBackup[] | null;
  onDeleted: (name: string) => void;
  onError: (msg: string) => void;
}) {
  const [busy, setBusy] = React.useState<string | null>(null);

  async function download(name: string) {
    try {
      await adminApi.downloadFile(
        `/admin/backup/safety/${encodeURIComponent(name)}`,
        name,
        "GET"
      );
    } catch (err) {
      onError((err as AdminApiError).message);
    }
  }

  async function remove(name: string) {
    if (
      !confirm(
        `Delete ${name}? This safety backup will be gone for good — there's no trash bin for backup files.`
      )
    ) {
      return;
    }
    setBusy(name);
    try {
      await adminApi.delete(
        `/admin/backup/safety/${encodeURIComponent(name)}`
      );
      onDeleted(name);
    } catch (err) {
      onError((err as AdminApiError).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-300">
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle className="text-base">Safety backups</CardTitle>
            <CardDescription className="mt-1">
              Automatic pre-restore snapshots — kept for 7 days, then
              auto-deleted. Download any you want to retain off-server.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {backups === null ? (
          <p className="text-sm text-muted-foreground">
            <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
            Loading…
          </p>
        ) : backups.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No safety backups on disk. One will be created automatically
            the next time you run a restore.
          </p>
        ) : (
          <ul className="divide-y divide-border/60">
            {backups.map((b) => (
              <li
                key={b.filename}
                className="flex flex-wrap items-center justify-between gap-2 py-2.5"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-sm">{b.filename}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {new Date(b.created_at).toLocaleString()} —{" "}
                    {(b.size_bytes / (1024 * 1024)).toFixed(1)} MB
                  </p>
                </div>
                <div className="inline-flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => download(b.filename)}
                    aria-label={`Download ${b.filename}`}
                    title="Download"
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => remove(b.filename)}
                    disabled={busy === b.filename}
                    aria-label={`Delete ${b.filename}`}
                    title="Delete"
                    className="text-rose-600 hover:text-rose-700"
                  >
                    {busy === b.filename ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

function Toast({
  message,
  onClose,
}: {
  message: string | null;
  onClose: () => void;
}) {
  React.useEffect(() => {
    if (!message) return;
    const t = setTimeout(onClose, 4500);
    return () => clearTimeout(t);
  }, [message, onClose]);
  if (!message) return null;
  return (
    <div
      role="status"
      className="mb-4 flex items-start gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-200"
    >
      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
