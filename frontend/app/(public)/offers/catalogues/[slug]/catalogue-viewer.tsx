"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  LayoutGrid,
  Maximize2,
  Minimize2,
  Share2,
  ZoomIn,
  ZoomOut,
  X,
} from "lucide-react";

import type {
  CatalogueDetail,
  CataloguePage,
} from "@/lib/admin/marketing-types";
import {
  catalogueDownloadUrl,
  detectDevice,
  getOrCreateSessionId,
  logCatalogueView,
} from "@/lib/public-offers-client";
import { cn } from "@/lib/utils";


interface Props {
  catalogue: CatalogueDetail;
}


export function CatalogueViewer({ catalogue }: Props) {
  // ``index`` is the zero-based index of the LEFT page in desktop
  // two-page spreads; on mobile we render one page at a time so it
  // simply points at the visible page.
  const [index, setIndex] = React.useState(0);
  const [zoom, setZoom] = React.useState(1);
  const [thumbsOpen, setThumbsOpen] = React.useState(false);
  const [shareOpen, setShareOpen] = React.useState(false);
  const [fullscreen, setFullscreen] = React.useState(false);
  const [isMobile, setIsMobile] = React.useState(false);

  const containerRef = React.useRef<HTMLDivElement>(null);
  const pages = catalogue.pages;
  const pageCount = pages.length;

  // Detect mobile vs desktop for the layout switch (and analytics).
  // Re-checks on resize so the user can rotate / drag the window.
  React.useEffect(() => {
    function check() {
      setIsMobile(window.innerWidth < 768);
    }
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // Analytics beacon — fired once on mount, again on unmount with
  // the duration the user spent in the viewer.
  React.useEffect(() => {
    const start = Date.now();
    const session = getOrCreateSessionId();
    const device = detectDevice();
    void logCatalogueView(catalogue.id, { session_hash: session, device });
    return () => {
      const duration = Math.round((Date.now() - start) / 1000);
      void logCatalogueView(catalogue.id, {
        session_hash: session,
        device,
        duration_seconds: duration,
      });
    };
  }, [catalogue.id]);

  // Keyboard navigation: ← / → arrow, Home / End, Esc to close fullscreen.
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }
      if (e.key === "ArrowRight") prev(false);
      else if (e.key === "ArrowLeft") prev(true);
      else if (e.key === "Home") setIndex(0);
      else if (e.key === "End") setIndex(pageCount - 1);
      else if (e.key === "+" || e.key === "=") setZoom((z) => clampZoom(z + 0.2));
      else if (e.key === "-") setZoom((z) => clampZoom(z - 0.2));
      else if (e.key.toLowerCase() === "f") toggleFullscreen();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageCount, isMobile]);

  // Listen for fullscreen change to keep state in sync if the user
  // hits Esc rather than our toggle button.
  React.useEffect(() => {
    function onFs() {
      setFullscreen(Boolean(document.fullscreenElement));
    }
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  function prev(backwards: boolean) {
    setIndex((cur) => {
      // Desktop: jump two pages at a time, except for the first
      // "single" page (the cover) which always sits on its own.
      const step = isMobile ? 1 : cur === 0 ? 1 : 2;
      const next = backwards ? cur - step : cur + step;
      if (next < 0) return 0;
      if (next > pageCount - 1) return pageCount - 1;
      return next;
    });
  }

  function jumpTo(pageNum: number) {
    setIndex(Math.max(0, Math.min(pageCount - 1, pageNum - 1)));
    setThumbsOpen(false);
  }

  function toggleFullscreen() {
    const el = containerRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      el.requestFullscreen().catch(() => {
        /* swallow — some browsers refuse without a gesture */
      });
    } else {
      document.exitFullscreen().catch(() => {});
    }
  }

  const shareUrl = typeof window !== "undefined" ? window.location.href : "";
  async function nativeShare() {
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({
          title: catalogue.title,
          text: catalogue.description || catalogue.title,
          url: shareUrl,
        });
      } catch {
        /* user-cancelled */
      }
    } else {
      setShareOpen((v) => !v);
    }
  }

  function copyLink() {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(shareUrl).catch(() => {});
    }
    setShareOpen(false);
  }

  // Two-page spread on desktop, single page on mobile.
  const leftPage = pages[index];
  const rightPage = !isMobile && index > 0 ? pages[index + 1] : null;
  const isSinglePage = isMobile || index === 0 || rightPage === undefined;

  return (
    <main
      ref={containerRef}
      className={cn(
        "relative flex min-h-screen flex-col bg-pug-green-800 text-pug-gold-50",
        fullscreen && "h-screen"
      )}
    >
      {/* ----- Top bar ----- */}
      <header className="z-10 flex items-center gap-3 border-b border-white/10 bg-pug-green-800/95 px-4 py-3 backdrop-blur sm:px-6">
        <Link
          href={
            catalogue.campaign_id
              ? `/offers`
              : "/offers"
          }
          className="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.18em] text-pug-gold-100 hover:text-pug-gold-300"
        >
          <ArrowLeft className="h-3 w-3" />
          Offers
        </Link>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{catalogue.title}</p>
          <p className="text-[11px] text-pug-gold-200/70">
            {pageCount} page{pageCount === 1 ? "" : "s"}
          </p>
        </div>
        <div className="hidden gap-1 sm:flex">
          <IconButton
            label="Zoom out"
            icon={ZoomOut}
            onClick={() => setZoom((z) => clampZoom(z - 0.2))}
            disabled={zoom <= MIN_ZOOM + 0.001}
          />
          <span className="inline-flex w-12 items-center justify-center text-xs text-pug-gold-100">
            {Math.round(zoom * 100)}%
          </span>
          <IconButton
            label="Zoom in"
            icon={ZoomIn}
            onClick={() => setZoom((z) => clampZoom(z + 0.2))}
            disabled={zoom >= MAX_ZOOM - 0.001}
          />
        </div>
        <IconButton
          label="Page thumbnails"
          icon={LayoutGrid}
          onClick={() => setThumbsOpen((v) => !v)}
          active={thumbsOpen}
        />
        <div className="relative">
          <IconButton
            label="Share"
            icon={Share2}
            onClick={() => void nativeShare()}
          />
          {shareOpen && <ShareMenu shareUrl={shareUrl} onCopy={copyLink} />}
        </div>
        <IconButton
          label="Download PDF"
          icon={Download}
          as={Link}
          href={catalogueDownloadUrl(catalogue.id)}
        />
        <IconButton
          label={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          icon={fullscreen ? Minimize2 : Maximize2}
          onClick={toggleFullscreen}
        />
      </header>

      {/* ----- Viewer body ----- */}
      <div className="relative flex-1 overflow-hidden">
        {isMobile ? (
          // Mobile: snap-scrolling vertical list of pages. Better touch
          // UX than a forced flipbook on a 6" screen.
          <MobileScroller pages={pages} onActivePage={(n) => setIndex(n - 1)} />
        ) : (
          <DesktopSpread
            leftPage={leftPage}
            rightPage={rightPage}
            isSinglePage={isSinglePage}
            zoom={zoom}
          />
        )}

        {/* Prev / next arrows — desktop only; mobile uses native scroll */}
        {!isMobile && (
          <>
            <NavArrow
              direction="prev"
              onClick={() => prev(true)}
              disabled={index === 0}
            />
            <NavArrow
              direction="next"
              onClick={() => prev(false)}
              disabled={index >= pageCount - 1}
            />
          </>
        )}
      </div>

      {/* ----- Thumbnail strip ----- */}
      {thumbsOpen && (
        <ThumbnailStrip
          pages={pages}
          currentIndex={index}
          onJump={jumpTo}
          onClose={() => setThumbsOpen(false)}
        />
      )}

      {/* ----- Page indicator (mobile only) ----- */}
      {isMobile && (
        <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full border border-white/20 bg-pug-green-900/80 px-3 py-1 text-[11px] text-pug-gold-100">
          Page {index + 1} of {pageCount}
        </div>
      )}
    </main>
  );
}


