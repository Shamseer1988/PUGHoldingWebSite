/**
 * Recognise Next.js's static-rendering bail-out signal.
 *
 * During ``next build`` Next tries to prerender every page. When a
 * page performs a ``cache: "no-store"`` fetch it cannot be static, and
 * Next signals that by **throwing** a ``DynamicServerError`` carrying
 * ``digest === "DYNAMIC_SERVER_USAGE"``. Next catches it upstream and
 * marks the route ``ƒ (Dynamic) server-rendered on demand``.
 *
 * It is control flow, not a failure — but it looks exactly like a
 * failed fetch to a ``try/catch`` around one. Our public fetch helpers
 * were logging it as ``fetch failed``, which filled the build output
 * with alarming stack traces for a build that had actually succeeded.
 *
 * Swallowing it is worse than noisy: if a helper catches the signal
 * and returns its empty fallback, the page can render with no data
 * instead of correctly bailing out to dynamic. So callers must
 * re-throw it and let Next do its job.
 */

/** True when ``error`` is Next's "this page must be dynamic" signal. */
export function isDynamicServerError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "digest" in error &&
    (error as { digest?: unknown }).digest === "DYNAMIC_SERVER_USAGE"
  );
}

/**
 * Re-throw Next's bail-out signal; return normally for real errors.
 *
 * Call as the first line of a ``catch`` around a ``no-store`` fetch:
 *
 * ```ts
 * } catch (error) {
 *   rethrowIfDynamicServerError(error);
 *   console.error("…", error);
 *   return null;
 * }
 * ```
 */
export function rethrowIfDynamicServerError(error: unknown): void {
  if (isDynamicServerError(error)) throw error;
}
