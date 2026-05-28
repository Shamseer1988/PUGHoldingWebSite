/**
 * Sentry server-side initialisation (Phase A-8).
 *
 * Loaded by Next.js's Node.js runtime — server components, route
 * handlers, server actions, middleware that runs in Node. Captures
 * unhandled errors thrown server-side that the user would otherwise
 * just see as a generic 500 page.
 *
 * Wired into the build via ``instrumentation.ts`` which
 * conditionally imports this file when ``NEXT_RUNTIME === "nodejs"``.
 */
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  release: process.env.NEXT_PUBLIC_APP_VERSION,
  environment: process.env.NODE_ENV,
  sendDefaultPii: false,
  debug: false,
});
