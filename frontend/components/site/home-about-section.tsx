"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import {
  motion,
  useScroll,
  useTransform,
  useReducedMotion,
} from "framer-motion";

import { GlassCard } from "@/components/site/glass-card";
import { Reveal } from "@/components/site/reveal";
import { Section } from "@/components/site/section";
import { Button } from "@/components/ui/button";
import { resolveAssetUrl } from "@/lib/public-api";

interface HomeAboutSectionProps {
  imageUrl: string | null;
  title: string | null;
  body: string | null;
}

/**
 * Home "About the group" split section.
 *
 * Left column: photo card with a soft, scroll-linked parallax — the
 * image shifts ~40px slower than the page as the section enters and
 * exits the viewport, which gives the layout depth without yanking
 * the eye around. Two ambient brand-glow orbs sit behind the card.
 *
 * Right column: text content that slides in from the right when the
 * section first reaches the viewport.
 *
 * Both effects degrade to plain static rendering when
 * `prefers-reduced-motion: reduce` is set.
 */
export function HomeAboutSection({
  imageUrl,
  title,
  body,
}: HomeAboutSectionProps) {
  const reduceMotion = useReducedMotion();
  const sectionRef = React.useRef<HTMLDivElement | null>(null);
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start end", "end start"],
  });
  const imageY = useTransform(scrollYProgress, [0, 1], ["-6%", "6%"]);
  const orbY = useTransform(scrollYProgress, [0, 1], ["10%", "-10%"]);

  if (!title && !body && !imageUrl) return null;
  const image = resolveAssetUrl(imageUrl);

  return (
    <Section className="py-16 sm:py-20">
      <div
        ref={sectionRef}
        className="grid items-center gap-10 lg:grid-cols-[1.1fr_1fr]"
      >
        <Reveal direction="left" className="relative">
          {image ? (
            <GlassCard className="relative overflow-hidden p-0">
              <div className="relative aspect-[4/3] w-full overflow-hidden">
                <motion.img
                  src={image}
                  alt={title ?? "About Paris United Group"}
                  loading="lazy"
                  style={{ y: reduceMotion ? 0 : imageY, scale: 1.08 }}
                  className="absolute inset-0 h-full w-full object-cover will-change-transform"
                />
              </div>
            </GlassCard>
          ) : (
            <GlassCard className="aspect-[4/3] w-full bg-gradient-to-br from-pug-green-500/40 via-pug-gold-500/30 to-pug-green-700/30" />
          )}
          <motion.div
            aria-hidden
            style={{ y: reduceMotion ? 0 : orbY }}
            className="pointer-events-none absolute -bottom-6 -right-6 h-32 w-32 rounded-full bg-pug-gold-500/20 blur-3xl"
          />
          <motion.div
            aria-hidden
            style={{ y: reduceMotion ? 0 : imageY }}
            className="pointer-events-none absolute -left-6 -top-6 h-32 w-32 rounded-full bg-pug-green-600/20 blur-3xl"
          />
        </Reveal>

        <Reveal direction="right" delay={0.08}>
          <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            About the group
          </span>
          {title && (
            <h2 className="mt-4 text-balance text-2xl font-semibold tracking-tight sm:text-3xl lg:text-4xl">
              {title}
            </h2>
          )}
          {body && (
            <p className="mt-4 whitespace-pre-line text-pretty text-muted-foreground sm:text-lg">
              {body}
            </p>
          )}
          <div className="mt-6">
            <Button asChild variant="outline">
              <Link href="/about">
                Read our story
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </Reveal>
      </div>
    </Section>
  );
}
