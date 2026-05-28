/**
 * Next.js instrumentation hook (Phase A-8).
 *
 * Next.js calls ``register()`` exactly once when the Node.js server
 * starts, and again for the edge runtime. We use the ``NEXT_RUNTIME``
 * env var to load the right Sentry config so a single ``Sentry.init``
 * happens per runtime — no double-init, no cross-runtime imports of
 * Node-only APIs into the edge bundle.
 *
 * The ``onRequestError`` hook is Next 15+; this file targets 14.2,
 * so we rely on Sentry's automatic instrumentation (wired via
 * ``withSentryConfig`` in ``next.config.mjs``) to capture
 * uncaught errors thrown server-side. Add the hook when we
 * upgrade to Next 15.
 */
export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}
