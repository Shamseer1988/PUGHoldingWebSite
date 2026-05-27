"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Bookmark,
  CheckCircle2,
  Loader2,
  Pin,
  PinOff,
  Plus,
  Trash2,
  Users,
} from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { usePermission } from "@/components/auth/permission";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { hrApi, HrApiError } from "@/lib/hr/api";
import { ANY_CANDIDATE_VIEW } from "@/lib/hr/permissions";
import { cn } from "@/lib/utils";


// ---------------------------------------------------------------------------
// Types — local to this page (the saved-search API is not used elsewhere yet)
// ---------------------------------------------------------------------------

type SavedSearchScope = "private" | "team";

interface SavedSearch {
  id: number;
  owner_id: number | null;
  owner_email: string | null;
  owner_name: string | null;
  name: string;
  description: string | null;
  filters: Record<string, unknown>;
  scope: SavedSearchScope;
  pinned: boolean;
  last_run_at: string | null;
  last_result_count: number | null;
  created_at: string;
  updated_at: string;
  is_owner: boolean;
}

interface RunResult {
  saved_search_id: number;
  name: string;
  result_count: number;
  candidate_ids: number[];
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TalentPoolPage() {
  const { hasAny } = usePermission();
  const canView = hasAny(ANY_CANDIDATE_VIEW);
  if (!canView) {
    return (
      <HrShell title="Talent pool" description="Saved candidate searches.">
        <HrEmptyState
          icon={Bookmark}
          title="Not available"
          description="You don't have permission to view saved candidate searches."
        />
      </HrShell>
    );
  }
  return <Body />;
}

function Body() {
  const [rows, setRows] = React.useState<SavedSearch[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [running, setRunning] = React.useState<number | null>(null);
  const [lastResult, setLastResult] = React.useState<RunResult | null>(null);

  React.useEffect(() => {
    void refresh();
  }, []);

  async function refresh() {
    setError(null);
    try {
      const data = await hrApi.get<SavedSearch[]>("/hr/saved-searches");
      setRows(data);
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  async function togglePinned(row: SavedSearch) {
    try {
      await hrApi.patch(`/hr/saved-searches/${row.id}`, {
        pinned: !row.pinned,
      });
      await refresh();
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  async function runSearch(row: SavedSearch) {
    setRunning(row.id);
    setError(null);
    try {
      const result = await hrApi.post<RunResult>(
        `/hr/saved-searches/${row.id}/run`,
        undefined
      );
      setLastResult(result);
      setToast(`"${row.name}" matched ${result.result_count} candidate(s).`);
      await refresh();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setRunning(null);
    }
  }

  async function remove(row: SavedSearch) {
    if (!confirm(`Delete saved search "${row.name}"? This can't be undone.`)) {
      return;
    }
    try {
      await hrApi.delete(`/hr/saved-searches/${row.id}`);
      setToast(`Deleted "${row.name}".`);
      await refresh();
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  return (
    <HrShell
      title="Talent pool"
      description="Saved candidate searches — reuse a filter set across the team."
      actions={
        <Button onClick={() => setCreating(true)} size="sm">
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New saved search</span>
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

      {lastResult && (
        <div className="mb-4 flex items-center justify-between rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-200">
          <span>
            <strong>{lastResult.name}</strong> — matched{" "}
            <strong>{lastResult.result_count}</strong> candidate(s).
          </span>
          {lastResult.candidate_ids.length > 0 && (
            <Link
              href={`/hr/candidates?ids=${lastResult.candidate_ids.join(",")}`}
              className="inline-flex items-center gap-1 text-xs font-medium hover:underline"
            >
              View in candidates
              <ArrowRight className="h-3 w-3" />
            </Link>
          )}
        </div>
      )}

      {rows === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading saved searches…
        </p>
      ) : rows.length === 0 ? (
        <HrEmptyState
          icon={Bookmark}
          title="No saved searches yet"
          description="Save the filter set you use most often so you (and the team) can re-run it in one click."
          action={
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" />
              Create the first one
            </Button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead className="hidden md:table-cell">Owner</TableHead>
                <TableHead className="w-24">Scope</TableHead>
                <TableHead className="hidden lg:table-cell w-32">
                  Last run
                </TableHead>
                <TableHead className="w-44 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <div className="flex items-start gap-2">
                      <button
                        type="button"
                        onClick={() => row.is_owner && togglePinned(row)}
                        disabled={!row.is_owner}
                        aria-label={row.pinned ? "Unpin" : "Pin"}
                        className={cn(
                          "mt-0.5 inline-flex h-4 w-4 items-center justify-center",
                          row.pinned
                            ? "text-pug-gold-600"
                            : "text-muted-foreground hover:text-foreground",
                          !row.is_owner && "cursor-not-allowed opacity-30"
                        )}
                      >
                        {row.pinned ? (
                          <Pin className="h-4 w-4 fill-current" />
                        ) : (
                          <PinOff className="h-4 w-4" />
                        )}
                      </button>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium leading-tight">{row.name}</p>
                        {row.description && (
                          <p className="line-clamp-2 text-xs text-muted-foreground">
                            {row.description}
                          </p>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-xs">
                    {row.owner_name || row.owner_email || "—"}
                  </TableCell>
                  <TableCell>
                    <ScopeChip scope={row.scope} />
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-xs text-muted-foreground">
                    {row.last_run_at ? (
                      <>
                        {new Date(row.last_run_at).toLocaleDateString()} —{" "}
                        {row.last_result_count} match
                        {row.last_result_count === 1 ? "" : "es"}
                      </>
                    ) : (
                      <span>Never</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => runSearch(row)}
                        disabled={running === row.id}
                      >
                        {running === row.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Users className="h-3.5 w-3.5" />
                        )}
                        Run
                      </Button>
                      {row.is_owner && (
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => remove(row)}
                          aria-label={`Delete ${row.name}`}
                          className="text-rose-600 hover:text-rose-700"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {creating && (
        <CreateDialog
          onClose={() => setCreating(false)}
          onCreated={(name) => {
            setCreating(false);
            setToast(`Created "${name}".`);
            void refresh();
          }}
          onError={(msg) => setError(msg)}
        />
      )}
    </HrShell>
  );
}

// ---------------------------------------------------------------------------
// Create dialog
// ---------------------------------------------------------------------------

function CreateDialog({
  onClose,
  onCreated,
  onError,
}: {
  onClose: () => void;
  onCreated: (name: string) => void;
  onError: (msg: string) => void;
}) {
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [scope, setScope] = React.useState<SavedSearchScope>("private");
  const [filtersJson, setFiltersJson] = React.useState("{}");
  const [saving, setSaving] = React.useState(false);

  async function submit() {
    setSaving(true);
    let filters: Record<string, unknown> = {};
    try {
      filters = JSON.parse(filtersJson || "{}");
      if (typeof filters !== "object" || Array.isArray(filters)) {
        throw new Error("Filters must be a JSON object.");
      }
    } catch (err) {
      onError(
        `Filters JSON is invalid: ${(err as Error).message}. Use {} for an empty filter.`
      );
      setSaving(false);
      return;
    }
    try {
      await hrApi.post("/hr/saved-searches", {
        name: name.trim(),
        description: description.trim() || undefined,
        scope,
        filters,
        pinned: false,
      });
      onCreated(name.trim());
    } catch (err) {
      onError((err as HrApiError).message);
    } finally {
      setSaving(false);
    }
  }

  const canSubmit = name.trim().length > 0 && !saving;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-40 flex"
    >
      <div
        className="flex-1 bg-background/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) submit();
        }}
        className="flex w-full max-w-lg flex-col bg-background shadow-2xl"
      >
        <header className="border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">New saved search</h2>
        </header>
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <div className="space-y-1.5">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Senior backend engineers, GCC"
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What this saved search is for."
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="scope">Visibility</Label>
            <Select
              id="scope"
              value={scope}
              onChange={(e) => setScope(e.target.value as SavedSearchScope)}
              disabled={saving}
            >
              <option value="private">Private — only me</option>
              <option value="team">Team — anyone with candidate access</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="filters">Filters (JSON)</Label>
            <Textarea
              id="filters"
              rows={8}
              value={filtersJson}
              onChange={(e) => setFiltersJson(e.target.value)}
              disabled={saving}
              className="font-mono text-xs"
              placeholder={`{\n  "q": "python",\n  "experience_min": 5,\n  "department": "Engineering"\n}`}
            />
            <p className="text-[11px] text-muted-foreground">
              Same shape as the candidate-list filter panel. Supported
              keys: q, nationality, location, experience_min,
              experience_max, salary_min, salary_max, visa, notice_period,
              education, language, skill, job_slug, department, status,
              score_min, score_max, uploaded_from, uploaded_to.
            </p>
          </div>
        </div>
        <footer className="flex items-center justify-end gap-2 border-t border-border/60 bg-background px-5 py-3">
          <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" disabled={!canSubmit}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {saving ? "Saving…" : "Create"}
          </Button>
        </footer>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reusable bits
// ---------------------------------------------------------------------------

function ScopeChip({ scope }: { scope: SavedSearchScope }) {
  const tone =
    scope === "team"
      ? "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300"
      : "border-slate-500/30 bg-slate-500/10 text-slate-700 dark:text-slate-300";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        tone
      )}
    >
      {scope === "team" ? "Team" : "Private"}
    </span>
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
