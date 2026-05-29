"use client";

/**
 * Toast viewport (Phase C-2).
 *
 * Mounts once high in the tree (admin layout, HR layout). Subscribes
 * to ``pug:toast`` window events the ``toast`` helper in
 * ``lib/toast.ts`` dispatches, renders a stack in the top-right
 * corner, and auto-dismisses each entry. The viewport flips to the
 * top-left under ``[dir="rtl"]`` so the Arabic locale doesn't park
 * notifications over the corner where the operator's eye lives.
 */
import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  X,
  XCircle,
} from "lucide-react";

import {
  TOAST_EVENT_NAME,
  type ToastInput,
  type ToastVariant,
} from "@/lib/toast";
import { cn } from "@/lib/utils";

interface ActiveToast extends ToastInput {
  id: number;
}

const DEFAULT_DURATION = 5000;

const VARIANT_STYLES: Record<ToastVariant, string> = {
  info: "border-sky-500/30 bg-sky-500/5 text-sky-900 dark:text-sky-200",
  success:
    "border-emerald-500/30 bg-emerald-500/5 text-emerald-900 dark:text-emerald-200",
  warning:
    "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200",
  error: "border-rose-500/40 bg-rose-500/10 text-rose-900 dark:text-rose-200",
};

const VARIANT_ICON: Record<
  ToastVariant,
  React.ComponentType<{ className?: string }>
> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle,
};

export function Toaster() {
  const [toasts, setToasts] = React.useState<ActiveToast[]>([]);
  const counter = React.useRef(0);

  React.useEffect(() => {
    function onToast(e: Event) {
      const detail = (e as CustomEvent<ToastInput>).detail;
      counter.current += 1;
      const id = counter.current;
      const entry: ActiveToast = { id, variant: "info", ...detail };
      setToasts((prev) => [...prev, entry]);

      const duration = entry.durationMs ?? DEFAULT_DURATION;
      if (duration > 0) {
        window.setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== id));
        }, duration);
      }
    }

    window.addEventListener(TOAST_EVENT_NAME, onToast);
    return () => window.removeEventListener(TOAST_EVENT_NAME, onToast);
  }, []);

  function dismiss(id: number) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  if (toasts.length === 0) return null;

  return (
    <div
      // Position in the corner opposite the reading direction so the
      // toasts don't sit under the page-action area the operator's
      // pointer hovers.
      className="pointer-events-none fixed top-4 z-[60] flex w-full max-w-sm flex-col gap-2 px-4 ltr:right-0 rtl:left-0"
      role="region"
      aria-live="polite"
      aria-label="Notifications"
    >
      {toasts.map((entry) => {
        const variant = entry.variant ?? "info";
        const Icon = VARIANT_ICON[variant];
        return (
          <div
            key={entry.id}
            role="status"
            className={cn(
              "pointer-events-auto flex items-start gap-3 rounded-xl border bg-background/95 p-3 text-sm shadow-lg backdrop-blur",
              VARIANT_STYLES[variant]
            )}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <div className="min-w-0 flex-1">
              {entry.title && (
                <p className="font-semibold leading-tight">{entry.title}</p>
              )}
              {entry.description && (
                <p className="mt-0.5 text-xs leading-snug opacity-80">
                  {entry.description}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismiss(entry.id)}
              aria-label="Dismiss"
              className="-mr-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md opacity-60 transition-opacity hover:opacity-100"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
