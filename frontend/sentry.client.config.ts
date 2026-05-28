/**
 * Sentry client-side initialisation (Phase A-8).
 *
 * Loaded by the Next.js client bundle so unhandled errors thrown
 * during render / hydration / interaction get reported. Inert when
 * ``NEXT_PUBLIC_SENTRY_DSN`` is unset — that's how dev + CI stay
 * silent.
 *
 * Note: ``Sentry.replayIntegration`` is intentionally NOT included
 * here. Session Replay would record every user interaction on the
 * public site, which is too much data + privacy exposure for a
 * corporate marketing site.
 */
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  // Sample 10% of traffic for transaction tracing in production;
  // every request in dev so a single navigation is visible end-to-end.
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  release: process.env.NEXT_PUBLIC_APP_VERSION,
  environment: process.env.NODE_ENV,
  // Limit data sent to Sentry to what's needed for debugging — no
  // request bodies, no cookies. Same defensive stance as the backend
  // (sentry_sdk.init(..., send_default_pii=False)).
  sendDefaultPii: false,
  // Silence the SDK in dev unless an operator opted into noise.
  debug: false,
});
