"use client";

import * as React from "react";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Inbox,
  Loader2,
  RefreshCw,
  Search,
  Send,
} from "lucide-react";

import { AdminShell } from "@/components/admin/admin-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { adminApi, AdminApiError } from "@/lib/admin/api";
import type {
  ContactMessage,
  ContactMessageDetail,
  ContactReplyBubble,
} from "@/lib/admin/types";
import { cn } from "@/lib/utils";


type ListFilter = "all" | "new" | "replied" | "failed" | "closed";


export default function InboxAdminPage() {
  const [messages, setMessages] = React.useState<ContactMessage[] | null>(null);
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const [detail, setDetail] = React.useState<ContactMessageDetail | null>(null);
  const [replyBody, setReplyBody] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<string | null>(null);
  const [filter, setFilter] = React.useState<ListFilter>("all");
  const [query, setQuery] = React.useState("");
  const [retryingId, setRetryingId] = React.useState<number | null>(null);

  const includeArchived = filter === "closed";

  React.useEffect(() => {
    void refreshList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeArchived]);

  async function refreshList() {
    setMessages(null);
    try {
      const list = await adminApi.get<ContactMessage[]>(
        `/admin/cms/contact-messages?include_archived=${includeArchived}`
      );
      setMessages(list);
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function openMessage(message: ContactMessage) {
    setSelectedId(message.id);
    setDetail(null);
    setReplyBody("");
    try {
      const fresh = await adminApi.get<ContactMessageDetail>(
        `/admin/cms/contact-messages/${message.id}`
      );
      setDetail(fresh);
      if (!message.is_read) {
        const updated = await adminApi.patch<ContactMessage>(
          `/admin/cms/contact-messages/${message.id}/read`
        );
        setMessages((prev) =>
          prev ? prev.map((m) => (m.id === updated.id ? updated : m)) : prev
        );
      }
    } catch (err) {
      setError((err as AdminApiError).message);
    }
  }

  async function sendReply() {
    if (!detail || !replyBody.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await adminApi.post<ContactMessageDetail>(
        `/admin/cms/contact-messages/${detail.id}/reply`,
        { reply_body: replyBody }
      );
      setDetail(updated);
      const lastBubble = updated.replies[updated.replies.length - 1];
      if (lastBubble?.email_status === "sent") {
        setReplyBody("");
        setToast("Reply sent.");
      } else if (lastBubble?.email_status === "failed") {
        // Keep typed text in the box so the admin can edit and retry,
        // but also expose the failed bubble's Retry control.
        setToast(null);
        setError(
          lastBubble.error_message ??
            "Reply saved but could not be emailed. Retry from the failed bubble."
        );
      }
      await refreshList();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function retryReply(replyId: number) {
    if (!detail) return;
    setRetryingId(replyId);
    setError(null);
    try {
      const updated = await adminApi.post<ContactMessageDetail>(
        `/admin/cms/contact-replies/${replyId}/retry`
      );
      setDetail(updated);
      const bubble = updated.replies.find((r) => r.id === replyId);
      if (bubble?.email_status === "sent") {
        setToast("Reply re-sent successfully.");
      } else if (bubble?.email_status === "failed") {
        setError(bubble.error_message ?? "Retry failed.");
      }
      await refreshList();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setRetryingId(null);
    }
  }

  async function archiveSelected() {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      await adminApi.patch(`/admin/cms/contact-messages/${detail.id}/archive`);
      setToast("Archived.");
      setSelectedId(null);
      setDetail(null);
      await refreshList();
    } catch (err) {
      setError((err as AdminApiError).message);
    } finally {
      setBusy(false);
    }
  }

  // Filter + search applied client-side over the full list.
  const filteredMessages = React.useMemo(() => {
    if (!messages) return null;
    const q = query.trim().toLowerCase();
    return messages.filter((m) => {
      // Filter chip
      switch (filter) {
        case "new":
          if (m.is_read || m.is_replied) return false;
          break;
        case "replied":
          if (!m.is_replied) return false;
          break;
        case "closed":
          if (!m.is_archived) return false;
          break;
        case "failed":
          // Per-list metadata doesn't carry reply status; surface
          // anything read-but-not-replied as a candidate. Detail view
          // shows the real per-reply status.
          if (m.is_replied || !m.is_read) return false;
          break;
      }
      if (!q) return true;
      const haystack = [
        m.name,
        m.email,
        m.phone ?? "",
        m.subject ?? "",
        m.message,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [messages, filter, query]);

  const unreadCount = React.useMemo(
    () => (messages ?? []).filter((m) => !m.is_read).length,
    [messages]
  );

  return (
    <AdminShell
      title="Contact inbox"
      description="Visitor enquiries submitted via the public Contact Us form. Replies are sent via email through the configured SMTP server."
      actions={
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <Badge variant="default" className="hidden sm:inline-flex">
              {unreadCount} unread
            </Badge>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={refreshList}
            disabled={messages === null}
          >
            <RefreshCw className="h-4 w-4" />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
        </div>
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

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <Card className="flex max-h-[78vh] flex-col overflow-hidden">
          <div className="space-y-3 border-b border-border/60 p-3">
            <div className="relative">
              <Search
                aria-hidden
                className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search name, email, subject…"
                className="pl-8"
              />
            </div>
            <div className="flex flex-wrap gap-1.5">
              {(
                [
                  ["all", "All"],
                  ["new", "New"],
                  ["replied", "Replied"],
                  ["failed", "Failed reply"],
                  ["closed", "Closed"],
                ] as [ListFilter, string][]
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setFilter(key)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                    filter === key
                      ? "border-primary/60 bg-primary/15 text-primary"
                      : "border-border/60 bg-background/40 text-muted-foreground hover:bg-muted/60"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {filteredMessages === null ? (
              <p className="p-6 text-sm text-muted-foreground">
                <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />
                Loading…
              </p>
            ) : filteredMessages.length === 0 ? (
              <EmptyState
                className="m-2 border-none p-8"
                icon={Inbox}
                title={
                  query
                    ? "No messages match your search"
                    : filter === "all"
                      ? "Inbox empty"
                      : `No ${filter} messages`
                }
                description="Submissions from the public contact form will land here."
              />
            ) : (
              <ul className="divide-y divide-border/60">
                {filteredMessages.map((m) => (
                  <li key={m.id}>
                    <button
                      type="button"
                      onClick={() => openMessage(m)}
                      className={cn(
                        "w-full px-4 py-3 text-left transition-colors hover:bg-muted/50",
                        selectedId === m.id && "bg-primary/10"
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
          </div>
        </Card>

        <Card className="flex max-h-[78vh] flex-col overflow-hidden">
          {!detail ? (
            <EmptyState
              className="m-2 border-none p-12"
              icon={Inbox}
              title={selectedId ? "Loading…" : "Pick a message"}
              description="Select a conversation from the list to read and reply."
            />
          ) : (
            <>
              <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border/60 p-5">
                <div className="min-w-0">
                  <h2 className="text-base font-semibold">
                    {detail.subject ?? "(no subject)"}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    <span className="font-medium">{detail.name}</span>{" "}
                    &lt;{detail.email}&gt;
                    {detail.department && ` · ${detail.department}`}
                    {detail.phone && ` · ${detail.phone}`}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Received {new Date(detail.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={archiveSelected}
                    disabled={busy}
                  >
                    <Archive className="h-4 w-4" />
                    Archive
                  </Button>
                </div>
              </header>

              {/* Chat thread — scrollable */}
              <div className="flex-1 overflow-y-auto bg-muted/20 px-4 py-5">
                <div className="mx-auto flex max-w-2xl flex-col gap-4">
                  {detail.replies.map((bubble, idx) => (
                    <ChatBubble
                      key={`${bubble.id}-${idx}`}
                      bubble={bubble}
                      onRetry={
                        bubble.direction === "outbound" &&
                        bubble.email_status === "failed"
                          ? () => retryReply(bubble.id)
                          : undefined
                      }
                      retrying={retryingId === bubble.id}
                    />
                  ))}
                </div>
              </div>

              {/* Composer */}
              <div className="border-t border-border/60 bg-background/80 p-4">
                <Textarea
                  rows={3}
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                  placeholder="Write a reply… (plain text, line breaks preserved)"
                  disabled={busy}
                />
                <div className="mt-2 flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">
                    Sent to <span className="font-medium">{detail.email}</span>{" "}
                    from the configured SMTP sender.
                  </p>
                  <Button
                    onClick={sendReply}
                    disabled={busy || !replyBody.trim()}
                  >
                    {busy ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                    Send reply
                  </Button>
                </div>
              </div>
            </>
          )}
        </Card>
      </div>
    </AdminShell>
  );
}


// ---------------------------------------------------------------------------
// Chat bubble — inbound on the left, outbound on the right.
// ---------------------------------------------------------------------------


function ChatBubble({
  bubble,
  onRetry,
  retrying,
}: {
  bubble: ContactReplyBubble;
  onRetry?: () => void;
  retrying: boolean;
}) {
  const outbound = bubble.direction === "outbound";
  const failed = bubble.email_status === "failed";
  return (
    <div
      className={cn(
        "flex max-w-full",
        outbound ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-2xl border px-4 py-3 shadow-sm",
          outbound
            ? "bg-primary/10 border-primary/30 text-foreground"
            : "bg-background border-border/70 text-foreground",
          failed && "border-rose-500/50 ring-1 ring-rose-500/30"
        )}
      >
        <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          <span>
            {outbound
              ? bubble.sender_name ?? "Admin"
              : bubble.sender_name ?? "Visitor"}
          </span>
          {bubble.sender_email && (
            <span className="font-normal normal-case lowercase text-muted-foreground/80">
              &lt;{bubble.sender_email}&gt;
            </span>
          )}
        </div>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {bubble.body}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          <span>{new Date(bubble.created_at).toLocaleString()}</span>
          {outbound && <StatusPill status={bubble.email_status} />}
          {failed && onRetry && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onRetry}
              disabled={retrying}
              className="h-7 px-2 text-[11px]"
            >
              {retrying ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <RefreshCw className="h-3 w-3" />
              )}
              Retry send
            </Button>
          )}
        </div>
        {failed && bubble.error_message && (
          <p className="mt-2 rounded-md bg-rose-500/10 px-2 py-1 text-[11px] text-rose-700 dark:text-rose-200">
            {bubble.error_message}
          </p>
        )}
      </div>
    </div>
  );
}


function StatusPill({ status }: { status: ContactReplyBubble["email_status"] }) {
  if (status === "sent") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-200">
        <CheckCircle2 className="h-3 w-3" />
        Sent
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/40 bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-medium text-rose-700 dark:text-rose-200">
        <AlertTriangle className="h-3 w-3" />
        Failed
      </span>
    );
  }
  if (status === "pending") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-200">
        <Loader2 className="h-3 w-3 animate-spin" />
        Pending
      </span>
    );
  }
  return null;
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
