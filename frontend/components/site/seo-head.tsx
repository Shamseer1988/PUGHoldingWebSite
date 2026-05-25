/**
 * Server component that injects the SEO `<head>` payload.
 *
 * Rendered once at the very top of `<body>` in the root layout — but
 * because every element returned here is either a Next.js
 * `<Script>` (which Next ports to `<head>`) or a meta tag returned
 * via the App Router's `generateMetadata()` API, nothing actually
 * lands in the body. Verification meta tags are NOT emitted here:
 * they ship via `generateMetadata()` in the root layout, because the
 * App Router only honours real metadata tags from there.
 *
 * Responsibilities of this component:
 *   - Render the GTM `<head>` script (afterInteractive) when active.
 *   - Render GA4 / Meta Pixel / Microsoft Clarity / LinkedIn Insight /
 *     TikTok Pixel / X Pixel direct scripts when active and the row
 *     has a placement of `head` (the default).
 *   - Nothing renders when the feed is empty or when this is the
 *     admin / HR surface (the layout decides; this component just
 *     does as it's told).
 *
 * Notes on duplication:
 *   - The admin UI surfaces a warning if GTM and direct GA4/Pixel are
 *     both active. We still render whatever the admin saved — the
 *     warning is advisory, not a hard block.
 */
import Script from "next/script";

import type {
  PublicSeoHeadFeed,
  PublicTrackingIntegration,
} from "@/lib/seo-api";

interface SeoHeadProps {
  feed: PublicSeoHeadFeed;
}

function gtmScript(id: string, dataLayerName: string): string {
  // Standard Google Tag Manager loader. The `j.async` flag is what
  // Google's own snippet uses; keeping it byte-identical keeps the
  // implementation easy to audit against their docs.
  const dl = dataLayerName || "dataLayer";
  return `(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);})(window,document,'script','${dl}','${id}');`;
}

function ga4ConfigScript(id: string, debug: boolean): string {
  // Inline config snippet that pairs with the external gtag.js loader
  // below. Kept tiny on purpose — extra options can live in GTM.
  const debugFlag = debug ? ", { 'debug_mode': true }" : "";
  return `window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${id}'${debugFlag});`;
}

function metaPixelScript(id: string): string {
  return `!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('init','${id}');fbq('track','PageView');`;
}

function clarityScript(id: string): string {
  return `(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};t=l.createElement(r);t.async=1;t.src='https://www.clarity.ms/tag/'+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})(window,document,'clarity','script','${id}');`;
}

function linkedinInsightScript(partnerId: string): string {
  return `_linkedin_partner_id = '${partnerId}';
window._linkedin_data_partner_ids = window._linkedin_data_partner_ids || [];
window._linkedin_data_partner_ids.push(_linkedin_partner_id);`;
}

function tiktokPixelScript(id: string): string {
  return `!function (w, d, t) {w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];ttq.methods=["page","track","identify","instances","debug","on","off","once","ready","alias","group","enableCookie","disableCookie","holdConsent","revokeConsent","grantConsent"],ttq.setAndDefer=function(t,e){t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}};for(var i=0;i<ttq.methods.length;i++)ttq.setAndDefer(ttq,ttq.methods[i]);ttq.instance=function(t){for(var e=ttq._i[t]||[],n=0;n<ttq.methods.length;n++)ttq.setAndDefer(e,ttq.methods[n]);return e},ttq.load=function(e,n){var r="https://analytics.tiktok.com/i18n/pixel/events.js",o=n&&n.partner;ttq._i=ttq._i||{},ttq._i[e]=[],ttq._i[e]._u=r,ttq._t=ttq._t||{},ttq._t[e]=+new Date,ttq._o=ttq._o||{},ttq._o[e]=n||{};n=document.createElement("script");n.type="text/javascript",n.async=!0,n.src=r+"?sdkid="+e+"&lib="+t;e=document.getElementsByTagName("script")[0];e.parentNode.insertBefore(n,e)};ttq.load('${id}');ttq.page();}(window, document, 'ttq');`;
}

