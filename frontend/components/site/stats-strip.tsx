"use client";

import * as React from "react";
import { motion, useInView } from "framer-motion";

import { GlassCard } from "@/components/site/glass-card";
import { STATS } from "@/lib/dummy-data/site-content";

export function StatsStrip() {
  return (
    <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {STATS.map((stat) => {
        const Icon = stat.icon;
        return (
          <li key={stat.label}>
            <GlassCard className="h-full p-5 text-center sm:text-left">
              <div className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Icon className="h-5 w-5" />
              </div>
              <div className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">
                <Counter target={stat.value} suffix={stat.suffix} />
              </div>
              <p className="mt-1 text-xs uppercase tracking-wide text-muted-foreground">
                {stat.label}
              </p>
            </GlassCard>
          </li>
        );
      })}
    </ul>
  );
}

function Counter({ target, suffix = "" }: { target: number; suffix?: string }) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const [value, setValue] = React.useState(0);

  React.useEffect(() => {
    if (!inView) return;
    const startTs = performance.now();
    const durationMs = Math.min(1400, 400 + Math.log10(target + 1) * 350);
    let raf = 0;

    function step(now: number) {
      const elapsed = now - startTs;
      const t = Math.min(1, elapsed / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(target * eased));
      if (t < 1) raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [inView, target]);

  return (
    <motion.span
      ref={ref}
      initial={{ opacity: 0 }}
      animate={{ opacity: inView ? 1 : 0 }}
      transition={{ duration: 0.4 }}
    >
      {value.toLocaleString()}
      {suffix}
    </motion.span>
  );
}
