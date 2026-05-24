"use client";

import * as React from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  MousePointer2,
  Pause,
  Play,
  Sparkles,
  Stars,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import type { HeroSlide } from "@/lib/admin/types";
import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";

interface HeroSliderProps {
  slides: HeroSlide[];
  intervalMs?: number;
}

/**
 * Premium homepage hero.
 *
 * What changed in this iteration:
 *   - "Cute" headline: the last 2–3 words of every slide title are
 *     rendered with a brand gold→green gradient, and a sparkle bobs
 *     softly next to the eyebrow. The badge gets an animated dot.
 *   - Modern scroll behaviour: parallax-style background drift,
 *     hero text fades + scales gently as you scroll past, and the
 *     down-chevron is replaced with a little Apple-style mouse with
 *     a falling dot.
 *   - Theme-aware accents: chrome (badge / pause button / scroll
 *     indicator border) follows light + dark via CSS variables. The
 *     foreground text stays white because every slide always sits on
 *     a dark video / image / dimmed-gradient backdrop.
 *   - Respects prefers-reduced-motion: all scroll-driven movement
 *     is disabled and CSS animations short-circuit.
 *
 * No new dependencies — uses the existing framer-motion + GSAP that
 * ship with the rest of the site (GSAP is loaded async).
 */
export function HeroSlider({ slides, intervalMs = 6500 }: HeroSliderProps) {
  const [index, setIndex] = React.useState(0);
  const [paused, setPaused] = React.useState(false);
  const sectionRef = React.useRef<HTMLElement | null>(null);
  const bgRef = React.useRef<HTMLDivElement | null>(null);
  const contentRef = React.useRef<HTMLDivElement | null>(null);

  // Auto-advance the slider.
  React.useEffect(() => {
    if (paused || slides.length <= 1) return;
    const t = setTimeout(() => {
      setIndex((i) => (i + 1) % slides.length);
    }, intervalMs);
    return () => clearTimeout(t);
  }, [index, paused, intervalMs, slides.length]);

  // Scroll-driven effects: parallax on background, gentle fade/scale on
  // the foreground content. Loads GSAP only when the hero is mounted.
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (reducedMotion) return;

    let cancelled = false;
    let cleanup: (() => void) | undefined;

    (async () => {
      const { gsap } = await import("gsap");
      const { ScrollTrigger } = await import("gsap/ScrollTrigger");
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);

      const section = sectionRef.current;
      const bg = bgRef.current;
      const content = contentRef.current;
      if (!section) return;

      const ctx = gsap.context(() => {
        // Parallax: the background drifts up slightly slower than the
        // viewport — gives that Apple/Stripe depth feeling.
        if (bg) {
          gsap.to(bg, {
            yPercent: 18,
            ease: "none",
            scrollTrigger: {
              trigger: section,
              start: "top top",
              end: "bottom top",
              scrub: 0.4,
            },
          });
        }
        // Foreground fades out and gently shrinks as the user scrolls
        // past the hero. Translates a touch upwards for a graceful exit.
        if (content) {
          gsap.to(content, {
            opacity: 0,
            scale: 0.95,
            y: -40,
            ease: "none",
            scrollTrigger: {
              trigger: section,
              start: "top top",
              end: "bottom 35%",
              scrub: 0.5,
            },
          });
        }
      }, section);

      cleanup = () => ctx.revert();
    })();

    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, []);

  if (slides.length === 0) return null;
  const slide = slides[Math.min(index, slides.length - 1)];
  const videoUrl = resolveAssetUrl(slide.background_video_url);
  const imageUrl = resolveAssetUrl(slide.background_image_url);

  return (
    <section
      ref={sectionRef}
      aria-roledescription="carousel"
      aria-label="Featured stories"
      className="relative isolate overflow-hidden"
    >
      {/* Background layer: video > image > gradient. Wrapped in an extra
          div so we can parallax-translate the whole thing without
          fighting the slide cross-fade. */}
      <div
        ref={bgRef}
        aria-hidden
        className="absolute inset-0 -z-10 will-change-transform"
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={`bg-${slide.id}`}
            initial={{ opacity: 0, scale: 1.05 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{
              opacity: { duration: 0.9 },
              scale: { duration: 7, ease: "easeOut" },
            }}
            aria-hidden
            className="absolute inset-0"
          >
            {videoUrl ? (
              <video
                key={videoUrl}
                src={videoUrl}
                autoPlay
                loop
                muted
                playsInline
                preload="metadata"
                poster={imageUrl ?? undefined}
                className="h-full w-full object-cover"
              />
            ) : imageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={imageUrl}
                alt=""
                className="h-full w-full object-cover"
              />
            ) : (
              <div
                className={cn(
                  "h-full w-full bg-gradient-to-br",
                  slide.gradient
                )}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Dim overlay for legibility — slightly stronger in dark mode so
          the brand gradient on the headline still pops. */}
      {(videoUrl || imageUrl) && (
        <div
          aria-hidden
          className="absolute inset-0 -z-10 bg-gradient-to-br from-pug-green-900/70 via-pug-green-800/55 to-pug-gold-700/45 dark:from-pug-green-950/80 dark:via-pug-green-900/65 dark:to-pug-gold-800/45"
        />
      )}
      {/* Top-edge radial glow */}
      <div
        aria-hidden
        className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,rgba(255,255,255,0.18),transparent_60%)] dark:bg-[radial-gradient(ellipse_at_top,rgba(245,222,179,0.12),transparent_55%)]"
      />
      {/* Soft floating accent blobs — bob up/down. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="hero-orb hero-orb--gold absolute left-[8%] top-[18%] h-40 w-40 rounded-full bg-pug-gold-400/30 blur-3xl" />
        <div className="hero-orb hero-orb--green absolute right-[12%] top-[55%] h-56 w-56 rounded-full bg-pug-green-400/25 blur-3xl" />
      </div>
      {/* Bottom fade into the page background — adapts to theme via the
          `to-background` token. */}
      <div
        aria-hidden
        className="absolute inset-x-0 bottom-0 -z-10 h-40 bg-gradient-to-b from-transparent to-background"
      />

      <div
        ref={contentRef}
        className="container mx-auto flex min-h-[78vh] flex-col justify-center px-4 py-20 text-white sm:min-h-[88vh] sm:py-28"
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={slide.id}
            initial={{ opacity: 0, y: 24, filter: "blur(8px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -12, filter: "blur(4px)" }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            className="max-w-3xl"
          >
            {slide.eyebrow && (
              <span className="group relative inline-flex items-center gap-2 rounded-full border border-white/30 bg-white/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-white shadow-[0_2px_24px_-12px_rgba(255,255,255,0.4)] backdrop-blur">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-pug-gold-300 opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-pug-gold-400" />
                </span>
                <Sparkles
                  className="h-3 w-3 text-pug-gold-300 transition-transform group-hover:rotate-12"
                  aria-hidden
                />
                {slide.eyebrow}
              </span>
            )}
            <h1 className="mt-5 text-balance text-4xl font-semibold leading-[1.05] tracking-tight drop-shadow-sm sm:text-5xl lg:text-6xl">
              <CuteTitle text={slide.title} />
            </h1>
            {slide.description && (
              <p className="mt-4 max-w-2xl text-pretty text-base text-white/90 drop-shadow-sm sm:text-lg">
                {slide.description}
              </p>
            )}

            <div className="mt-7 flex flex-wrap gap-3">
              {slide.cta_label && slide.cta_href && (
                <Button
                  asChild
                  size="lg"
                  className="group bg-white text-pug-green-900 shadow-[0_8px_30px_-12px_rgba(255,255,255,0.5)] transition-all hover:-translate-y-0.5 hover:bg-white/95 hover:text-pug-green-950 hover:shadow-[0_12px_40px_-12px_rgba(255,255,255,0.6)] dark:text-pug-green-900 dark:hover:text-pug-green-950"
                >
                  <Link href={slide.cta_href}>
                    {slide.cta_label}
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </Link>
                </Button>
              )}
              {slide.secondary_cta_label && slide.secondary_cta_href && (
                <Button
                  asChild
                  size="lg"
                  variant="outline"
                  className="border-white/40 bg-white/5 text-white backdrop-blur transition-all hover:-translate-y-0.5 hover:bg-white/15 hover:text-white"
                >
                  <Link href={slide.secondary_cta_href}>
                    {slide.secondary_cta_label}
                  </Link>
                </Button>
              )}
            </div>
          </motion.div>
        </AnimatePresence>

        {/* Controls + indicators */}
        <div className="mt-12 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            {slides.map((s, i) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setIndex(i)}
                aria-label={`Go to slide ${i + 1}`}
                aria-current={i === index}
                className={cn(
                  "h-1.5 rounded-full transition-all duration-500",
                  i === index
                    ? "w-10 bg-gradient-to-r from-pug-gold-300 to-white shadow-[0_0_12px_-2px_rgba(255,255,255,0.7)]"
                    : "w-4 bg-white/40 hover:w-6 hover:bg-white/70"
                )}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            className="inline-flex items-center gap-2 rounded-full border border-white/30 bg-white/10 px-3 py-1.5 text-xs font-medium text-white backdrop-blur transition-colors hover:bg-white/20"
            aria-label={paused ? "Play slideshow" : "Pause slideshow"}
          >
            {paused ? (
              <Play className="h-3 w-3" />
            ) : (
              <Pause className="h-3 w-3" />
            )}
            {paused ? "Play" : "Pause"}
          </button>
        </div>
      </div>

      {/* Cute scroll indicator: little mouse outline with a dropping dot
          + "Scroll" label that pulses gently. */}
      <ScrollHint />
    </section>
  );
}


