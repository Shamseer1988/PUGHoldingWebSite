"use client";

import * as React from "react";
import { Download, Loader2, Mail, Trash2 } from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import type { NewsletterSubscriber } from "@/lib/admin/types";

export default function SubscribersAdminPage() {
  const [items, setItems] = React.useState<NewsletterSubscriber[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => { refresh(); }, []);

  async function refresh() {
    setItems(null);
    try {
      setItems(await adminApi.get<NewsletterSubscriber[]>("/admin/cms/newsletter-subscribers"));
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function remove(id: number, email: string) {
    if (!confirm(`Remove ${email} from the newsletter list?`)) return;
    try {
      await adminApi.delete(`/admin/cms/newsletter-subscribers/${id}`);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  function exportCsv() {
    if (!items || items.length === 0) return;
    const header = "email,is_active,created_at\n";
    const rows = items
      .map(
        (s) =>
          `"${s.email.replace(/"/g, '""')}",${s.is_active},${s.created_at}`
      )
      .join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pug-subscribers-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <AdminShell
      title="Newsletter subscribers"
      description="Emails captured via the public newsletter form."
      actions={
        <Button
          variant="outline"
          size="sm"
          onClick={exportCsv}
          disabled={!items || items.length === 0}
        >
          <Download className="h-4 w-4" />
          Export CSV
        </Button>
      }
    >
      {error && (
        <div role="alert" className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">
          {error}
        </div>
      )}

      {items === null ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
          Loading…
        </p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={Mail}
          title="No subscribers yet"
          description="Once the public newsletter form is wired up (Phase 6) emails will appear here."
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead className="w-32">Status</TableHead>
                <TableHead className="w-44">Subscribed</TableHead>
                <TableHead className="w-20 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.email}</TableCell>
                  <TableCell>
                    {s.is_active ? <Badge variant="success">Active</Badge> : <Badge variant="muted">Inactive</Badge>}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(s.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => remove(s.id, s.email)}
                      aria-label={`Remove ${s.email}`}
                      className="text-rose-600 hover:text-rose-700"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
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
