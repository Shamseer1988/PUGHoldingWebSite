import { withSentryConfig } from "@sentry/nextjs";

/** @type {import('next').NextConfig} */

// ---------------------------------------------------------------------------
// Phase A-2 — Security headers
// ---------------------------------------------------------------------------
//
// The frontend talks to the backend over an absolute origin
// (`NEXT_PUBLIC_API_BASE_URL`) rather than always going through
// next.js rewrites, so a strict `connect-src 'self'` would block
// admin login + public CMS fetches in production. We derive the
// backend origin from the env var and add it to `connect-src` so the
// same policy works in dev (localhost:8000) and prod
// (api.your-domain.com / same-origin via reverse proxy).
const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.API_BASE_URL ??
  "http://localhost:8000/api/v1";
let apiOrigin = "";
try {
  apiOrigin = new URL(apiBaseUrl).origin;
} catch {
  // Malformed URL — leave empty; `'self'` will still cover same-origin.
  apiOrigin = "";
}

// CSP directives expressed as an array so each line is reviewable in
// diffs. Joined with `; ` before being emitted as the header value.
const csp = [
  "default-src 'self'",
  // `unsafe-inline` + `unsafe-eval` are required by Next.js's hydration
  // bootstrap and by Tag Manager / Pixel SDKs until we wire a nonce.
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' " +
    "https://www.googletagmanager.com https://www.google-analytics.com " +
    "https://connect.facebook.net https://snap.licdn.com " +
    "https://analytics.tiktok.com https://clarity.ms",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com data:",
  "img-src 'self' data: blob: https:",
  // `connect-src` needs the backend API origin plus the analytics +
  // R2 hosts the frontend fetches from.
  "connect-src 'self' " +
    (apiOrigin ? apiOrigin + " " : "") +
    "https://www.google-analytics.com https://vitals.vercel-insights.com " +
    "*.r2.cloudflarestorage.com",
  // ``frame-src`` allows the Google Maps embed on the Contact page +
  // the optional admin-pasted map embed in the footer. ``youtube.com``
  // covers any future hero video embeds. Anything else in an iframe is
  // blocked.
  "frame-src 'self' https://www.google.com https://www.youtube.com https://www.youtube-nocookie.com",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");


const securityHeaders = [
  { key: "X-DNS-Prefetch-Control", value: "on" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  { key: "Content-Security-Policy", value: csp },
];


// Phase A-7: derive the public R2 / CDN hostname from
// ``NEXT_PUBLIC_MEDIA_BASE_URL`` so the same config works for any
// custom domain the operator wires up in Phase A-5 step 4
// (e.g. ``media.your-domain.com``). Falls back to a placeholder so a
// ``next.config`` import doesn't crash in a fresh checkout that
// hasn't filled in ``.env.local`` yet — the placeholder will never
// match a real request.
let r2Host;
try {
  r2Host = new URL(
    process.env.NEXT_PUBLIC_MEDIA_BASE_URL ??
      "https://placeholder.r2.cloudflarestorage.com",
  ).hostname;
} catch {
  r2Host = "placeholder.r2.cloudflarestorage.com";
}


const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // ESLint + the TypeScript type-checker each cache the whole
  // codebase in memory while ``next build`` runs, and on a 2 GB
  // EC2 the combined peak (Node + Webpack + ESLint + tsc) blows
  // past available RAM, OOM-killing the build (and sometimes the
  // host). Both checks already run in CI (``npm run lint`` /
  // ``npm run type-check`` via GitHub Actions) and surface live
  // in the dev IDE, so re-running them inside the production
  // Docker build is duplicate work that costs ~600 MB of peak
  // memory. Skip them at build time; the bundle webpack emits
  // is unaffected.
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "images.unsplash.com" },
      // Default R2 bucket URL form ``<account>.r2.cloudflarestorage.com``.
      { protocol: "https", hostname: "**.r2.cloudflarestorage.com" },
      // Operator's custom R2 / CDN domain when configured.
      { protocol: "https", hostname: r2Host },
    ],
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
  async rewrites() {
    // Admin-controlled domain-verification files (Google Search Console,
    // Bing, Pinterest, Yandex, generic *-verification.html). The backend
    // validates the filename pattern again at the API layer so this
    // rewrite is safe even if someone added a permissive pattern below.
    //
    // Admins upload the file content under
    //   Admin -> Settings -> SEO Configuration -> Domain Verification.
    //
    // Examples of supported root URLs:
    //   /google1234567890abcd.html
    //   /BingSiteAuth.xml
    //   /pinterest-abc123.html
    //   /yandex_abc123.html
    //   /my-site-verification.html
    const apiBase =
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      process.env.API_BASE_URL ??
      "http://localhost:8000/api/v1";
    return [
      // Branded short URLs — ``/go/{slug}`` resolves to the backend
      // public endpoint, which 302s to the campaign target. Pattern
      // accepts upper-case too so a flyer printed in CAPS still
      // works (the backend lower-cases before lookup). Kept as a
      // rewrite so every click round-trips through us for the
      // counter.
      {
        source: "/go/:slug([A-Za-z0-9_-]{3,32})",
        destination: `${apiBase}/go/:slug`,
      },
      {
        source: "/:filename(google[a-zA-Z0-9_-]{4,64}\\.html)",
        destination: `${apiBase}/public/seo/verify/:filename`,
      },
      {
        source: "/BingSiteAuth.xml",
        destination: `${apiBase}/public/seo/verify/BingSiteAuth.xml`,
      },
      {
        source: "/:filename(pinterest-[a-zA-Z0-9_-]{4,64}\\.html)",
        destination: `${apiBase}/public/seo/verify/:filename`,
      },
      {
        source: "/:filename(yandex_[a-zA-Z0-9_-]{4,64}\\.html)",
        destination: `${apiBase}/public/seo/verify/:filename`,
      },
      {
        source: "/:filename([a-zA-Z0-9_-]{3,40}-verification\\.html)",
        destination: `${apiBase}/public/seo/verify/:filename`,
      },
      {
        source: "/:filename([a-zA-Z0-9_-]{3,40}-site-verification\\.html)",
        destination: `${apiBase}/public/seo/verify/:filename`,
      },
    ];
  },
};

// Phase A-8: Sentry wrap. ``withSentryConfig`` is what hooks
// ``instrumentation.ts`` + the three ``sentry.*.config.ts`` files
// into the bundle so the SDK actually loads at runtime. Source-map
// upload is intentionally disabled here because it requires a
// ``SENTRY_AUTH_TOKEN`` that lives outside this repo — when an
// operator wants nicer stack traces in the dashboard they can flip
// ``sourcemaps.disable`` to ``false`` and add the token to their
// CI environment. Runtime error capture works without it.
export default withSentryConfig(nextConfig, {
  silent: !process.env.CI,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  // Skip the auth-token-gated upload step.
  sourcemaps: {
    disable: true,
  },
  // Don't proxy events through a Next.js API route — we ship them
  // straight to Sentry's ingest endpoint. Tunnel routes are
  // useful when ad-blockers eat the requests, but they bypass our
  // own CSP and add latency.
  tunnelRoute: undefined,
});
