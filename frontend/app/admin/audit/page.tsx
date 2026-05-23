"use client";

import * as React from "react";
import { History, Loader2 } from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import type { AuditEntry } from "@/lib/admin/types";

export default function AuditLogAdminPage() {
  const [items, setItems] = React.useState<AuditEntry[] | null>(null);
  const [scope, setScope] = React.useState("");
  const [actionPrefix, setActionPrefix] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => { refresh(); }, []);

  async function refresh() {
    setItems(null);
    const params = new URLSearchParams();
    if (scope) params.set("scope", scope);
    if (actionPrefix) params.set("action_prefix", actionPrefix);
    try {
      setItems(await adminApi.get<AuditEntry[]>(
        `/admin/cms/audit-logs${params.toString() ? `?${params}` : ""}`
      ));
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  return (
    <AdminShell
      title="Audit log"
      description="Every sensitive action (logins, CRUD, replies) writes here."
    >
      {error && (
        <div role="alert" className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">
          {error}
        </div>
      )}

      <form
        onSubmit={(e) => { e.preventDefault(); refresh(); }}
        className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border/60 bg-background/60 p-4 backdrop-blur"
      >
        <div className="space-y-1.5">
          <Label htmlFor="scope">Scope</Label>
          <Select
            id="scope"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            className="w-40"
          >
            <option value="">All</option>
            <option value="website">Website</option>
            <option value="hr">HR</option>
            <option value="system">System</option>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="action">Action prefix</Label>
          <Input
            id="action"
            placeholder="auth. or cms."
            value={actionPrefix}
            onChange={(e) => setActionPrefix(e.target.value)}
            className="w-56"
          />
        </div>
        <button
          type="submit"
          className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Apply filters
        </button>
      </form>

      {items === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading…
        </p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={History}
          title="No matching entries"
          description="Try widening the filters above."
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-44">When</TableHead>
                <TableHead className="w-24">Scope</TableHead>
                <TableHead>Action</TableHead>
                <TableHead className="hidden md:table-cell">Actor</TableHead>
                <TableHead className="hidden lg:table-cell">Target</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="text-xs text-muted-foreground">
                    {row.created_at ? new Date(row.created_at).toLocaleString() : "—"}
                  </TableCell>
                  <TableCell>
                    {row.scope ? <Badge variant="muted">{row.scope}</Badge> : "—"}
                  </TableCell>
                  <TableCell className="font-medium">{row.action}</TableCell>
                  <TableCell className="hidden md:table-cell">
                    {row.actor_email ?? <span className="text-muted-foreground">—</span>}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-muted-foreground">
                    {row.target_type ? `${row.target_type}#${row.target_id ?? "?"}` : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </AdminShell>
  );
}
