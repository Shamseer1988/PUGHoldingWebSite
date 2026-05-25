"use client";

import { motion } from "framer-motion";

import { TIMELINE, type TimelineEntry } from "@/lib/dummy-data/site-content";

interface TimelineProps {
  entries?: TimelineEntry[];
}

export function Timeline({ entries = TIMELINE }: TimelineProps) {
  return (
    <ol className="relative ml-3 border-l border-border/60 pl-6 sm:ml-6">
      {entries.map((entry, index) => (
        <motion.li
          key={entry.year}
          initial={{ opacity: 0, x: -8 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 0.4, delay: index * 0.05 }}
          className="relative pb-8 last:pb-0"
        >
          <span
            aria-hidden
            className="absolute -left-[33px] top-1.5 inline-flex h-6 w-6 items-center justify-center rounded-full border-2 border-background bg-primary text-[10px] font-semibold text-primary-foreground shadow-md"
          >
            ●
          </span>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-primary">
            {entry.year}
          </p>
          <h3 className="mt-1 text-lg font-semibold tracking-tight">
            {entry.title}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {entry.description}
          </p>
        </motion.li>
      ))}
    </ol>
  );
}
