"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, Send, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  askPugAi,
  PublicApiError,
  type AskPugAiTurn,
} from "@/lib/public-api-client";
import { cn } from "@/lib/utils";

const SESSION_KEY = "pug.ask.session_id";
const SUGGESTED_QUESTIONS = [
  "What companies are in Paris United Group?",
  "Do you have any open jobs right now?",
  "How can I contact your team?",
  "What's the latest news from the group?",
];

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  was_fallback?: boolean;
  mode?: string;
}

function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function loadSessionId(): string {
  if (typeof window === "undefined") return newId();
  try {
    const existing = window.localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const fresh = newId();
    window.localStorage.setItem(SESSION_KEY, fresh);
    return fresh;
  } catch {
    return newId();
  }
}

export function AskPugAiButton() {
  const [open, setOpen] = React.useState(false);
  const [messages, setMessages] = React.useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I'm the Paris United Group assistant. Ask me about our group companies, leadership, open jobs, news, or how to get in touch.",
    },
  ]);
  const [input, setInput] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const sessionIdRef = React.useRef<string>("");
  const scrollerRef = React.useRef<HTMLDivElement | null>(null);
  const inputRef = React.useRef<HTMLTextAreaElement | null>(null);

  React.useEffect(() => {
    sessionIdRef.current = loadSessionId();
  }, []);

  React.useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    // focus the input after the dialog mounts
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 120);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
      window.clearTimeout(focusTimer);
    };
  }, [open]);

  React.useEffect(() => {
    if (!scrollerRef.current) return;
    scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
  }, [messages, busy, open]);

  async function send(rawText: string) {
    const text = rawText.trim();
    if (!text || busy) return;

    const userMsg: ChatMessage = {
      id: newId(),
      role: "user",
      content: text,
    };

    // Build history from prior real turns (drop the welcome bubble) — keep
    // the last 8 turns so the backend isn't overwhelmed.
    const history: AskPugAiTurn[] = messages
      .filter((m) => m.id !== "welcome" && m.role !== "system")
      .slice(-8)
      .map((m) => ({
        role: m.role === "assistant" ? "assistant" : "user",
        content: m.content,
      }));

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setBusy(true);

    try {
      const result = await askPugAi({
        question: text,
        session_id: sessionIdRef.current || null,
        history,
      });
      if (result.session_id) {
        sessionIdRef.current = result.session_id;
        try {
          window.localStorage.setItem(SESSION_KEY, result.session_id);
        } catch {
          /* ignore quota */
        }
      }
      const assistantMsg: ChatMessage = {
        id: newId(),
        role: "assistant",
        content: result.answer,
        was_fallback: result.was_fallback,
        mode: result.mode,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const detail =
        err instanceof PublicApiError
          ? err.message
          : "Sorry, something went wrong. Please try again later or contact us directly.";
      setMessages((prev) => [
        ...prev,
        { id: newId(), role: "system", content: detail },
      ]);
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    void send(input);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(input);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open Ask PUG AI assistant"
        className={cn(
          "group fixed bottom-5 right-5 z-30 inline-flex items-center gap-2 rounded-full",
          "bg-gradient-to-r from-pug-green-700 via-pug-green-600 to-pug-gold-500 px-4 py-3",
          "text-sm font-medium text-white shadow-lg shadow-pug-green-900/30",
          "transition-transform hover:scale-[1.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pug-gold-400 focus-visible:ring-offset-2"
        )}
      >
        <span className="relative inline-flex h-6 w-6 items-center justify-center">
          <Bot className="h-5 w-5" />
          <span className="absolute -right-0.5 -top-0.5 inline-flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-pug-gold-300 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-pug-gold-300" />
          </span>
        </span>
        <span className="hidden sm:inline">Ask PUG AI</span>
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setOpen(false)}
              className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm"
              aria-hidden
            />
            <motion.div
              key="dialog"
              initial={{ opacity: 0, y: 24, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.98 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              role="dialog"
              aria-modal="true"
              aria-labelledby="ask-pug-ai-title"
              className="fixed inset-x-0 bottom-0 z-50 mx-auto w-full max-w-md p-3 sm:bottom-24 sm:right-5 sm:left-auto sm:p-0"
            >
              <div className="glass-card flex h-[min(70vh,560px)] flex-col overflow-hidden">
                <header className="flex items-start justify-between gap-3 border-b border-border/60 p-4">
                  <div>
                    <div className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      <Sparkles className="h-3.5 w-3.5 text-pug-gold-500" />
                      Paris United Group
                    </div>
                    <h2
                      id="ask-pug-ai-title"
                      className="mt-1 text-lg font-semibold"
                    >
                      Ask PUG AI
                    </h2>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setOpen(false)}
                    aria-label="Close Ask PUG AI"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </header>

                <div
                  ref={scrollerRef}
                  className="flex-1 space-y-3 overflow-y-auto p-4 text-sm"
                >
                  {messages.map((m) => (
                    <MessageBubble key={m.id} message={m} />
                  ))}
                  {busy && <TypingIndicator />}
                  {!busy && messages.length <= 1 && (
                    <div className="pt-2">
                      <p className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">
                        Try asking
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {SUGGESTED_QUESTIONS.map((q) => (
                          <button
                            key={q}
                            type="button"
                            onClick={() => void send(q)}
                            className="rounded-full border border-border/60 bg-background/40 px-3 py-1.5 text-xs text-foreground/80 transition hover:border-pug-gold-400/60 hover:text-foreground"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <form
                  onSubmit={handleSubmit}
                  className="border-t border-border/60 p-3"
                >
                  <div className="flex items-end gap-2 rounded-2xl border border-border/60 bg-background/60 p-2 focus-within:border-pug-gold-400/60">
                    <textarea
                      ref={inputRef}
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      rows={1}
                      maxLength={2000}
                      placeholder="Ask about companies, jobs, news…"
                      disabled={busy}
                      aria-label="Type your question"
                      className="max-h-32 min-h-[2.25rem] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none disabled:opacity-60"
                    />
                    <Button
                      type="submit"
                      size="icon"
                      disabled={busy || !input.trim()}
                      aria-label="Send message"
                      className="h-9 w-9 shrink-0 rounded-full bg-pug-green-600 text-white hover:bg-pug-green-700"
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  </div>
                  <p className="mt-2 px-1 text-[0.65rem] text-muted-foreground">
                    Answers are AI-generated from public information only.
                    Never share private or sensitive details here.
                  </p>
                </form>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "system") {
    return (
      <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-200">
        {message.content}
      </div>
    );
  }

  const isUser = message.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
          isUser
            ? "bg-pug-green-700 text-white rounded-br-md"
            : "bg-background/70 border border-border/60 text-foreground rounded-bl-md"
        )}
      >
        {message.content}
        {!isUser && message.was_fallback && (
          <p className="mt-1.5 text-[0.65rem] uppercase tracking-wider text-amber-600 dark:text-amber-300">
            AI offline — fallback response
          </p>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="inline-flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-border/60 bg-background/70 px-3 py-2.5">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-pug-green-500" />
        <span
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-pug-green-500"
          style={{ animationDelay: "0.15s" }}
        />
        <span
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-pug-green-500"
          style={{ animationDelay: "0.3s" }}
        />
      </div>
    </div>
  );
}
