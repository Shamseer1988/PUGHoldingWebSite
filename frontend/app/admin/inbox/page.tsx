"use client";

import * as React from "react";
import {
  Archive,
  CheckCircle2,
  Inbox,
  Loader2,
  Reply,
  Send,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import type { ContactMessage } from "@/lib/admin/types";
import { cn } from "@/lib/utils";

export default function InboxAdminPage() {
  const [messages, setMessages] = React.useState<ContactMessage[] | null>(null);
  const [selected, setSelected] = React.useState<ContactMessage | null>(null);
  const [replyBody, setReplyBody] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [showArchived, setShowArchived] = React.useState(false);

  React.useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showArchived]);

  async function refresh() {
    setMessages(null);
    try {
      const list = await adminApi.get<ContactMessage[]>(
        `/admin/cms/contact-messages?include_archived=${showArchived}`
      );
      setMessages(list);
      if (selected) {
        const next = list.find((m) => m.id === selected.id);
        setSelected(next ?? null);
      }
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function open(message: ContactMessage) {
    setSelected(message);
    setReplyBody(message.reply_body ?? "");
    if (!message.is_read) {
      try {
        const updated = await adminApi.patch<ContactMessage>(
          `/admin/cms/contact-messages/${message.id}/read`
        );
        setMessages((prev) =>
          prev ? prev.map((m) => (m.id === updated.id ? updated : m)) : prev
        );
      } catch (err) {
        setError((err as AdminApiError).message);
      }
    }
  }

  async function reply() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await adminApi.post<ContactMessage>(
        `/admin/cms/contact-messages/${selected.id}/reply`,
        { reply_body: replyBody }
      );
      setSelected(updated);
      setToast("Reply saved.");
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await adminApi.patch(`/admin/cms/contact-messages/${selected.id}/archive`);
      setToast("Archived.");
      setSelected(null);
      await refresh();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdminShell
      title="Contact inbox"
      description="Messages submitted via the public Contact Us form."
      actions={
        <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
            checked={showArchived}
            onChange={(e) => setShowArchived(e.target.checked)}
          />
          Include archived
        </label>
      }
    >
      <Toast message={toast} onClose={() => setToast(null)} />
      {error && (
        <div role="alert" className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <Card className="overflow-hidden">
          {messages === null ? (
            <p className="p-6 text-sm text-muted-foreground">
              <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
              Loading…
            </p>
          ) : messages.length === 0 ? (
            <EmptyState
              className="m-2 border-none p-8"
              icon={Inbox}
              title="Inbox empty"
              description="Submissions from the public contact form will land here."
            />
          ) : (
            <ul className="max-h-[70vh] divide-y divide-border/60 overflow-y-auto">
              {messages.map((m) => (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => open(m)}
                    className={cn(
                      "w-full px-4 py-3 text-left transition-colors hover:bg-muted/50",
                      selected?.id === m.id && "bg-primary/10"
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-medium">{m.name}</span>
                      {m.is_replied ? (
                        <Badge variant="success">Replied</Badge>
                      ) : m.is_read ? (
                        <Badge variant="muted">Read</Badge>
                      ) : (
                        <Badge variant="default">New</Badge>
                      )}
                    </div>
                    <p className="truncate text-sm text-muted-foreground">
                      {m.subject ?? m.email}
                    </p>
                    <p className="mt-1 truncate text-xs text-muted-foreground">
                      {new Date(m.created_at).toLocaleString()}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="overflow-hidden">
          {selected ? (
            <article className="p-5">
              <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border/60 pb-4">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold">{selected.subject ?? "(no subject)"}</h2>
                  <p className="text-sm text-muted-foreground">
                    <span className="font-medium">{selected.name}</span>{" "}
                    &lt;{selected.email}&gt;
                    {selected.department && ` · ${selected.department}`}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {new Date(selected.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={archive} disabled={busy}>
                    <Archive className="h-4 w-4" />
                    Archive
                  </Button>
                </div>
              </header>

              <p className="mt-4 whitespace-pre-wrap text-sm leading-relaxed">
                {selected.message}
              </p>

              <section className="mt-6 border-t border-border/60 pt-4">
                <h3 className="inline-flex items-center gap-2 text-sm font-semibold">
                  <Reply className="h-4 w-4" />
                  Reply
                </h3>
                <Textarea
                  rows={5}
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                  placeholder="Write a reply…"
                  disabled={busy}
                  className="mt-2"
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  The reply is stored against the message and audit-logged.
                  Outbound email is sent only when SMTP credentials are
                  configured under Site settings.
                </p>
                <div className="mt-3 flex justify-end">
                  <Button onClick={reply} disabled={busy || !replyBody.trim()}>
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    Save reply
                  </Button>
                </div>
                {selected.is_replied && selected.replied_at && (
                  <p className="mt-2 text-xs text-emerald-700 dark:text-emerald-300">
                    Last replied {new Date(selected.replied_at).toLocaleString()}.
                  </p>
                )}
              </section>
            </article>
          ) : (
            <EmptyState
              className="m-2 border-none p-12"
              icon={Inbox}
              title="Pick a message"
              description="Select a conversation from the list to read and reply."
            />
          )}
        </Card>
      </div>
    </AdminShell>
  );
}

function Toast({ message, onClose }: { message: string | null; onClose: () => void }) {
  React.useEffect(() => {
    if (!message) return;
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [message, onClose]);
  if (!message) return null;
  return (
    <div role="status" className="mb-4 inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-200">
      <CheckCircle2 className="h-4 w-4" />
      {message}
    </div>
  );
}
