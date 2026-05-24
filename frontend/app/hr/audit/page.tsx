"use client";

import * as React from "react";
import { History, Loader2 } from "lucide-react";

import { HrEmptyState } from "@/components/hr/empty-state";
import { HrShell } from "@/components/hr/hr-shell";
import { Badge } from "@/components/ui/badge";
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
import { hrApi, HrApiError } from "@/lib/hr/api";
import type { HrAuditEntry } from "@/lib/hr/types";

export default function HrAuditPage() {
  const [items, setItems] = React.useState<HrAuditEntry[] | null>(null);
  const [actionPrefix, setActionPrefix] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setItems(null);
    const params = new URLSearchParams();
    if (actionPrefix) params.set("action_prefix", actionPrefix);
    try {
      setItems(
        await hrApi.get<HrAuditEntry[]>(
          `/hr/audit-logs${params.toString() ? `?${params}` : ""}`
        )
      );
    } catch (err) {
      setError((err as HrApiError).message);
    }
  }

  return (
    <HrShell
      title="HR audit log"
      description="Every HR action (logins, CRUD, status changes, scoring overrides, AI reviews, exports) writes here."
    >
      {error && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
        >
          {error}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          refresh();
        }}
        className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-border/60 bg-background/60 p-4 backdrop-blur"
      >
        <div className="space-y-1.5">
          <Label htmlFor="action">Action prefix</Label>
          <Input
            id="action"
            placeholder="auth. or hr."
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
        <HrEmptyState
          icon={History}
          title="No HR audit entries yet"
          description="As HR users sign in, manage candidates, and update statuses, their actions will be recorded here under scope=hr."
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-44">When</TableHead>
                <TableHead>Action</TableHead>
                <TableHead className="hidden md:table-cell">Actor</TableHead>
                <TableHead className="hidden lg:table-cell">Target</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="text-xs text-muted-foreground">
                    {row.created_at
                      ? new Date(row.created_at).toLocaleString()
                      : "—"}
                  </TableCell>
                  <TableCell className="font-medium">
                    <Badge variant="muted" className="font-mono text-[11px]">
                      {row.action}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {row.actor_email ?? (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell text-muted-foreground">
                    {row.target_type
                      ? `${row.target_type}#${row.target_id ?? "?"}`
                      : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </HrShell>
  );
}
