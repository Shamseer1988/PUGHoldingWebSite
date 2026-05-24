"use client";

import * as React from "react";
import { motion, useScroll, useSpring, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";

/**
 * Site-wide scroll-progress indicator.
 *
 * A 2-pixel gradient bar pinned to the top of the viewport that
 * fills left → right as the user scrolls the page. Powered by
 * Framer Motion's `useScroll` + a soft spring so the bar never feels
 * jittery, even on a trackpad. Respects `prefers-reduced-motion` by
 * snapping to the raw progress with no spring overshoot.
 *
 * Visual: warm gold → emerald, matching the brand-gold-shift used in
 * the hero. Sits above the navbar via z-50 so it's always visible.
 *
 * Mount once at the layout root — no props required.
 */
export function ScrollProgressBar({ className }: { className?: string }) {
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 140,
    damping: 24,
    mass: 0.4,
    restDelta: 0.001,
  });

  return (
    <motion.div
      aria-hidden
      style={{ scaleX: reduceMotion ? scrollYProgress : scaleX, transformOrigin: "0% 50%" }}
      className={cn(
        "fixed inset-x-0 top-0 z-[60] h-[2px] origin-left",
        "bg-gradient-to-r from-amber-400 via-orange-400 to-emerald-500",
        "shadow-[0_0_12px_rgba(251,191,36,0.4)]",
        className
      )}
    />
  );
}
