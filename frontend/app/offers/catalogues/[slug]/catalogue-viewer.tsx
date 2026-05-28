"use client";

import * as React from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
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
import { resolveAssetUrl } from "@/lib/public-api";
import {
  catalogueDownloadUrl,
  detectDevice,
  getOrCreateSessionId,
  logCatalogueView,
} from "@/lib/public-offers-client";
import { cn } from "@/lib/utils";


// react-pageflip is a client-only library that touches DOM refs on
// mount. Wrap it in next/dynamic with ssr:false so the bundle stays
// server-renderable and the flipbook hydrates after the catalogue
// detail has loaded.
const HTMLFlipBook = dynamic(() => import("react-pageflip"), {
  ssr: false,
});


interface Props {
  catalogue: CatalogueDetail;
}


export function CatalogueViewer({ catalogue }: Props) {
  const [pageIndex, setPageIndex] = React.useState(0);
  const [thumbsOpen, setThumbsOpen] = React.useState(false);
  const [shareOpen, setShareOpen] = React.useState(false);
  const [fullscreen, setFullscreen] = React.useState(false);
  const [isMobile, setIsMobile] = React.useState(false);
  const [zoom, setZoom] = React.useState(1);

  const containerRef = React.useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const flipBookRef = React.useRef<any>(null);

  const pages = catalogue.pages;
  const pageCount = pages.length;

  // -----------------------------------------------------------------
  // Mobile detect (Tailwind ``md`` breakpoint)
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
  // Analytics — beacon on open + on close with duration
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
  // Keyboard
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageCount]);

  React.useEffect(() => {
    function onFs() {
      setFullscreen(Boolean(document.fullscreenElement));
    }
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  // -----------------------------------------------------------------
  // Page navigation — go through the flipbook ref on desktop so the
  // animation fires; fall back to direct state on mobile.
  // -----------------------------------------------------------------
  function next() {
    if (!isMobile && flipBookRef.current?.pageFlip) {
      flipBookRef.current.pageFlip().flipNext();
    } else {
      setPageIndex((i) => Math.min(pageCount - 1, i + 1));
    }
  }
  function prev() {
    if (!isMobile && flipBookRef.current?.pageFlip) {
      flipBookRef.current.pageFlip().flipPrev();
    } else {
      setPageIndex((i) => Math.max(0, i - 1));
    }
  }
  function goTo(idx: number) {
    const target = Math.max(0, Math.min(pageCount - 1, idx));
    if (!isMobile && flipBookRef.current?.pageFlip) {
      flipBookRef.current.pageFlip().flip(target);
    } else {
      setPageIndex(target);
    }
    setThumbsOpen(false);
  }

  function toggleFullscreen() {
    const el = containerRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      el.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  }

  // -----------------------------------------------------------------
  // Share
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
  // asset. A short noise burst through a band-pass + envelope sounds
  // close enough to a paper flip for the effect to feel real.
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
      // Decaying noise + slight upward tilt = paper rustle.
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
  // Page geometry for the flipbook — fit a two-page spread into the
  // viewport while honouring the source aspect ratio.
  // -----------------------------------------------------------------
  const firstPage = pages[0];
  const aspect = firstPage
    ? firstPage.width / firstPage.height
    : 0.7071; // A4
  // Pick a height that fits the viewer area (vh minus topbar minus a
  // little padding); width follows the aspect. SSR fallback: 720x1000.
  const [size, setSize] = React.useState({ w: 500, h: 700 });
  React.useEffect(() => {
    function measure() {
      // 3.5rem top bar (layout) + 3rem viewer top bar + 1.5rem padding
      const available = window.innerHeight - 56 - 56 - 24;
      const h = Math.max(400, Math.min(available, 1100));
      const w = Math.floor(h * aspect);
      setSize({ w, h });
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [aspect]);

  return (
    <main
      ref={containerRef}
      className={cn(
        // Calaméo-style dark theatre. The dark gradient frames the
        // page art and the brand-gold chevrons pop on the dark
        // backdrop.
        "relative flex w-full flex-col bg-gradient-to-b from-zinc-900 via-zinc-950 to-black text-zinc-100",
        fullscreen ? "h-screen" : "h-[calc(100vh-3.5rem)]"
      )}
    >
      {/* ----- Top bar ----- */}
      <header className="relative z-20 flex items-center gap-3 border-b border-white/5 bg-black/40 px-4 py-2.5 backdrop-blur sm:px-6">
        <Link
          href="/offers"
          className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-300 hover:text-white"
        >
          <ArrowLeft className="h-3 w-3" />
          Offers
        </Link>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{catalogue.title}</p>
          <PageReadout
            pageIndex={pageIndex}
            pageCount={pageCount}
            isMobile={isMobile}
          />
        </div>
        <div className="hidden gap-1 sm:flex">
          <IconButton
            label="Thumbnails"
            icon={LayoutGrid}
            onClick={() => setThumbsOpen((v) => !v)}
            active={thumbsOpen}
          />
          <IconButton
            label="Zoom out"
            icon={ZoomOut}
            onClick={() => setZoom((z) => clampZoom(z - 0.15))}
            disabled={zoom <= MIN_ZOOM + 0.001}
          />
          <span className="inline-flex w-12 items-center justify-center text-[11px] text-zinc-300">
            {Math.round(zoom * 100)}%
          </span>
          <IconButton
            label="Zoom in"
            icon={ZoomIn}
            onClick={() => setZoom((z) => clampZoom(z + 0.15))}
            disabled={zoom >= MAX_ZOOM - 0.001}
          />
        </div>
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
      <div className="relative flex flex-1 items-center justify-center overflow-hidden">
        {isMobile ? (
          <MobileScroller
            pages={pages}
            onActivePage={(n) => setPageIndex(n - 1)}
          />
        ) : pageCount > 0 ? (
          <div
            className="transition-transform duration-200"
            style={{ transform: `scale(${zoom})`, transformOrigin: "center" }}
          >
            {/* The cast keeps TS quiet about the dynamic import +
                ref typing. The library accepts any sane refs. */}
            <HTMLFlipBook
              ref={flipBookRef as never}
              width={size.w}
              height={size.h}
              size="stretch"
              minWidth={300}
              maxWidth={1200}
              minHeight={400}
              maxHeight={1600}
              maxShadowOpacity={0.5}
              showCover
              mobileScrollSupport={false}
              drawShadow
              flippingTime={650}
              usePortrait={false}
              startZIndex={0}
              autoSize={false}
              clickEventForward
              useMouseEvents
              swipeDistance={30}
              showPageCorners
              disableFlipByClick={false}
              startPage={0}
              style={{}}
              className=""
              onFlip={(e: { data: number }) => {
                setPageIndex(e.data);
                playFlipSound();
              }}
            >
              {pages.map((p) => (
                <FlipPage
                  key={p.page_number}
                  page={p}
                  width={size.w}
                  height={size.h}
                />
              ))}
            </HTMLFlipBook>
          </div>
        ) : (
          <p className="text-sm text-zinc-400">No pages to display.</p>
        )}

        {/* Nav arrows — desktop only; mobile uses native scroll. */}
        {!isMobile && (
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

      {/* ----- Bottom progress + thumbnail strip ----- */}
      {!isMobile && pageCount > 0 && (
        <ProgressBar
          pageIndex={pageIndex}
          pageCount={pageCount}
          onSeek={goTo}
        />
      )}
      {thumbsOpen && (
        <ThumbnailGrid
          pages={pages}
          currentIndex={pageIndex}
          onJump={goTo}
          onClose={() => setThumbsOpen(false)}
        />
      )}

      {/* Mobile page indicator */}
      {isMobile && (
        <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full border border-white/15 bg-black/60 px-3 py-1 text-[11px] text-zinc-200">
          Page {pageIndex + 1} of {pageCount}
        </div>
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
  // Desktop two-page spread except the cover (page 1 alone) and the
  // last page if it lands on a left-side slot.
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


function MobileScroller({
  pages,
  onActivePage,
}: {
  pages: CataloguePage[];
  onActivePage: (n: number) => void;
}) {
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
    return () => observer.current?.disconnect();
  }, [onActivePage]);

  const setRef = React.useCallback((el: HTMLDivElement | null) => {
    if (!el || !observer.current) return;
    observer.current.observe(el);
  }, []);

  return (
    <div className="flex h-full w-full snap-y snap-mandatory flex-col overflow-y-auto">
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
              src={resolveAssetUrl(p.image_url) ?? ""}
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


function ProgressBar({
  pageIndex,
  pageCount,
  onSeek,
}: {
  pageIndex: number;
  pageCount: number;
  onSeek: (i: number) => void;
}) {
  // Slider goes from 0 to pageCount-1. We let the browser handle the
  // pointer events; on change we jump to the page (which triggers the
  // flipbook's flipTo animation).
  return (
    <div className="absolute bottom-0 left-0 right-0 z-10 flex items-center gap-3 border-t border-white/5 bg-black/50 px-4 py-2 backdrop-blur sm:px-6">
      <span className="font-mono text-[11px] text-zinc-300">
        {pageIndex + 1}
      </span>
      <input
        type="range"
        min={0}
        max={pageCount - 1}
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
  | { as: typeof Link; href: string }
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
        "absolute top-1/2 z-10 flex h-14 w-14 -translate-y-1/2 items-center justify-center rounded-full border border-white/10 bg-black/40 text-zinc-100 backdrop-blur transition-all",
        direction === "prev" ? "left-3 sm:left-6" : "right-3 sm:right-6",
        disabled
          ? "cursor-not-allowed opacity-25"
          : "hover:bg-black/70 hover:text-white"
      )}
    >
      <Icon className="h-7 w-7" />
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
