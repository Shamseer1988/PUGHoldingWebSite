"use client";

import * as React from "react";
import { FileText, Loader2, Plus, Star, Trash2, X } from "lucide-react";

import { usePermission } from "@/components/auth/permission";
import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { hrApi, HrApiError } from "@/lib/hr/api";
import { PERM_HR_OFFERS_CREATE, PERM_HR_OFFERS_DELETE } from "@/lib/hr/permissions";
import type { OfferLetterTemplate, OfferMergeField } from "@/lib/hr/types";

export default function HrOfferTemplatesPage() {
  const perms = usePermission();
  const canManage = perms.has(PERM_HR_OFFERS_CREATE);
  const canDelete = perms.has(PERM_HR_OFFERS_DELETE);

  const [templates, setTemplates] = React.useState<OfferLetterTemplate[] | null>(
    null,
  );
  const [tokens, setTokens] = React.useState<OfferMergeField[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [editing, setEditing] = React.useState<
    OfferLetterTemplate | "new" | null
  >(null);

  const refresh = React.useCallback(async () => {
    setTemplates(null);
    setError(null);
    try {
      setTemplates(await hrApi.get<OfferLetterTemplate[]>("/hr/offer-templates"));
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
    hrApi
      .get<OfferMergeField[]>("/hr/offer-templates/tokens")
      .then(setTokens)
      .catch(() => setTokens([]));
  }, [refresh]);

  return (
    <HrShell
      title="Offer-letter templates"
      description="Reusable letter bodies with merge fields — picked when issuing an offer."
      actions={
        canManage ? (
          <Button size="sm" onClick={() => setEditing("new")}>
            <Plus className="h-4 w-4" />
            New template
          </Button>
        ) : undefined
      }
    >
      {error && (
        <div
          role="alert"
          className="mb-3 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      {templates === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
          Loading templates…
        </p>
      ) : templates.length === 0 ? (
        <HrEmptyState
          icon={FileText}
          title="No offer-letter templates yet"
          description="Create a template with merge fields like {{candidate_name}} and {{salary}}; HR picks one when issuing an offer."
          action={
            canManage ? (
              <Button size="sm" onClick={() => setEditing("new")}>
                <Plus className="h-4 w-4" />
                New template
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {templates.map((t) => (
            <div
              key={t.id}
              className="flex flex-col rounded-xl border border-border/60 bg-card p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="flex items-center gap-1.5 font-medium">
                    {t.name}
                    {t.is_default && (
                      <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                    )}
                  </p>
                  {t.description && (
                    <p className="text-xs text-muted-foreground">
                      {t.description}
                    </p>
                  )}
                </div>
                {!t.is_active && <Badge variant="muted">Inactive</Badge>}
              </div>
              <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-xs text-muted-foreground">
                {t.body}
              </p>
              {canManage && (
                <div className="mt-3 flex items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setEditing(t)}
                  >
                    Edit
                  </Button>
                  {canDelete && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        try {
                          await hrApi.delete(`/hr/offer-templates/${t.id}`);
                          void refresh();
                        } catch (err) {
                          setError((err as HrApiError).message);
                        }
                      }}
                      aria-label={`Delete ${t.name}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {editing && (
        <TemplateEditor
          template={editing === "new" ? null : editing}
          tokens={tokens}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void refresh();
          }}
        />
      )}
    </HrShell>
  );
}

function TemplateEditor({
  template,
  tokens,
  onClose,
  onSaved,
}: {
  template: OfferLetterTemplate | null;
  tokens: OfferMergeField[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = React.useState(template?.name ?? "");
  const [description, setDescription] = React.useState(
    template?.description ?? "",
  );
  const [body, setBody] = React.useState(template?.body ?? "");
  const [isDefault, setIsDefault] = React.useState(template?.is_default ?? false);
  const [isActive, setIsActive] = React.useState(template?.is_active ?? true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const bodyRef = React.useRef<HTMLTextAreaElement>(null);

  function insertToken(token: string) {
    const snippet = `{{${token}}}`;
    const el = bodyRef.current;
    if (!el) {
      setBody((b) => b + snippet);
      return;
    }
    const start = el.selectionStart ?? body.length;
    const end = el.selectionEnd ?? body.length;
    const next = body.slice(0, start) + snippet + body.slice(end);
    setBody(next);
    // Restore caret after the inserted token on the next tick.
    requestAnimationFrame(() => {
      el.focus();
      const caret = start + snippet.length;
      el.setSelectionRange(caret, caret);
    });
  }

  async function save() {
    if (!name.trim()) {
      setError("Template name is required.");
      return;
    }
    if (!body.trim()) {
      setError("Template body is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || null,
        body,
        is_default: isDefault,
        is_active: isActive,
      };
      if (template) {
        await hrApi.patch(`/hr/offer-templates/${template.id}`, payload);
      } else {
        await hrApi.post("/hr/offer-templates", payload);
      }
      onSaved();
    } catch (err) {
      setError((err as HrApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={template ? "Edit template" : "New template"}
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 p-4 backdrop-blur-sm"
    >
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-border/60 bg-background shadow-2xl">
        <header className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <h2 className="text-base font-semibold">
            {template ? "Edit template" : "New template"}
          </h2>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="flex-1 space-y-3 overflow-y-auto p-5">
          <div className="space-y-1">
            <Label htmlFor="t-name">Name</Label>
            <Input
              id="t-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Standard offer (full-time)"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="t-desc">Description (optional)</Label>
            <Input
              id="t-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label>Insert a merge field</Label>
            <div className="flex flex-wrap gap-1.5">
              {tokens.map((tk) => (
                <button
                  key={tk.token}
                  type="button"
                  onClick={() => insertToken(tk.token)}
                  title={tk.label}
                  className="rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 font-mono text-[11px] text-muted-foreground hover:border-primary/60 hover:text-foreground"
                >
                  {`{{${tk.token}}}`}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="t-body">Letter body</Label>
            <Textarea
              id="t-body"
              ref={bodyRef}
              rows={10}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={
                "Dear {{candidate_name}},\n\nWe are pleased to offer you the role of {{position}} at {{company}}…"
              }
              className="font-mono text-sm"
            />
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
                className="h-4 w-4 accent-primary"
              />
              Default template
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="h-4 w-4 accent-primary"
              />
              Active
            </label>
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-md border border-rose-500/30 bg-rose-500/10 p-2 text-sm text-rose-700 dark:text-rose-200"
            >
              {error}
            </p>
          )}
        </div>

        <footer className="flex justify-end gap-2 border-t border-border/60 px-5 py-3">
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={save} disabled={busy}>
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save template
          </Button>
        </footer>
      </div>
    </div>
  );
}