function twitterPixelScript(id: string): string {
  return `!function(e,t,n,s,u,a){e.twq||(s=e.twq=function(){s.exe?s.exe.apply(s,arguments):s.queue.push(arguments);},s.version='1.1',s.queue=[],u=t.createElement(n),u.async=!0,u.src='https://static.ads-twitter.com/uwt.js',a=t.getElementsByTagName(n)[0],a.parentNode.insertBefore(u,a))}(window,document,'script');twq('config','${id}');`;
}

function pickHeadIntegrations(
  integrations: PublicTrackingIntegration[]
): PublicTrackingIntegration[] {
  // Phase 1 only renders integrations whose placement is `head`.
  // Body-start (GTM noscript) and body-end placements are handled
  // separately so they sit in the right spot in the DOM.
  return integrations.filter((row) => row.placement === "head");
}

export function SeoHead({ feed }: SeoHeadProps) {
  if (!feed.integrations.length) return null;

  return (
    <>
      {pickHeadIntegrations(feed.integrations).map((row) => {
        switch (row.provider) {
          case "google_tag_manager":
            return (
              <Script
                id="seo-gtm"
                key={`gtm-${row.tracking_id}`}
                strategy="afterInteractive"
              >
                {gtmScript(row.tracking_id, row.data_layer_name)}
              </Script>
            );
          case "google_analytics_ga4":
            // GA4 needs both the external gtag loader and the config
            // snippet. Two `<Script>` tags so Next can hash them
            // separately and skip re-hydration on navigation.
            return (
              <>
                <Script
                  id="seo-ga4-loader"
                  key={`ga4-loader-${row.tracking_id}`}
                  src={`https://www.googletagmanager.com/gtag/js?id=${row.tracking_id}`}
                  strategy="afterInteractive"
                />
                <Script
                  id="seo-ga4-config"
                  key={`ga4-config-${row.tracking_id}`}
                  strategy="afterInteractive"
                >
                  {ga4ConfigScript(row.tracking_id, row.debug_mode)}
                </Script>
              </>
            );
          case "meta_pixel":
            return (
              <Script
                id="seo-meta-pixel"
                key={`pixel-${row.tracking_id}`}
                strategy="afterInteractive"
              >
                {metaPixelScript(row.tracking_id)}
              </Script>
            );
          case "microsoft_clarity":
            return (
              <Script
                id="seo-clarity"
                key={`clarity-${row.tracking_id}`}
                strategy="afterInteractive"
              >
                {clarityScript(row.tracking_id)}
              </Script>
            );
          case "linkedin_insight":
            return (
              <>
                <Script
                  id="seo-linkedin-config"
                  key={`linkedin-config-${row.tracking_id}`}
                  strategy="afterInteractive"
                >
                  {linkedinInsightScript(row.tracking_id)}
                </Script>
                <Script
                  id="seo-linkedin-loader"
                  key={`linkedin-loader-${row.tracking_id}`}
                  src="https://snap.licdn.com/li.lms-analytics/insight.min.js"
                  strategy="afterInteractive"
                />
              </>
            );
          case "tiktok_pixel":
            return (
              <Script
                id="seo-tiktok"
                key={`tiktok-${row.tracking_id}`}
                strategy="afterInteractive"
              >
                {tiktokPixelScript(row.tracking_id)}
              </Script>
            );
          case "twitter_pixel":
            return (
              <Script
                id="seo-twitter"
                key={`twitter-${row.tracking_id}`}
                strategy="afterInteractive"
              >
                {twitterPixelScript(row.tracking_id)}
              </Script>
            );
          default:
            // Unknown / custom provider — silently skipped in Phase 1.
            // The "Advanced Scripts" tab arrives in Phase 3.
            return null;
        }
      })}
    </>
  );
}
