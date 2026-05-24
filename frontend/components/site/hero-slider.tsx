"use client";

import * as React from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ChevronDown, Pause, Play } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { HeroSlide } from "@/lib/admin/types";
import { resolveAssetUrl } from "@/lib/public-api";
import { cn } from "@/lib/utils";

interface HeroSliderProps {
  slides: HeroSlide[];
  intervalMs?: number;
}

export function HeroSlider({ slides, intervalMs = 6500 }: HeroSliderProps) {
  const [index, setIndex] = React.useState(0);
  const [paused, setPaused] = React.useState(false);

  React.useEffect(() => {
    if (paused || slides.length <= 1) return;
    const t = setTimeout(() => {
      setIndex((i) => (i + 1) % slides.length);
    }, intervalMs);
    return () => clearTimeout(t);
  }, [index, paused, intervalMs, slides.length]);

  if (slides.length === 0) return null;
  const slide = slides[Math.min(index, slides.length - 1)];
  const videoUrl = resolveAssetUrl(slide.background_video_url);
  const imageUrl = resolveAssetUrl(slide.background_image_url);

  return (
    <section
      aria-roledescription="carousel"
      aria-label="Featured stories"
      className="relative isolate overflow-hidden"
    >
      {/* Background layer: video > image > gradient */}
      <AnimatePresence mode="wait">
        <motion.div
          key={`bg-${slide.id}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.8 }}
          aria-hidden
          className="absolute inset-0 -z-10"
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

      {/* Dim overlay so text stays legible over imagery */}
      {(videoUrl || imageUrl) && (
        <div
          aria-hidden
          className="absolute inset-0 -z-10 bg-gradient-to-br from-pug-green-900/70 via-pug-green-800/55 to-pug-gold-700/45"
        />
      )}
      <div
        aria-hidden
        className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,rgba(255,255,255,0.18),transparent_60%)]"
      />
      <div
        aria-hidden
        className="absolute inset-x-0 bottom-0 -z-10 h-40 bg-gradient-to-b from-transparent to-background"
      />

      <div className="container mx-auto flex min-h-[78vh] flex-col justify-center px-4 py-20 text-white sm:min-h-[88vh] sm:py-28">
        <AnimatePresence mode="wait">
          <motion.div
            key={slide.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="max-w-3xl"
          >
            <span className="inline-flex items-center rounded-full border border-white/30 bg-white/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] backdrop-blur">
              {slide.eyebrow}
            </span>
            <h1 className="mt-5 text-balance text-4xl font-semibold leading-[1.05] tracking-tight drop-shadow-sm sm:text-5xl lg:text-6xl">
              {slide.title}
            </h1>
            <p className="mt-4 max-w-2xl text-pretty text-base text-white/90 sm:text-lg">
              {slide.description}
            </p>

            <div className="mt-7 flex flex-wrap gap-3">
              {slide.cta_label && slide.cta_href && (
                <Button
                  asChild
                  size="lg"
                  className="bg-white text-foreground hover:bg-white/90"
                >
                  <Link href={slide.cta_href}>
                    {slide.cta_label}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              )}
              {slide.secondary_cta_label && slide.secondary_cta_href && (
                <Button
                  asChild
                  size="lg"
                  variant="outline"
                  className="border-white/40 bg-white/0 text-white hover:bg-white/10 hover:text-white"
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
                  "h-1.5 rounded-full transition-all",
                  i === index
                    ? "w-8 bg-white"
                    : "w-4 bg-white/40 hover:bg-white/60"
                )}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            className="inline-flex items-center gap-2 rounded-full border border-white/30 bg-white/10 px-3 py-1.5 text-xs font-medium backdrop-blur hover:bg-white/20"
            aria-label={paused ? "Play slideshow" : "Pause slideshow"}
          >
            {paused ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
            {paused ? "Play" : "Pause"}
          </button>
        </div>
      </div>

      <div
        aria-hidden
        className="absolute inset-x-0 bottom-4 z-10 flex justify-center text-white/80"
      >
        <ChevronDown className="h-5 w-5 animate-bounce" />
      </div>
    </section>
  );
}
