"use client";

import * as React from "react";
import {
  motion,
  useReducedMotion,
  type HTMLMotionProps,
  type Variants,
} from "framer-motion";

import { cn } from "@/lib/utils";

type RevealDirection = "up" | "down" | "left" | "right" | "zoom" | "fade";

interface RevealProps
  extends Omit<HTMLMotionProps<"div">, "variants" | "children"> {
  /** Entry direction. Defaults to `up`. */
  direction?: RevealDirection;
  /** Starting offset distance in pixels (ignored for `fade` / `zoom`). */
  distance?: number;
  /** Delay before the animation starts, in seconds. */
  delay?: number;
  /** Animation duration in seconds. Defaults to `0.65`. */
  duration?: number;
  /**
   * Container vertical offset for the IntersectionObserver — negative
   * margins make the reveal trigger *before* the element fully enters
   * the viewport, which feels snappier.
   */
  rootMargin?: string;
  /** Animate once and stay, vs. re-animate on every entry. */
  once?: boolean;
  children?: React.ReactNode;
}

const distanceFor = (dir: RevealDirection, d: number) => {
  switch (dir) {
    case "up":
      return { y: d };
    case "down":
      return { y: -d };
    case "left":
      return { x: d };
    case "right":
      return { x: -d };
    case "zoom":
      return { scale: 0.94 };
    case "fade":
    default:
      return {};
  }
};

/**
 * Lightweight scroll-into-view reveal wrapper.
 *
 * Wraps children in a `motion.div` that fades + slides into place the
 * first time it enters the viewport. Designed to be sprinkled across
 * marketing pages (home, about, careers, etc.) without each section
 * having to wire its own IntersectionObserver / framer config.
 *
 * Respects `prefers-reduced-motion` — under that setting the children
 * render in their resting state with no transition at all.
 *
 * Pair with `<RevealGroup>` (sibling component below) when staggering
 * a list of cards.
 */
export function Reveal({
  direction = "up",
  distance = 28,
  delay = 0,
  duration = 0.65,
  rootMargin = "-80px",
  once = true,
  className,
  children,
  ...rest
}: RevealProps) {
  const reduceMotion = useReducedMotion();
  if (reduceMotion) {
    return (
      <div className={cn(className)} {...(rest as React.HTMLAttributes<HTMLDivElement>)}>
        {children}
      </div>
    );
  }

  const offset = distanceFor(direction, distance);

  return (
    <motion.div
      initial={{ opacity: 0, ...offset }}
      whileInView={{ opacity: 1, x: 0, y: 0, scale: 1 }}
      viewport={{ once, margin: rootMargin }}
      transition={{
        duration,
        delay,
        ease: [0.21, 0.61, 0.35, 1],
      }}
      className={cn(className)}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

interface RevealGroupProps
  extends Omit<HTMLMotionProps<"div">, "variants" | "children"> {
  /** Delay between each direct child's animation start. */
  stagger?: number;
  /** Initial delay before the first child animates. */
  delay?: number;
  /** Entry direction shared by every child. */
  direction?: RevealDirection;
  distance?: number;
  rootMargin?: string;
  once?: boolean;
  /** Per-child duration. */
  duration?: number;
  children?: React.ReactNode;
}

/**
 * Stagger-aware reveal container.
 *
 * Each direct child fades+slides into place sequentially as the group
 * enters the viewport. Children don't need any extra markup — the
 * stagger is driven by Framer Motion variants on the parent.
 *
 * Falls back to a plain `div` (no motion, no opacity flicker) when
 * `prefers-reduced-motion: reduce` is set.
 */
export function RevealGroup({
  stagger = 0.08,
  delay = 0,
  direction = "up",
  distance = 24,
  rootMargin = "-80px",
  once = true,
  duration = 0.6,
  className,
  children,
  ...rest
}: RevealGroupProps) {
  const reduceMotion = useReducedMotion();
  if (reduceMotion) {
    return (
      <div className={cn(className)} {...(rest as React.HTMLAttributes<HTMLDivElement>)}>
        {children}
      </div>
    );
  }

  const offset = distanceFor(direction, distance);

  const container: Variants = {
    hidden: {},
    show: {
      transition: {
        delayChildren: delay,
        staggerChildren: stagger,
      },
    },
  };

  const item: Variants = {
    hidden: { opacity: 0, ...offset },
    show: {
      opacity: 1,
      x: 0,
      y: 0,
      scale: 1,
      transition: { duration, ease: [0.21, 0.61, 0.35, 1] },
    },
  };

  // React children may include falsy entries (e.g. `cond && <X/>`).
  // Filter so we don't wrap nulls — that'd create empty motion slots
  // and visibly waste stagger ticks on nothing.
  const items = React.Children.toArray(children).filter(Boolean);

  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once, margin: rootMargin }}
      variants={container}
      className={cn(className)}
      {...rest}
    >
      {items.map((child, idx) => (
        <motion.div key={idx} variants={item}>
          {child}
        </motion.div>
      ))}
    </motion.div>
  );
}
