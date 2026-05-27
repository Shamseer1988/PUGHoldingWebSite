"use client";

import * as React from "react";
import {
  CheckCircle2,
  ClipboardList,
  Loader2,
  Pencil,
  Plus,
  Star,
  Trash2,
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
import { PERM_HR_INTERVIEWS_SCHEDULE } from "@/lib/hr/permissions";
import { cn } from "@/lib/utils";


interface Dimension {
  key: string;
  label: string;
  description?: string | null;
  max_score: number;
  weight: number;
}

interface ScorecardTemplate {
  id: number;
  name: string;
  description: string | null;
  scope: "global" | "job";
  job_opening_id: number | null;
  job_title: string | null;
  dimensions: Dimension[];
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

const BASE = "/hr/scorecard-templates";

export default function ScorecardTemplatesPage() {
  const { has } = usePermission();
  const canManage = has(PERM_HR_INTERVIEWS_SCHEDULE);

  if (!canManage) {
    return (
      <HrShell
        title="Scorecard templates"
        description="Interview rubrics that interviewers score against."
      >
        <HrEmptyState
          icon={ClipboardList}
          title="Not available"
          description="You don't have permission to manage scorecard templates."
        />
      </HrShell>
    );
  }
  return <Body />;
}

function Body() {
  const [rows, setRows] = React.useState<ScorecardTemplate[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [creating, setCreating] = React.useState(false);
  // When non-null, the dialog opens in edit mode prefilled with this row.
  const [editing, setEditing] = React.useState<ScorecardTemplate | null>(null);
  const [includeInactive, setIncludeInactive] = React.useState(false);

  React.useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  async function refresh() {
    setError(null);
    try {
      const q = includeInactive ? "?include_inactive=true" : "";
      const data = await hrApi.get<ScorecardTemplate[]>(`${BASE}${q}`);
      setRows(data);
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  async function deactivate(row: ScorecardTemplate) {
    if (
      !confirm(
        `Archive "${row.name}"? Interviewers won't be able to pick it for new feedback. Existing submitted scorecards keep their reference.`
      )
    ) {
      return;
    }
    try {
      await hrApi.delete(`${BASE}/${row.id}`);
      setToast(`Archived "${row.name}".`);
      await refresh();
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  return (
    <HrShell
      title="Scorecard templates"
      description="Reusable interview rubrics — set the dimensions interviewers will score against."
      actions={
        <Button onClick={() => setCreating(true)} size="sm">
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New template</span>
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

      <label className="mb-4 inline-flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
          checked={includeInactive}
          onChange={(e) => setIncludeInactive(e.target.checked)}
        />
        Include archived templates
      </label>

      {rows === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading templates…
        </p>
      ) : rows.length === 0 ? (
        <HrEmptyState
          icon={ClipboardList}
          title="No scorecard templates yet"
          description="Create a rubric and interviewers will be able to score candidates against it."
          action={
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" />
              New template
            </Button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Template</TableHead>
                <TableHead className="hidden md:table-cell">Scope</TableHead>
                <TableHead className="w-20 text-right">Dimensions</TableHead>
                <TableHead className="w-24 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((t) => (
                <TableRow key={t.id}>
                  <TableCell>
                    <p className="flex items-center gap-1.5 font-medium leading-tight">
                      {t.name}
                      {t.is_default && (
                        <span
                          title="Default template"
                          className="inline-flex items-center gap-1 rounded-full border border-pug-gold-500/40 bg-pug-gold-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-pug-gold-700 dark:text-pug-gold-300"
                        >
                          <Star className="h-2.5 w-2.5 fill-current" />
                          Default
                        </span>
                      )}
                      {!t.is_active && (
                        <span className="rounded-full border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-rose-700 dark:text-rose-300">
                          Archived
                        </span>
                      )}
                    </p>
                    {t.description && (
                      <p className="line-clamp-2 text-xs text-muted-foreground">
                        {t.description}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-xs">
                    {t.scope === "global" ? (
                      <span>Global</span>
                    ) : (
                      <span>Job — {t.job_title || `#${t.job_opening_id}`}</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs">
                    {t.dimensions.length}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex items-center gap-1">
                      {t.is_active && (
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => setEditing(t)}
                          aria-label={`Edit ${t.name}`}
                          title="Edit"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      )}
                      {t.is_active && (
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => deactivate(t)}
                          className="text-rose-600 hover:text-rose-700"
                          aria-label={`Archive ${t.name}`}
                          title="Archive"
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

      {(creating || editing) && (
        <TemplateDialog
          editing={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={(name, mode) => {
            setCreating(false);
            setEditing(null);
            setToast(
              mode === "create" ? `Created "${name}".` : `Updated "${name}".`
            );
            void refresh();
          }}
          onError={setError}
        />
      )}
    </HrShell>
  );
}

// ---------------------------------------------------------------------------
// Create / Edit dialog
// ---------------------------------------------------------------------------

function TemplateDialog({
  editing,
  onClose,
  onSaved,
  onError,
}: {
  editing: ScorecardTemplate | null;
  onClose: () => void;
  onSaved: (name: string, mode: "create" | "edit") => void;
  onError: (msg: string) => void;
}) {
  const [name, setName] = React.useState(() => editing?.name ?? "");
  const [description, setDescription] = React.useState(
    () => editing?.description ?? ""
  );
  const [scope, setScope] = React.useState<"global" | "job">(
    () => editing?.scope ?? "global"
  );
  const [jobId, setJobId] = React.useState(() =>
    editing?.job_opening_id != null ? String(editing.job_opening_id) : ""
  );
  const [isDefault, setIsDefault] = React.useState(
    () => editing?.is_default ?? false
  );
  const [dimensions, setDimensions] = React.useState<Dimension[]>(() =>
    editing?.dimensions && editing.dimensions.length > 0
      ? editing.dimensions.map((d) => ({ ...d }))
      : [
          { key: "system_design", label: "System design", max_score: 5, weight: 40 },
          { key: "coding", label: "Coding", max_score: 5, weight: 40 },
          { key: "communication", label: "Communication", max_score: 5, weight: 20 },
        ]
  );
  const [saving, setSaving] = React.useState(false);

  const weightSum = dimensions.reduce((s, d) => s + (d.weight || 0), 0);
  const canSubmit =
    name.trim().length > 0 &&
    dimensions.length > 0 &&
    weightSum === 100 &&
    (scope !== "job" || jobId.trim().length > 0) &&
    !saving;

  function updateDim(i: number, patch: Partial<Dimension>) {
    setDimensions((prev) =>
      prev.map((d, idx) => (idx === i ? { ...d, ...patch } : d))
    );
  }

  function addDim() {
    setDimensions((prev) => [
      ...prev,
      { key: `dim_${prev.length + 1}`, label: "New dimension", max_score: 5, weight: 0 },
    ]);
  }

  function removeDim(i: number) {
    setDimensions((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function submit() {
    setSaving(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || undefined,
        scope,
        job_opening_id: scope === "job" ? Number(jobId) : null,
        dimensions,
        is_default: isDefault,
      };
      if (editing) {
        await hrApi.patch(`${BASE}/${editing.id}`, payload);
        onSaved(name.trim(), "edit");
      } else {
        await hrApi.post(BASE, { ...payload, is_active: true });
        onSaved(name.trim(), "create");
      }
    } catch (err) {
      onError((err as HrApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" className="fixed inset-0 z-40 flex">
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
        className="flex w-full max-w-2xl flex-col bg-background shadow-2xl"
      >
        <header className="border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">
            {editing ? `Edit "${editing.name}"` : "New scorecard template"}
          </h2>
        </header>
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <div className="space-y-1.5">
            <Label htmlFor="t-name">Name *</Label>
            <Input
              id="t-name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Backend engineer rubric"
              disabled={saving}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="t-desc">Description</Label>
            <Textarea
              id="t-desc"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={saving}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="t-scope">Scope</Label>
              <Select
                id="t-scope"
                value={scope}
                onChange={(e) => setScope(e.target.value as "global" | "job")}
                disabled={saving}
              >
                <option value="global">Global (any role)</option>
                <option value="job">Specific job opening</option>
              </Select>
            </div>
            {scope === "job" && (
              <div className="space-y-1.5">
                <Label htmlFor="t-jobid">Job opening ID *</Label>
                <Input
                  id="t-jobid"
                  type="number"
                  required
                  value={jobId}
                  onChange={(e) => setJobId(e.target.value)}
                  disabled={saving}
                />
              </div>
            )}
          </div>
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
              disabled={saving}
            />
            Mark as default template
          </label>

          <fieldset className="rounded-xl border border-border/60 p-3">
            <div className="mb-2 flex items-center justify-between">
              <legend className="text-sm font-medium">Dimensions</legend>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={addDim}
                disabled={saving}
              >
                <Plus className="h-3.5 w-3.5" />
                Add dimension
              </Button>
            </div>
            <div className="space-y-2">
              {dimensions.map((d, i) => (
                <div
                  key={i}
                  className="grid grid-cols-12 gap-2 rounded-md border border-border/60 p-2 text-sm"
                >
                  <Input
                    className="col-span-3 font-mono text-xs"
                    placeholder="key"
                    value={d.key}
                    onChange={(e) => updateDim(i, { key: e.target.value })}
                    disabled={saving}
                  />
                  <Input
                    className="col-span-4"
                    placeholder="Label"
                    value={d.label}
                    onChange={(e) => updateDim(i, { label: e.target.value })}
                    disabled={saving}
                  />
                  <Input
                    type="number"
                    className="col-span-2"
                    placeholder="Max"
                    value={d.max_score}
                    onChange={(e) =>
                      updateDim(i, { max_score: Number(e.target.value) })
                    }
                    disabled={saving}
                    min={1}
                    max={10}
                  />
                  <Input
                    type="number"
                    className="col-span-2"
                    placeholder="Weight"
                    value={d.weight}
                    onChange={(e) =>
                      updateDim(i, { weight: Number(e.target.value) })
                    }
                    disabled={saving}
                    min={0}
                    max={100}
                  />
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    onClick={() => removeDim(i)}
                    disabled={saving}
                    className="col-span-1 text-rose-600"
                    aria-label="Remove"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
            <p
              className={cn(
                "mt-2 text-[11px]",
                weightSum === 100
                  ? "text-emerald-700 dark:text-emerald-300"
                  : "text-rose-600"
              )}
            >
              Weights sum: {weightSum} / 100
            </p>
          </fieldset>
        </div>
        <footer className="flex items-center justify-end gap-2 border-t border-border/60 px-5 py-3">
          <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" disabled={!canSubmit}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {saving
              ? "Saving…"
              : editing
                ? "Save changes"
                : "Create template"}
          </Button>
        </footer>
      </form>
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
