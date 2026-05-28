"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Copy,
  Download,
  LayoutGrid,
  List,
  Maximize2,
  Minimize2,
  Printer,
  Share2,
  ZoomIn,
  ZoomOut,
  X,
} from "lucide-react";

import type {
  CatalogueDetail,
  CataloguePage,
} from "@/lib/admin/marketing-types";
import { resolveAssetUrl } from "@/lib/public-api";
import {
  catalogueDownloadUrl,
  detectDevice,
  getOrCreateSessionId,
  logCatalogueView,
} from "@/lib/public-offers-client";
import { cn } from "@/lib/utils";


// react-pageflip touches ``window`` at import time (via its
// page-flip dependency), so we can't import it eagerly during SSR.
// Doing the dynamic import inside ``useEffect`` lets the class
// component render directly here — which means refs work the
// natural way. ``next/dynamic`` would otherwise swallow the ref.
type FlipBookComponent = React.ComponentType<Record<string, unknown>>;


interface Props {
  catalogue: CatalogueDetail;
}


export function CatalogueViewer({ catalogue }: Props) {
  const [pageIndex, setPageIndex] = React.useState(0);
  const [thumbsOpen, setThumbsOpen] = React.useState(false);
  const [outlineOpen, setOutlineOpen] = React.useState(false);
  const [shareOpen, setShareOpen] = React.useState(false);
  const [fullscreen, setFullscreen] = React.useState(false);
  const [isMobile, setIsMobile] = React.useState(false);
  const [zoom, setZoom] = React.useState(1);
  const [FlipBookComp, setFlipBookComp] =
    React.useState<FlipBookComponent | null>(null);

  const containerRef = React.useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const flipBookRef = React.useRef<any>(null);

  const pages = catalogue.pages;
  const pageCount = pages.length;

  // -----------------------------------------------------------------
  // Lazy-load react-pageflip on mount (uses ``window`` at import).
  // -----------------------------------------------------------------
  React.useEffect(() => {
    let cancelled = false;
    import("react-pageflip").then((mod) => {
      if (cancelled) return;
      const Comp = mod.default as unknown as FlipBookComponent;
      setFlipBookComp(() => Comp);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // -----------------------------------------------------------------
  // Mobile detect (Tailwind ``md`` breakpoint).
  // -----------------------------------------------------------------
  React.useEffect(() => {
    function check() {
      setIsMobile(window.innerWidth < 768);
    }
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // -----------------------------------------------------------------
  // Analytics — beacon on open + on close with duration.
  // -----------------------------------------------------------------
  React.useEffect(() => {
    const start = Date.now();
    const session = getOrCreateSessionId();
    const device = detectDevice();
    void logCatalogueView(catalogue.id, { session_hash: session, device });
    return () => {
      void logCatalogueView(catalogue.id, {
        session_hash: session,
        device,
        duration_seconds: Math.round((Date.now() - start) / 1000),
      });
    };
  }, [catalogue.id]);

  // -----------------------------------------------------------------
  // Navigation helpers — always go through the flipbook so the
  // animation fires. ``pageFlip()`` returns the PageFlip instance.
  // -----------------------------------------------------------------
  const next = React.useCallback(() => {
    const api = flipBookRef.current?.pageFlip?.();
    if (api) api.flipNext();
    else setPageIndex((i) => Math.min(pageCount - 1, i + 1));
  }, [pageCount]);

  const prev = React.useCallback(() => {
    const api = flipBookRef.current?.pageFlip?.();
    if (api) api.flipPrev();
    else setPageIndex((i) => Math.max(0, i - 1));
  }, []);

  const goTo = React.useCallback(
    (idx: number) => {
      const target = Math.max(0, Math.min(pageCount - 1, idx));
      const api = flipBookRef.current?.pageFlip?.();
      if (api) api.flip(target);
      else setPageIndex(target);
      setThumbsOpen(false);
      setOutlineOpen(false);
    },
    [pageCount]
  );

  // -----------------------------------------------------------------
  // Keyboard.
  // -----------------------------------------------------------------
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }
      if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "Home") goTo(0);
      else if (e.key === "End") goTo(pageCount - 1);
      else if (e.key.toLowerCase() === "f") toggleFullscreen();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, goTo, pageCount]);

  React.useEffect(() => {
    function onFs() {
      setFullscreen(Boolean(document.fullscreenElement));
    }
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  function toggleFullscreen() {
    const el = containerRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      el.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  }

  function printCatalogue() {
    // Open the source PDF in a new tab — the browser's PDF reader
    // exposes its own print button. We don't auto-trigger print()
    // because cross-origin iframes block it.
    window.open(catalogueDownloadUrl(catalogue.id), "_blank");
  }

  // -----------------------------------------------------------------
  // Share.
  // -----------------------------------------------------------------
  const shareUrl =
    typeof window !== "undefined" ? window.location.href : "";

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

  // -----------------------------------------------------------------
  // Page-flip sound — synthesized via Web Audio so we don't ship an
  // asset. A short noise burst through a band-pass envelope sounds
  // close enough to a paper flip.
  // -----------------------------------------------------------------
  const audioCtxRef = React.useRef<AudioContext | null>(null);
  function playFlipSound() {
    try {
      type AnyAudioCtor = typeof AudioContext;
      const W = window as unknown as {
        AudioContext?: AnyAudioCtor;
        webkitAudioContext?: AnyAudioCtor;
      };
      const Ctor = W.AudioContext ?? W.webkitAudioContext;
      if (!Ctor) return;
      if (!audioCtxRef.current) audioCtxRef.current = new Ctor();
      const ctx = audioCtxRef.current;
      const duration = 0.18;
      const sampleRate = ctx.sampleRate;
      const length = Math.floor(sampleRate * duration);
      const buffer = ctx.createBuffer(1, length, sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < length; i++) {
        const t = i / length;
        const noise = Math.random() * 2 - 1;
        const env = Math.pow(1 - t, 2.5) * (0.3 + 0.7 * Math.exp(-t * 8));
        data[i] = noise * env * 0.5;
      }
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      const filter = ctx.createBiquadFilter();
      filter.type = "bandpass";
      filter.frequency.value = 2400;
      filter.Q.value = 0.9;
      const gain = ctx.createGain();
      gain.gain.value = 0.35;
      src.connect(filter);
      filter.connect(gain);
      gain.connect(ctx.destination);
      src.start();
    } catch {
      /* sound is best-effort */
    }
  }

  // -----------------------------------------------------------------
  // Size — fill the viewer body in BOTH dimensions. Compute the
  // largest page size that fits given the spread width factor (2 in
  // landscape, 1 in portrait).
  // -----------------------------------------------------------------
  const firstPage = pages[0];
  const aspect = firstPage
    ? firstPage.width / firstPage.height
    : 0.7071; // A4 portrait fallback

  const [size, setSize] = React.useState({ w: 420, h: 600 });
  React.useEffect(() => {
    function measure() {
      // Reserved vertical chrome (viewer top bar + progress bar +
      // small breathing room). The progress bar is hidden on
      // mobile so we get its 48px back for the page art.
      const reservedV = isMobile ? 52 + 16 : 52 + 48 + 16;
      // Horizontal: nav arrow circles (~56px) on each side on
      // desktop, plus tiny gutter; minimal padding on mobile.
      const reservedH = isMobile ? 16 : 144;
      const availH = Math.max(360, window.innerHeight - reservedV);
      const availW = Math.max(320, window.innerWidth - reservedH);
      const spread = isMobile ? 1 : 2;
      const hByWidth = (availW / spread) / aspect;
      const hByHeight = availH;
      const h = Math.floor(Math.min(hByWidth, hByHeight));
      const w = Math.floor(h * aspect);
      setSize({ w, h });
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [aspect, isMobile]);

  // Force the flipbook to remount when the device mode flips —
  // ``usePortrait`` is read once in componentDidMount and won't
  // react to a prop change otherwise.
  const flipBookKey = isMobile ? "portrait" : "landscape";

  const ready = FlipBookComp !== null && pageCount > 0;

  return (
    <main
      ref={containerRef}
      className={cn(
        // Calaméo-style dark theatre. ``fixed inset-0`` makes the
        // viewer cover the parent ``/offers`` layout header — the
        // catalogue should feel like a full-bleed app, not a panel
        // nested under site chrome.
        "fixed inset-0 z-50 flex w-full flex-col bg-gradient-to-b from-zinc-900 via-zinc-950 to-black text-zinc-100",
        fullscreen && "h-screen"
      )}
    >
      {/* ----- Top toolbar ----- */}
      <header className="relative z-20 flex items-center gap-2 border-b border-white/5 bg-black/40 px-3 py-2 backdrop-blur sm:px-5">
        <Link
          href="/offers"
          className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-300 hover:text-white"
        >
          <ArrowLeft className="h-3 w-3" />
          Offers
        </Link>
        <div className="min-w-0 flex-1 px-2">
          <p className="truncate text-sm font-semibold">{catalogue.title}</p>
          <PageReadout
            pageIndex={pageIndex}
            pageCount={pageCount}
            isMobile={isMobile}
          />
        </div>

        {/* Page navigation / view group — full set on desktop, trimmed on mobile */}
        <div className="hidden items-center gap-0.5 sm:flex">
          <IconButton
            label="Thumbnails"
            icon={LayoutGrid}
            onClick={() => {
              setOutlineOpen(false);
              setThumbsOpen((v) => !v);
            }}
            active={thumbsOpen}
          />
          <IconButton
            label="Page list"
            icon={List}
            onClick={() => {
              setThumbsOpen(false);
              setOutlineOpen((v) => !v);
            }}
            active={outlineOpen}
          />
          <IconButton
            label="First page"
            icon={ChevronsLeft}
            onClick={() => goTo(0)}
            disabled={pageIndex === 0}
          />
          <IconButton
            label="Last page"
            icon={ChevronsRight}
            onClick={() => goTo(pageCount - 1)}
            disabled={pageIndex >= pageCount - 1}
          />
          <span className="mx-1 h-5 w-px bg-white/10" aria-hidden />
          <IconButton
            label="Zoom out"
            icon={ZoomOut}
            onClick={() => setZoom((z) => clampZoom(z - 0.15))}
            disabled={zoom <= MIN_ZOOM + 0.001}
          />
          <span className="inline-flex w-11 items-center justify-center font-mono text-[11px] text-zinc-300">
            {Math.round(zoom * 100)}%
          </span>
          <IconButton
            label="Zoom in"
            icon={ZoomIn}
            onClick={() => setZoom((z) => clampZoom(z + 0.15))}
            disabled={zoom >= MAX_ZOOM - 0.001}
          />
          <span className="mx-1 h-5 w-px bg-white/10" aria-hidden />
          <IconButton
            label="Print"
            icon={Printer}
            onClick={printCatalogue}
          />
        </div>

        {/* Always-visible group (mobile too) */}
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
          as="a"
          href={catalogueDownloadUrl(catalogue.id)}
        />
        <IconButton
          label={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          icon={fullscreen ? Minimize2 : Maximize2}
          onClick={toggleFullscreen}
        />
        {/* Mobile-only quick thumbnails button */}
        <div className="sm:hidden">
          <IconButton
            label="Thumbnails"
            icon={LayoutGrid}
            onClick={() => setThumbsOpen((v) => !v)}
            active={thumbsOpen}
          />
        </div>
      </header>

      {/* ----- Viewer body ----- */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden">
        {!ready ? (
          <p className="text-sm text-zinc-400">
            {pageCount === 0 ? "No pages to display." : "Loading viewer…"}
          </p>
        ) : (
          <div
            className="transition-transform duration-200"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: "center",
            }}
          >
            {FlipBookComp ? (
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              React.createElement(FlipBookComp as any, {
                key: flipBookKey,
                ref: flipBookRef,
                width: size.w,
                height: size.h,
                size: "fixed",
                minWidth: 280,
                maxWidth: 1600,
                minHeight: 380,
                maxHeight: 2000,
                maxShadowOpacity: 0.5,
                showCover: true,
                mobileScrollSupport: false,
                drawShadow: true,
                flippingTime: 650,
                usePortrait: isMobile,
                startZIndex: 0,
                autoSize: false,
                clickEventForward: true,
                useMouseEvents: true,
                swipeDistance: 20,
                showPageCorners: true,
                disableFlipByClick: false,
                startPage: 0,
                style: {},
                className: "",
                onFlip: (e: { data: number }) => {
                  setPageIndex(e.data);
                  playFlipSound();
                },
                children: pages.map((p) => (
                  <FlipPage
                    key={p.page_number}
                    page={p}
                    width={size.w}
                    height={size.h}
                  />
                )),
              })
            ) : null}
          </div>
        )}

        {/* Nav arrows — visible on all sizes so mobile gets explicit
            controls in addition to the swipe gesture. */}
        {ready && (
          <>
            <NavArrow
              direction="prev"
              onClick={prev}
              disabled={pageIndex === 0}
            />
            <NavArrow
              direction="next"
              onClick={next}
              disabled={pageIndex >= pageCount - 1}
            />
          </>
        )}
      </div>

      {/* ----- Bottom progress bar (hidden on mobile — phones have
          the swipe gesture + on-screen page indicator) ----- */}
      {pageCount > 0 && (
        <div className="hidden sm:block">
          <ProgressBar
            pageIndex={pageIndex}
            pageCount={pageCount}
            onSeek={goTo}
          />
        </div>
      )}

      {thumbsOpen && (
        <ThumbnailGrid
          pages={pages}
          currentIndex={pageIndex}
          onJump={goTo}
          onClose={() => setThumbsOpen(false)}
        />
      )}
      {outlineOpen && (
        <OutlinePanel
          pages={pages}
          currentIndex={pageIndex}
          onJump={goTo}
          onClose={() => setOutlineOpen(false)}
        />
      )}
    </main>
  );
}


// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const FlipPage = React.forwardRef<
  HTMLDivElement,
  { page: CataloguePage; width: number; height: number }
>(function FlipPage({ page, width, height }, ref) {
  return (
    <div
      ref={ref}
      className="overflow-hidden bg-white shadow-2xl shadow-black/50"
      style={{ width, height }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={resolveAssetUrl(page.image_url) ?? ""}
        alt={`Page ${page.page_number}`}
        className="h-full w-full object-contain"
        loading={page.page_number <= 4 ? "eager" : "lazy"}
        draggable={false}
      />
    </div>
  );
});


function PageReadout({
  pageIndex,
  pageCount,
  isMobile,
}: {
  pageIndex: number;
  pageCount: number;
  isMobile: boolean;
}) {
  if (pageCount === 0) {
    return <p className="text-[11px] text-zinc-400">No pages</p>;
  }
  if (!isMobile && pageIndex > 0 && pageIndex < pageCount - 1) {
    return (
      <p className="text-[11px] text-zinc-400">
        Pages {pageIndex + 1}–{Math.min(pageIndex + 2, pageCount)} of {pageCount}
      </p>
    );
  }
  return (
    <p className="text-[11px] text-zinc-400">
      Page {pageIndex + 1} of {pageCount}
    </p>
  );
}


function ProgressBar({
  pageIndex,
  pageCount,
  onSeek,
}: {
  pageIndex: number;
  pageCount: number;
  onSeek: (i: number) => void;
}) {
  return (
    <div className="relative z-10 flex items-center gap-3 border-t border-white/5 bg-black/60 px-4 py-2 backdrop-blur sm:px-6">
      <span className="font-mono text-[11px] text-zinc-300">
        {pageIndex + 1}
      </span>
      <input
        type="range"
        min={0}
        max={Math.max(0, pageCount - 1)}
        value={pageIndex}
        onChange={(e) => onSeek(Number(e.target.value))}
        aria-label="Jump to page"
        className="flex-1 cursor-pointer accent-pug-gold-400"
      />
      <span className="font-mono text-[11px] text-zinc-300">{pageCount}</span>
    </div>
  );
}


function ThumbnailGrid({
  pages,
  currentIndex,
  onJump,
  onClose,
}: {
  pages: CataloguePage[];
  currentIndex: number;
  onJump: (i: number) => void;
  onClose: () => void;
}) {
  return (
    <div
      className="absolute inset-0 z-30 flex flex-col bg-black/85 backdrop-blur"
      role="dialog"
      aria-label="Catalogue pages"
    >
      <header className="flex items-center justify-between border-b border-white/10 px-4 py-2.5 sm:px-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-300">
          All pages ({pages.length})
        </p>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full p-1 text-zinc-300 hover:text-white"
          aria-label="Close thumbnails"
        >
          <X className="h-4 w-4" />
        </button>
      </header>
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8">
          {pages.map((p, i) => (
            <button
              key={p.page_number}
              type="button"
              onClick={() => onJump(i)}
              className={cn(
                "group block overflow-hidden rounded border bg-zinc-800 transition-all",
                i === currentIndex
                  ? "border-pug-gold-300 ring-2 ring-pug-gold-300/40"
                  : "border-white/10 opacity-80 hover:opacity-100"
              )}
              aria-label={`Jump to page ${p.page_number}`}
              title={`Page ${p.page_number}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={resolveAssetUrl(p.thumbnail_url) ?? ""}
                alt=""
                className="aspect-[2/3] w-full bg-white object-cover"
                loading="lazy"
              />
              <p className="px-1 py-0.5 text-center text-[10px] text-zinc-300">
                {p.page_number}
              </p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}


function OutlinePanel({
  pages,
  currentIndex,
  onJump,
  onClose,
}: {
  pages: CataloguePage[];
  currentIndex: number;
  onJump: (i: number) => void;
  onClose: () => void;
}) {
  return (
    <div
      className="absolute right-0 top-0 z-30 flex h-full w-72 flex-col border-l border-white/10 bg-black/90 backdrop-blur"
      role="dialog"
      aria-label="Page list"
    >
      <header className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-300">
          Pages
        </p>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full p-1 text-zinc-300 hover:text-white"
          aria-label="Close page list"
        >
          <X className="h-4 w-4" />
        </button>
      </header>
      <ul className="flex-1 overflow-y-auto py-1">
        {pages.map((p, i) => (
          <li key={p.page_number}>
            <button
              type="button"
              onClick={() => onJump(i)}
              className={cn(
                "flex w-full items-center gap-3 px-4 py-2 text-left text-sm transition-colors",
                i === currentIndex
                  ? "bg-white/10 text-white"
                  : "text-zinc-300 hover:bg-white/5 hover:text-white"
              )}
            >
              <span className="inline-flex h-6 w-8 items-center justify-center rounded bg-white/5 font-mono text-[11px]">
                {p.page_number}
              </span>
              <span className="text-[12px] text-zinc-400">
                Page {p.page_number}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Small UI primitives
// ---------------------------------------------------------------------------

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 1.6;
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
  | { as: "a"; href: string }
);


function IconButton(props: IconButtonProps) {
  const { label, icon: Icon, onClick, disabled, active } = props;
  const className = cn(
    "inline-flex h-9 w-9 items-center justify-center rounded-md text-zinc-200 transition-colors",
    active && "bg-white/10 text-white",
    disabled
      ? "cursor-not-allowed opacity-30"
      : "hover:bg-white/10 hover:text-white"
  );
  if (props.as === "a" && props.href) {
    return (
      <a
        href={props.href}
        className={className}
        aria-label={label}
        title={label}
        target="_blank"
        rel="noreferrer"
      >
        <Icon className="h-4 w-4" />
      </a>
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
        "absolute top-1/2 z-10 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full border border-white/10 bg-black/50 text-zinc-100 shadow-lg backdrop-blur transition-all sm:h-14 sm:w-14",
        direction === "prev" ? "left-2 sm:left-5" : "right-2 sm:right-5",
        disabled
          ? "cursor-not-allowed opacity-25"
          : "hover:bg-black/80 hover:text-white"
      )}
    >
      <Icon className="h-6 w-6 sm:h-7 sm:w-7" />
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
      className="absolute right-0 top-full mt-2 w-52 overflow-hidden rounded-lg border border-white/10 bg-black/95 text-sm shadow-2xl backdrop-blur"
    >
      <a
        href={whatsAppUrl}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-2 px-3 py-2 text-zinc-100 hover:bg-white/10"
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
        className="flex items-center gap-2 px-3 py-2 text-zinc-100 hover:bg-white/10"
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
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-zinc-100 hover:bg-white/10"
        role="menuitem"
      >
        <Copy className="h-3.5 w-3.5" />
        Copy link
      </button>
    </div>
  );
}
