/**
 * Server component that renders body-start tags.
 *
 * Mounted as the FIRST child of `<body>` in the root layout so the
 * GTM noscript iframe — which Google requires to sit immediately
 * after the opening `<body>` — is in the correct position.
 *
 * Also handles the Meta Pixel noscript image beacon when Pixel is
 * active and `enable_noscript` is set on the row.
 *
 * Inactive rows are filtered upstream by the backend.
 */
import { pickGtmId, type PublicSeoHeadFeed } from "@/lib/seo-api";

interface SeoBodyStartProps {
  feed: PublicSeoHeadFeed;
}

export function SeoBodyStart({ feed }: SeoBodyStartProps) {
  const gtmId = pickGtmId(feed);
  const pixel = feed.integrations.find(
    (i) => i.provider === "meta_pixel" && i.enable_noscript
  );

  if (!gtmId && !pixel) return null;

  return (
    <>
      {gtmId && (
        <noscript>
          <iframe
            src={`https://www.googletagmanager.com/ns.html?id=${gtmId}`}
            height="0"
            width="0"
            title="Google Tag Manager"
            style={{ display: "none", visibility: "hidden" }}
          />
        </noscript>
      )}
      {pixel && (
        <noscript>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`https://www.facebook.com/tr?id=${pixel.tracking_id}&ev=PageView&noscript=1`}
            alt=""
            height="1"
            width="1"
            style={{ display: "none" }}
          />
        </noscript>
      )}
    </>
  );
}
