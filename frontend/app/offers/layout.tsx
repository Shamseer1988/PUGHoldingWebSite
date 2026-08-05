/**
 * Layout for the public Offers / Catalogue surface.
 *
 * Intentionally lives OUTSIDE the ``(public)`` route group so it
 * doesn't inherit the site navbar / footer / floating AI button —
 * these pages need a full-bleed, immersive feel so the flyer occupies
 * the whole viewport.
 *
 * Deliberately chrome-free: no top bar, no footer.
 *
 * The top bar used to carry "Back to site" / "Offers & Catalogues". It
 * cost a sticky strip of every phone screen on a surface whose visitors
 * arrive by scanning a code in-store — they came for the flyer, not to
 * navigate the corporate site. Removing it also lets the branch hero
 * banner start immediately below the browser chrome.
 *
 * The footer isn't here either: branch storefronts render their own
 * (that store's address, hours and socials), and a layout-level footer
 * stacked a second one underneath it. Pages that want the slim group
 * footer — which carries the "Main site" link — import ``OffersFooter``
 * directly.
 */
export default function OffersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <div className="flex-1">{children}</div>
    </div>
  );
}
