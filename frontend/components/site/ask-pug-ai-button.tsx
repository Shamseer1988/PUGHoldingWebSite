"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Floating "Ask PUG AI" launcher.
 *
 * Phase 3 ships the launcher button + a placeholder modal so the
 * footprint is reserved in every layout. The actual Azure OpenAI chat
 * is implemented in Phase 17.
 */
export function AskPugAiButton() {
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open Ask PUG AI assistant"
        className={cn(
          "group fixed bottom-5 right-5 z-30 inline-flex items-center gap-2 rounded-full",
          "bg-gradient-to-r from-primary via-fuchsia-500 to-emerald-400 px-4 py-3",
          "text-sm font-medium text-primary-foreground shadow-lg shadow-primary/20",
          "transition-transform hover:scale-[1.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        )}
      >
        <span className="relative inline-flex h-6 w-6 items-center justify-center">
          <Bot className="h-5 w-5" />
          <span className="absolute -right-0.5 -top-0.5 inline-flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-300" />
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
              className="fixed bottom-0 left-0 right-0 z-50 mx-auto max-w-md p-4 sm:bottom-24 sm:right-5 sm:left-auto sm:p-0"
            >
              <div className="glass-card overflow-hidden">
                <header className="flex items-start justify-between gap-3 border-b border-border/60 p-4">
                  <div>
                    <div className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      <Sparkles className="h-3.5 w-3.5 text-primary" />
                      Coming in Phase 17
                    </div>
                    <h2 id="ask-pug-ai-title" className="mt-1 text-lg font-semibold">
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

                <div className="space-y-3 p-4 text-sm">
                  <p className="text-muted-foreground">
                    The Ask PUG AI assistant will answer questions about
                    Paris United Group Holding — company profile, group
                    companies, services, contact details, and current
                    job openings.
                  </p>
                  <p className="text-muted-foreground">
                    It will <span className="font-medium text-foreground">never</span>{" "}
                    expose private candidate data, never modify database
                    records, and will only return safe, company-approved
                    answers.
                  </p>

                  <div className="rounded-md border border-border/60 bg-background/40 p-3 text-xs text-muted-foreground">
                    <p className="font-medium text-foreground">Status</p>
                    <p className="mt-1">
                      Floating launcher reserved in Phase 3 ·
                      Azure OpenAI integration lands in Phase 17.
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
