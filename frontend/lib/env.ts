/**
 * Centralised access to public environment variables exposed to the
 * browser. Keep `NEXT_PUBLIC_*` reads in this single module so the rest
 * of the app can swap them in tests / storybooks without sprinkling
 * `process.env` everywhere.
 */

export const env = {
  apiBaseUrl:
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1",
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  siteName:
    process.env.NEXT_PUBLIC_SITE_NAME ?? "Paris United Group Holding",
} as const;

export type AppEnv = typeof env;
