/**
 * Minimal in-process toast bus (Phase C-2).
 *
 * Hand-rolled — no ``react-hot-toast`` / ``sonner`` dependency
 * (CLAUDE.md: justify new deps). The HR console only needs short
 * confirmation toasts and "new candidate landed" alerts. A
 * ``CustomEvent`` on ``window`` with a JSON detail is plenty;
 * upgrading to a richer library is a search-and-replace if the
 * surface grows.
 *
 * Use sites call ``toast.info("…")`` / ``toast.success("…")`` and a
 * single ``<Toaster />`` mounted high in the tree renders them. The
 * provider listens for the event, manages the visible stack, and
 * auto-dismisses after ``DEFAULT_DURATION``.
 */

export type ToastVariant = "info" | "success" | "warning" | "error";

export interface ToastInput {
  title?: string;
  description?: string;
  variant?: ToastVariant;
  /** Override the auto-dismiss in ms. ``0`` disables it. */
  durationMs?: number;
}

const EVENT_NAME = "pug:toast";

function emit(detail: ToastInput): void {
  // SSR-safe: silently no-op when there's no window. The toast layer
  // only matters in the browser.
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<ToastInput>(EVENT_NAME, { detail }));
}

export const toast = {
  info(title: string, opts: Omit<ToastInput, "title" | "variant"> = {}) {
    emit({ ...opts, title, variant: "info" });
  },
  success(title: string, opts: Omit<ToastInput, "title" | "variant"> = {}) {
    emit({ ...opts, title, variant: "success" });
  },
  warning(title: string, opts: Omit<ToastInput, "title" | "variant"> = {}) {
    emit({ ...opts, title, variant: "warning" });
  },
  error(title: string, opts: Omit<ToastInput, "title" | "variant"> = {}) {
    emit({ ...opts, title, variant: "error" });
  },
} as const;

export const TOAST_EVENT_NAME = EVENT_NAME;
