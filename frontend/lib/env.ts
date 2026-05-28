/**
 * Centralised access to environment variables.
 *
 * Three distinct base URLs intentionally exposed:
 *
 *   - ``apiBaseUrl``
 *     URL used by ``fetch()`` calls inside this app. Picks a
 *     **different** URL on the server vs the browser:
 *
 *       * Server (Node): prefers ``API_BASE_URL`` (typically
 *         ``http://127.0.0.1:8000/api/v1``) so SSR / server-
 *         component fetches hit the backend via loopback. This
 *         bypasses Cloudflare's edge cache + WAF entirely,
 *         eliminating the "first refresh fine, second refresh
 *         missing footer / leadership fields" flicker we used to
 *         see when SSR went out through the public HTTPS URL.
 *       * Browser: uses ``NEXT_PUBLIC_API_BASE_URL`` (the only
 *         value the bundle has access to) so client-side calls
 *         hit the public hostname through Cloudflare like any
 *         normal page resource.
 *
 *   - ``publicApiBaseUrl``
 *     The PUBLIC HTTPS URL — always. Used by ``resolveAssetUrl``
 *     and anything else that builds a URL the browser will
 *     ultimately fetch (e.g. ``<img src>`` baked into SSR HTML).
 *     Never the loopback, regardless of where the code runs.
 *
 *   - ``siteUrl`` / ``siteName``
 *     Cosmetic / SEO values, baked into the bundle.
 *
 * All three are declared in ``frontend/.env.production``.
 */

const isServer = typeof window === "undefined";

const FALLBACK_API = "http://localhost:8000/api/v1";

const publicApi =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? FALLBACK_API;

// Phase A-7: ``publicMediaBaseUrl`` is the CDN host the backend's
// storage layer (``app.services.storage``) returns when R2 is
// configured — e.g. ``https://media.your-domain.com``. When unset
// (dev, CI, any install that hasn't gone through Phase A-5), the
// existing local-disk path under ``/api/v1/uploads/…`` keeps
// flowing through ``resolveAssetUrl`` unchanged, so a fresh checkout
// still renders images without touching env files.
const publicMedia = process.env.NEXT_PUBLIC_MEDIA_BASE_URL ?? "";

export const env = {
  apiBaseUrl: isServer
    ? process.env.API_BASE_URL ?? publicApi
    : publicApi,
  publicApiBaseUrl: publicApi,
  publicMediaBaseUrl: publicMedia,
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  siteName:
    process.env.NEXT_PUBLIC_SITE_NAME ?? "Paris United Group Holding",
} as const;

export type AppEnv = typeof env;
