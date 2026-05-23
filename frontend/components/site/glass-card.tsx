"use client";

import * as React from "react";
import { motion, type HTMLMotionProps } from "framer-motion";

import { cn } from "@/lib/utils";

type GlassCardProps = Omit<HTMLMotionProps<"div">, "children"> & {
  /** Disable the entry animation (useful in tests / SSR-heavy sections). */
  noAnimate?: boolean;
  children?: React.ReactNode;
};

export const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, noAnimate, children, ...rest }, ref) => {
    if (noAnimate) {
      return (
        <div ref={ref} className={cn("glass-card p-6", className)}>
          {children}
        </div>
      );
    }
    return (
      <motion.div
        ref={ref}
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.2 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        className={cn("glass-card p-6", className)}
        {...rest}
      >
        {children}
      </motion.div>
    );
  }
);
GlassCard.displayName = "GlassCard";