/**
 * Word-aware title: keeps everything but the last 2 words white, and
 * paints the last 2 words with a brand gold → green gradient. Falls
 * back to a single gradient word if the title has 2 words; falls back
 * to the full text gradient if there's only one word.
 */
function CuteTitle({ text }: { text: string }) {
  const words = text.trim().split(/\s+/);
  if (words.length <= 1) {
    return <span className="hero-gradient-text">{text}</span>;
  }
  const accentCount = words.length >= 4 ? 2 : 1;
  const head = words.slice(0, words.length - accentCount).join(" ");
  const tail = words.slice(words.length - accentCount).join(" ");
  return (
    <>
      {head}{" "}
      <span className="hero-gradient-text relative inline-block">
        {tail}
        <svg
          aria-hidden
          viewBox="0 0 200 12"
          className="absolute -bottom-1 left-0 h-2 w-full opacity-70"
          preserveAspectRatio="none"
        >
          <path
            d="M2 8 C 50 -2, 150 14, 198 4"
            stroke="url(#hero-underline)"
            strokeWidth="2.4"
            strokeLinecap="round"
            fill="none"
          />
          <defs>
            <linearGradient id="hero-underline" x1="0" x2="1" y1="0" y2="0">
              <stop offset="0%" stopColor="rgb(212, 175, 55)" />
              <stop offset="100%" stopColor="rgb(232, 232, 232)" />
            </linearGradient>
          </defs>
        </svg>
      </span>
    </>
  );
}


function ScrollHint() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-x-0 bottom-6 z-10 flex flex-col items-center gap-2 text-white/85"
    >
      <span className="hero-scroll-mouse relative flex h-9 w-5 items-start justify-center rounded-full border border-white/55 px-[5px] pt-1.5 backdrop-blur">
        <span className="hero-scroll-dot block h-1.5 w-1.5 rounded-full bg-white/95" />
      </span>
      <span className="text-[10px] font-medium uppercase tracking-[0.3em] text-white/75">
        Scroll
      </span>
    </div>
  );
}