// ---------------------------------------------------------------------------
// Layout — Desktop two-page spread
// ---------------------------------------------------------------------------

function DesktopSpread({
  leftPage,
  rightPage,
  isSinglePage,
  zoom,
}: {
  leftPage: CataloguePage | undefined;
  rightPage: CataloguePage | null;
  isSinglePage: boolean;
  zoom: number;
}) {
  if (!leftPage) return null;
  return (
    <div className="h-full w-full overflow-auto">
      <div
        className="flex min-h-full items-center justify-center p-6 transition-transform"
        style={{ transform: `scale(${zoom})`, transformOrigin: "top center" }}
      >
        <div
          className={cn(
            "flex gap-2 transition-all",
            isSinglePage ? "max-w-[60vh]" : "max-w-[120vh]"
          )}
        >
          <PageImage page={leftPage} side="left" />
          {!isSinglePage && rightPage && (
            <PageImage page={rightPage} side="right" />
          )}
        </div>
      </div>
    </div>
  );
}


function PageImage({
  page,
  side,
}: {
  page: CataloguePage;
  side: "left" | "right";
}) {
  return (
    <div
      className={cn(
        "relative overflow-hidden bg-white shadow-2xl shadow-black/40 transition-shadow",
        side === "left" ? "rounded-l-lg" : "rounded-r-lg"
      )}
      style={{ aspectRatio: `${page.width} / ${page.height}` }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={page.image_url}
        alt={`Page ${page.page_number}`}
        className="h-full w-full object-contain"
        loading="lazy"
      />
      <span className="absolute bottom-2 left-2 rounded-full bg-pug-green-900/70 px-2 py-0.5 text-[10px] font-medium text-pug-gold-100">
        {page.page_number}
      </span>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Layout — Mobile vertical scroller
// ---------------------------------------------------------------------------

function MobileScroller({
  pages,
  onActivePage,
}: {
  pages: CataloguePage[];
  onActivePage: (pageNumber: number) => void;
}) {
  // Track which page is centered in the viewport so the page-indicator
  // pill stays accurate as the user swipes.
  const observer = React.useRef<IntersectionObserver | null>(null);
  React.useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    observer.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && entry.intersectionRatio > 0.55) {
            const num = Number(
              (entry.target as HTMLElement).dataset.pageNumber
            );
            if (!Number.isNaN(num)) onActivePage(num);
          }
        }
      },
      { threshold: [0.55] }
    );
    return () => {
      observer.current?.disconnect();
    };
  }, [onActivePage]);

  const setRef = React.useCallback(
    (el: HTMLDivElement | null) => {
      if (!el || !observer.current) return;
      observer.current.observe(el);
    },
    []
  );

  return (
    <div className="flex h-full snap-y snap-mandatory flex-col overflow-y-auto">
      {pages.map((p) => (
        <div
          key={p.page_number}
          ref={setRef}
          data-page-number={p.page_number}
          className="flex min-h-full shrink-0 snap-center items-center justify-center p-3"
        >
          <div
            className="overflow-hidden rounded-lg bg-white shadow-2xl shadow-black/40"
            style={{ aspectRatio: `${p.width} / ${p.height}` }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={p.image_url}
              alt={`Page ${p.page_number}`}
              className="h-full w-full object-contain"
              loading="lazy"
            />
          </div>
        </div>
      ))}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Thumbnail strip
// ---------------------------------------------------------------------------

function ThumbnailStrip({
  pages,
  currentIndex,
  onJump,
  onClose,
}: {
  pages: CataloguePage[];
  currentIndex: number;
  onJump: (pageNumber: number) => void;
  onClose: () => void;
}) {
  return (
    <aside
      className="z-20 border-t border-white/10 bg-pug-green-900/95 backdrop-blur"
      aria-label="Page thumbnails"
    >
      <header className="flex items-center justify-between px-4 py-2 sm:px-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-pug-gold-200/80">
          Pages ({pages.length})
        </p>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full p-1 text-pug-gold-200/80 hover:text-white"
          aria-label="Close thumbnails"
        >
          <X className="h-4 w-4" />
        </button>
      </header>
      <div className="overflow-x-auto pb-3">
        <div className="flex gap-2 px-4 sm:px-6">
          {pages.map((p, i) => (
            <button
              key={p.page_number}
              type="button"
              onClick={() => onJump(p.page_number)}
              className={cn(
                "shrink-0 overflow-hidden rounded border transition-all",
                i === currentIndex
                  ? "border-pug-gold-300 ring-2 ring-pug-gold-300/40"
                  : "border-white/15 opacity-70 hover:opacity-100"
              )}
              aria-label={`Jump to page ${p.page_number}`}
              title={`Page ${p.page_number}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={p.thumbnail_url}
                alt=""
                className="h-24 w-auto bg-white object-cover"
                loading="lazy"
              />
              <p className="px-1 py-0.5 text-center text-[10px] text-pug-gold-100">
                {p.page_number}
              </p>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}


// ---------------------------------------------------------------------------
// Reusable bits
// ---------------------------------------------------------------------------

const MIN_ZOOM = 0.6;
const MAX_ZOOM = 2.4;
function clampZoom(v: number) {
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Number(v.toFixed(2))));
}


type IconButtonProps = {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick?: () => void;
  disabled?: boolean;
  active?: boolean;
} & (
  | { as?: undefined; href?: undefined }
  | { as: typeof Link; href: string }
);


function IconButton(props: IconButtonProps) {
  const { label, icon: Icon, onClick, disabled, active } = props;
  const className = cn(
    "inline-flex h-9 w-9 items-center justify-center rounded-md text-pug-gold-100 transition-colors",
    active && "bg-white/10",
    disabled
      ? "cursor-not-allowed opacity-30"
      : "hover:bg-white/10 hover:text-white"
  );
  if (props.as === Link && props.href) {
    return (
      <Link
        href={props.href}
        className={className}
        aria-label={label}
        title={label}
        target="_blank"
      >
        <Icon className="h-4 w-4" />
      </Link>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={className}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}


function NavArrow({
  direction,
  onClick,
  disabled,
}: {
  direction: "prev" | "next";
  onClick: () => void;
  disabled: boolean;
}) {
  const Icon = direction === "prev" ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={direction === "prev" ? "Previous page" : "Next page"}
      className={cn(
        "absolute top-1/2 z-10 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full border border-white/10 bg-pug-green-900/80 text-pug-gold-100 backdrop-blur transition-all",
        direction === "prev" ? "left-4" : "right-4",
        disabled
          ? "cursor-not-allowed opacity-30"
          : "hover:bg-pug-green-900 hover:text-white"
      )}
    >
      <Icon className="h-6 w-6" />
    </button>
  );
}


function ShareMenu({
  shareUrl,
  onCopy,
}: {
  shareUrl: string;
  onCopy: () => void;
}) {
  const whatsAppUrl = `https://wa.me/?text=${encodeURIComponent(shareUrl)}`;
  const mailtoUrl = `mailto:?subject=${encodeURIComponent(
    "Have a look at this catalogue"
  )}&body=${encodeURIComponent(shareUrl)}`;
  return (
    <div
      role="menu"
      className="absolute right-0 top-full mt-2 w-52 overflow-hidden rounded-lg border border-white/10 bg-pug-green-900/95 text-sm shadow-2xl backdrop-blur"
    >
      <a
        href={whatsAppUrl}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-2 px-3 py-2 text-pug-gold-100 hover:bg-white/10"
        role="menuitem"
      >
        <span
          aria-hidden
          className="inline-block h-2 w-2 rounded-full bg-emerald-400"
        />
        Share on WhatsApp
      </a>
      <a
        href={mailtoUrl}
        className="flex items-center gap-2 px-3 py-2 text-pug-gold-100 hover:bg-white/10"
        role="menuitem"
      >
        <span
          aria-hidden
          className="inline-block h-2 w-2 rounded-full bg-sky-400"
        />
        Share via email
      </a>
      <button
        type="button"
        onClick={onCopy}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-pug-gold-100 hover:bg-white/10"
        role="menuitem"
      >
        <Copy className="h-3.5 w-3.5" />
        Copy link
      </button>
    </div>
  );
}
