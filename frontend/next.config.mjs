/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "images.unsplash.com" },
      { protocol: "https", hostname: "**.r2.cloudflarestorage.com" },
    ],
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

export default nextConfig;
