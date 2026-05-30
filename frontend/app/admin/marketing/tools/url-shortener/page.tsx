"use client";

import * as React from "react";
import {
  CheckCircle2,
  Copy,
  Eye,
  EyeOff,
  ExternalLink,
  Link2,
  Loader2,
  Plus,
  Trash2,
  X,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import { env } from "@/lib/env";
import { cn } from "@/lib/utils";

interface ShortUrlRead {
  id: number;
  slug: string;
  target_url: string;
  title: string | null;
  is_active: boolean;
  expires_at: string | null;
  click_count: number;
  last_click_at: string | null;
  created_at: string;
  updated_at: string;
}

interface ShortUrlListResponse {
  items: ShortUrlRead[];
  total: number;
}

const BASE = "/admin/marketing/short-urls";

function shortUrlFor(slug: string): string {
  // Browser-side: use the current origin so the URL works on any
  // domain the admin happens to be logged into. Falls back to
  // ``env.siteUrl`` during SSR (which doesn't actually render this
  // client component, but keeps the helper safe to call anywhere).
  if (typeof window !== "undefined") {
    return `${window.location.origin}/go/${slug}`;
  }
  return `${env.siteUrl}/go/${slug}`;
}

export default function UrlShortenerPage() {
  const [rows, setRows] = React.useState<ShortUrlRead[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [search, setSearch] = React.useState("");
  const [includeInactive, setIncludeInactive] = React.useState(true);
  const [creating, setCreating] = React.useState(false);

  const refresh = React.useCallback(async () => {
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("include_inactive", String(includeInactive));
      if (search.trim()) params.set("search", search.trim());
      const data = await adminApi.get<ShortUrlListResponse>(
        `${BASE}?${params.toString()}`,
      );
      setRows(data.items);
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }, [includeInactive, search]);

  React.useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  async function toggleActive(row: ShortUrlRead) {
    try {
      await adminApi.patch(`${BASE}/${row.id}`, { is_active: !row.is_active });
      setToast(
        row.is_active
          ? `Disabled /go/${row.slug}`
          : `Enabled /go/${row.slug}`,
      );
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function remove(row: ShortUrlRead) {
    if (
      !confirm(
        `Delete /go/${row.slug}? This is permanent — the slug becomes available for reuse and the click history is lost.`,
      )
    ) {
      return;
    }
    try {
      await adminApi.delete(`${BASE}/${row.id}`);
      setToast(`Deleted /go/${row.slug}`);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function copy(slug: string) {
    try {
      await navigator.clipboard.writeText(shortUrlFor(slug));
      setToast(`Copied ${shortUrlFor(slug)}`);
    } catch {
      setToast("Could not access the clipboard — copy the URL by hand.");
    }
  }

  return (
    <AdminShell
      title="URL Shortener"
      description="Branded short links served from /go/{slug}. Click counts update live; disable a link to break it without losing history."
      actions={
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New short URL</span>
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

      {creating && (
        <CreateForm
          onCancel={() => setCreating(false)}
          onCreated={async (created) => {
            setCreating(false);
            setToast(`Created ${shortUrlFor(created.slug)}`);
            await refresh();
          }}
          onError={setError}
        />
      )}

      {/* Filter bar */}
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border/60 bg-background/60 p-4 backdrop-blur">
        <div className="min-w-[200px] flex-1 space-y-1.5">
          <Label htmlFor="search">Search</Label>
          <Input
            id="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void refresh()}
            placeholder="Slug, target URL or title"
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
          />
          Include disabled
        </label>
        <Button size="sm" variant="outline" onClick={() => void refresh()}>
          Apply
        </Button>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Short URL</TableHead>
              <TableHead className="hidden md:table-cell">Target</TableHead>
              <TableHead className="text-right">Clicks</TableHead>
              <TableHead className="hidden lg:table-cell">Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows === null && (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                  <Loader2 className="mx-auto h-4 w-4 animate-spin" />
                </TableCell>
              </TableRow>
            )}
            {rows && rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                  No short URLs yet — click <strong>New short URL</strong> to make one.
                </TableCell>
              </TableRow>
            )}
            {rows?.map((row) => (
              <TableRow key={row.id}>
                <TableCell>
                  <div className="flex items-start gap-2">
                    <Link2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    <div className="min-w-0">
                      <p
                        className={cn(
                          "truncate font-mono text-sm",
                          row.is_active ? "text-foreground" : "text-muted-foreground line-through",
                        )}
                      >
                        /go/{row.slug}
                      </p>
                      {row.title && (
                        <p className="truncate text-xs text-muted-foreground">{row.title}</p>
                      )}
                      {!row.is_active && (
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-rose-600 dark:text-rose-300">
                          Disabled
                        </p>
                      )}
                    </div>
                  </div>
                </TableCell>
                <TableCell className="hidden md:table-cell">
                  <a
                    href={row.target_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex max-w-[28rem] items-center gap-1 truncate text-xs text-primary hover:underline"
                    title={row.target_url}
                  >
                    <span className="truncate">{row.target_url}</span>
                    <ExternalLink className="h-3 w-3 shrink-0" />
                  </a>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {row.click_count.toLocaleString()}
                </TableCell>
                <TableCell className="hidden whitespace-nowrap text-xs text-muted-foreground lg:table-cell">
                  {new Date(row.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void copy(row.slug)}
                      title="Copy short URL"
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void toggleActive(row)}
                      title={row.is_active ? "Disable" : "Enable"}
                    >
                      {row.is_active ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void remove(row)}
                      title="Delete"
                      className="text-rose-600 hover:text-rose-700 dark:text-rose-300 dark:hover:text-rose-200"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </AdminShell>
  );
}


// ---------------------------------------------------------------------------
// Create form
// ---------------------------------------------------------------------------


function CreateForm({
  onCancel,
  onCreated,
  onError,
}: {
  onCancel: () => void;
  onCreated: (created: ShortUrlRead) => void | Promise<void>;
  onError: (msg: string) => void;
}) {
  const [target, setTarget] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const body: Record<string, unknown> = { target_url: target.trim() };
      if (slug.trim()) body.slug = slug.trim();
      if (title.trim()) body.title = title.trim();
      const created = await adminApi.post<ShortUrlRead>(BASE, body);
      await onCreated(created);
    } catch (err) {
      onError((err as AdminApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="mb-4 rounded-xl border border-primary/30 bg-primary/[0.04] p-4"
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">New short URL</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Leave the slug blank to auto-generate a 7-character random code.
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onCancel}
          disabled={busy}
          title="Close"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="grid gap-3 md:grid-cols-[1fr_180px]">
        <div className="space-y-1.5">
          <Label htmlFor="target_url">Target URL</Label>
          <Input
            id="target_url"
            type="url"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="https://parisunitedgroup.com/offers/summer"
            required
            disabled={busy}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="slug">Custom slug (optional)</Label>
          <Input
            id="slug"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="summer-25"
            disabled={busy}
            pattern="[a-z0-9](?:[a-z0-9_-]{1,30}[a-z0-9])?"
            title="3-32 lowercase letters, digits, hyphen or underscore"
          />
        </div>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto]">
        <div className="space-y-1.5">
          <Label htmlFor="title">Internal title (optional)</Label>
          <Input
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Where this link is used — e.g. Lulu Eid mailer"
            disabled={busy}
          />
        </div>
        <div className="flex items-end">
          <Button type="submit" disabled={busy || !target.trim()}>
            {busy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Creating…
              </>
            ) : (
              <>
                <Link2 className="h-4 w-4" />
                Create
              </>
            )}
          </Button>
        </div>
      </div>
    </form>
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
    const t = setTimeout(onClose, 3500);
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
