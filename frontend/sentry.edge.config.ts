/**
 * Sentry edge-runtime initialisation (Phase A-8).
 *
 * Loaded by Next.js's edge runtime — currently only the ``middleware``
 * we don't have, but the SDK pattern bundles a config for it so a
 * future edge-runtime route is automatically instrumented when we
 * add one. Kept slim because the edge runtime has tight bundle-size
 * limits.
 */
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  release: process.env.NEXT_PUBLIC_APP_VERSION,
  environment: process.env.NODE_ENV,
  sendDefaultPii: false,
});
