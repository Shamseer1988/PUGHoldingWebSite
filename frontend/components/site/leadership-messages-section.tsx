"use client";

import * as React from "react";
import Link from "next/link";
import { motion, useReducedMotion, type Variants } from "framer-motion";
import { ArrowUpRight, Quote, Sparkles } from "lucide-react";

import { HeadingAccent } from "@/components/site/heading-accent";
import { Section } from "@/components/site/section";
import {
  normaliseMediaUrl,
  type HomepageLeadershipCard,
  type HomepageLeadershipSection,
} from "@/lib/public-api";
import { cn } from "@/lib/utils";


interface LeadershipMessagesSectionProps {
  data: HomepageLeadershipSection;
}

// Phase B-5 — framer-motion variants replacing the previous GSAP
// timeline. The card variant is dynamic (``i % 2`` decides whether
// the card slides in from the left or the right), and the inner
// elements (photo, quote, text, footer) cascade via nested staggers.
// The scrub-based background-glow parallax the GSAP version added is
// dropped — it was a marginal effect and would have required the
// framer-motion ``useScroll`` / ``useTransform`` machinery on top of
// the variants tree, which isn't worth the complexity.
const REVEAL_EASE = [0.16, 1, 0.3, 1] as const;
const BACK_EASE = [0.34, 1.56, 0.64, 1] as const; // approx GSAP back.out(2)

const ROOT_VARIANTS: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.18 } },
};

const HEADER_VARIANTS: Variants = {
  hidden: { opacity: 0, y: 36 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.8, ease: REVEAL_EASE } },
};

interface CardCustom {
  fromLeft: boolean;
  isDesktop: boolean;
}

const CARD_VARIANTS: Variants = {
  hidden: ({ fromLeft, isDesktop }: CardCustom) => ({
    x: isDesktop ? (fromLeft ? -90 : 90) : 0,
    y: isDesktop ? (fromLeft ? 40 : 70) : 40,
    rotate: isDesktop ? (fromLeft ? -1.5 : 1.5) : 0,
    scale: isDesktop ? 0.96 : 1,
    opacity: 0,
  }),
  visible: {
    x: 0,
    y: 0,
    rotate: 0,
    scale: 1,
    opacity: 1,
    transition: {
      duration: 1.05,
      ease: REVEAL_EASE,
      // Slight delay between the card slide-in and the inner
      // photo/quote/text reveals lining up with GSAP's at + 0.05/0.25/0.3
      // offsets. ``staggerChildren`` doesn't apply here because the
      // inner items have their own explicit ``delay``s.
    },
  },
};

const PHOTO_VARIANTS: Variants = {
  hidden: { clipPath: "inset(12% 12% 12% 12% round 28px)", scale: 1.08 },
  visible: {
    clipPath: "inset(0% 0% 0% 0% round 28px)",
    scale: 1,
    transition: { duration: 1.05, ease: REVEAL_EASE, delay: 0.05 },
  },
};

const QUOTE_VARIANTS: Variants = {
  hidden: { opacity: 0, rotate: -10, scale: 0.75 },
  visible: {
    opacity: 1,
    rotate: 0,
    scale: 1,
    transition: { duration: 0.55, ease: BACK_EASE, delay: 0.25 },
  },
};

const TEXT_CONTAINER_VARIANTS: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08, delayChildren: 0.3 },
  },
};

const TEXT_VARIANTS: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, ease: REVEAL_EASE },
  },
};

const FOOTER_VARIANTS: Variants = {
  hidden: { opacity: 0, y: 18 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: REVEAL_EASE, delay: 0.55 },
  },
};

function useIsDesktop(): boolean {
  const [isDesktop, setIsDesktop] = React.useState(false);
  React.useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(min-width: 768px)");
    const sync = () => setIsDesktop(mql.matches);
    sync();
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", sync);
      return () => mql.removeEventListener("change", sync);
    }
    mql.addListener(sync);
    return () => mql.removeListener(sync);
  }, []);
  return isDesktop;
}

/**
 * Unified homepage "Leadership Messages" section.
 *
 * Premium editorial layout — both Chairman and MD live inside this
 * single section as side-by-side cards on desktop and stacked cards
 * on mobile. The second card sits ~80px lower than the first on
 * desktop for an intentional asymmetric editorial rhythm.
 *
 * Each card is a two-column layout:
 *
 *   ┌─────────────┬───────────────────────────────┐
 *   │  portrait   │  role label                    │
 *   │  (medium-   │  name                          │
 *   │   large,    │  designation                   │
 *   │   220×280)  │                                │
 *   │             │  ─── quote rule ───            │
 *   │             │  "highlight quote"             │
 *   │             │  paragraph 1                   │
 *   │             │  paragraph 2                   │
 *   │             │  (footer w/ signature + cta)   │
 *   └─────────────┴───────────────────────────────┘
 *
 * Mobile collapses the portrait to a full-width top block (max
 * 280px tall, centered) and stacks the right column below.
 *
 * Animation — "Dual Portrait Leadership Reveal":
 *   - Section header fades up first.
 *   - Background glow drifts slowly with scroll (scrubbed).
 *   - Chairman card slides in from left, MD from right, with soft
 *     rotation + scale.
 *   - Portrait images reveal via clip-path inset from 12% → 0%
 *     while easing scale 1.08 → 1.
 *   - Quote glyph fades + rotates softly into place.
 *   - Inner text elements stagger up.
 *   - Signature + CTA reveal last.
 *
 * All theme tokens are CSS custom properties driven by Tailwind's
 * `dark:` variant so the section adapts to the existing global
 * theme system with no extra runtime code.
 */
export function LeadershipMessagesSection({
  data,
}: LeadershipMessagesSectionProps) {
  const prefersReducedMotion = useReducedMotion();
  const isDesktop = useIsDesktop();

  const messages = React.useMemo(
    () => data.messages.filter((m) => m.is_active),
    [data.messages]
  );

  const animationsOff = !data.animation_enabled || prefersReducedMotion;
  const initial = animationsOff ? "visible" : "hidden";

  if (!data.enabled || messages.length === 0) return null;

  const isSingle = messages.length === 1;

  return (
    <Section
      className={cn(
        "leadership-messages-section relative overflow-hidden py-16 sm:py-24",
        // Light theme tokens.
        "[--lms-bg:#f8f5ef]",
        "[--lms-card-bg:rgba(255,255,255,0.78)]",
        "[--lms-card-edge:rgba(255,255,255,0.6)]",
        "[--lms-text:#17382f]",
        "[--lms-muted:#61736b]",
        "[--lms-border:rgba(176,138,46,0.18)]",
        "[--lms-rule:rgba(23,56,47,0.10)]",
        "[--lms-accent:#b08a2e]",
        "[--lms-accent-soft:rgba(176,138,46,0.16)]",
        "[--lms-glow-a:rgba(176,138,46,0.18)]",
        "[--lms-glow-b:rgba(36,105,75,0.18)]",
        // Dark theme tokens.
        "dark:[--lms-bg:#06110d]",
        "dark:[--lms-card-bg:rgba(255,255,255,0.065)]",
        "dark:[--lms-card-edge:rgba(255,255,255,0.08)]",
        "dark:[--lms-text:#f5f1e7]",
        "dark:[--lms-muted:#bdcbc3]",
        "dark:[--lms-border:rgba(211,170,69,0.22)]",
        "dark:[--lms-rule:rgba(245,241,231,0.12)]",
        "dark:[--lms-accent:#d3aa45]",
        "dark:[--lms-accent-soft:rgba(211,170,69,0.18)]",
        "dark:[--lms-glow-a:rgba(211,170,69,0.18)]",
        "dark:[--lms-glow-b:rgba(26,150,103,0.22)]"
      )}
      style={{
        background:
          "linear-gradient(180deg, transparent, var(--lms-bg) 18%, var(--lms-bg) 82%, transparent)",
      }}
    >
      <motion.div
        variants={ROOT_VARIANTS}
        initial={initial}
        whileInView="visible"
        viewport={{ once: true, amount: 0.15 }}
        className="relative isolate"
        style={{ color: "var(--lms-text)" }}
      >
        {/* Ambient background glow (Phase B-5: dropped the scrub-based
            slow drift this had under GSAP — the static positioning
            still reads as ambient depth and avoids the extra scroll
            listener.) */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10"
        >
          <div
            className="absolute -left-32 top-8 h-[28rem] w-[28rem] rounded-full blur-3xl"
            style={{ background: "var(--lms-glow-b)" }}
          />
          <div
            className="absolute -right-24 bottom-0 h-[24rem] w-[24rem] rounded-full blur-3xl"
            style={{ background: "var(--lms-glow-a)" }}
          />
          <div
            className="absolute left-1/2 top-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl opacity-60"
            style={{ background: "var(--lms-accent-soft)" }}
          />
        </div>

        {/* Header */}
        <motion.div
          variants={HEADER_VARIANTS}
          className="mx-auto mb-12 max-w-2xl text-center sm:mb-16"
        >
          {data.eyebrow && (
            <span
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em]"
              style={{
                color: "var(--lms-accent)",
                borderColor: "var(--lms-border)",
                background: "var(--lms-accent-soft)",
              }}
            >
              <Sparkles className="h-3 w-3" />
              {data.eyebrow}
            </span>
          )}
          {data.title && (
            <h2
              className="mt-4 text-balance text-3xl font-semibold tracking-tight sm:text-4xl lg:text-[2.65rem]"
              style={{ color: "var(--lms-text)" }}
            >
              <HeadingAccent value={data.title} />
            </h2>
          )}
          {data.subtitle && (
            <p
              className="mt-4 text-pretty text-base sm:text-lg"
              style={{ color: "var(--lms-muted)" }}
            >
              {data.subtitle}
            </p>
          )}
        </motion.div>

        {/* Cards */}
        <div
          className={cn(
            "grid grid-cols-1 gap-10",
            !isSingle && "lg:grid-cols-2 lg:gap-10",
            isSingle && "mx-auto max-w-3xl"
          )}
        >
          {messages.map((message, idx) => (
            <motion.article
              key={message.slug}
              custom={{ fromLeft: idx % 2 === 0, isDesktop } satisfies CardCustom}
              variants={CARD_VARIANTS}
              className={cn(
                "group/lms-card relative overflow-hidden rounded-[2rem] border p-5 backdrop-blur-2xl sm:p-7 lg:p-8",
                "shadow-[0_18px_60px_-22px_rgba(15,40,32,0.30)] dark:shadow-[0_18px_60px_-22px_rgba(0,0,0,0.55)]",
                !isSingle && idx % 2 === 1 && "lg:mt-20"
              )}
              style={{
                background: "var(--lms-card-bg)",
                borderColor: "var(--lms-border)",
                willChange: "transform, opacity",
              }}
            >
              {/* Decorative inner edge stroke + corner glints */}
              <span
                aria-hidden
                className="pointer-events-none absolute inset-0 rounded-[2rem] ring-1 ring-inset"
                style={{ boxShadow: "inset 0 1px 0 0 var(--lms-card-edge)" }}
              />
              <span
                aria-hidden
                className="pointer-events-none absolute -left-10 -top-10 h-32 w-32 rounded-full blur-2xl opacity-60"
                style={{ background: "var(--lms-accent-soft)" }}
              />

              <CardBody message={message} />
            </motion.article>
          ))}
        </div>
      </motion.div>
    </Section>
  );
}


// ---------------------------------------------------------------------------
// Card body — premium two-column editorial layout.
// ---------------------------------------------------------------------------

function CardBody({ message }: { message: HomepageLeadershipCard }) {
  const photo = normaliseMediaUrl(message.photo_url ?? null);
  const signature = normaliseMediaUrl(message.signature_image_url ?? null);
  const hasMessage =
    Boolean(message.highlight_quote) ||
    Boolean(message.message_paragraph_1) ||
    Boolean(message.message_paragraph_2);

  // Each ``motion.*`` element below inherits the "visible" state from
  // its parent card the moment the card animates in, and applies the
  // delay encoded in its own variant. That re-creates the GSAP
  // ``at + 0.05 / 0.25 / 0.3 / 0.55`` offsets without a manual
  // timeline.
  return (
    <motion.div
      variants={TEXT_CONTAINER_VARIANTS}
      className="relative flex h-full flex-col gap-6 sm:gap-7 md:flex-row md:items-stretch md:gap-7 lg:gap-8"
    >
      {/* Portrait column */}
      <div className="relative mx-auto w-full max-w-[280px] shrink-0 md:mx-0 md:max-w-none md:w-[210px] lg:w-[230px]">
        <PortraitFrame
          photo={photo}
          initials={message.initials}
          accent={message.accent}
          name={message.name}
          roleType={message.role_type}
        />
      </div>

      {/* Content column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="space-y-1.5">
          {message.role_label && (
            <motion.p
              variants={TEXT_VARIANTS}
              className="text-[11px] font-semibold uppercase tracking-[0.22em]"
              style={{ color: "var(--lms-accent)" }}
            >
              {message.role_label}
            </motion.p>
          )}
          <motion.h3
            variants={TEXT_VARIANTS}
            className="text-balance text-xl font-semibold leading-tight sm:text-2xl"
            style={{ color: "var(--lms-text)" }}
          >
            {message.name}
          </motion.h3>
          <motion.p
            variants={TEXT_VARIANTS}
            className="text-sm"
            style={{ color: "var(--lms-muted)" }}
          >
            {message.designation ?? message.role}
          </motion.p>
        </header>

        {hasMessage && (
          <>
            <motion.hr
              variants={TEXT_VARIANTS}
              className="my-4 sm:my-5"
              style={{
                border: 0,
                height: 1,
                background:
                  "linear-gradient(90deg, var(--lms-accent-soft), var(--lms-rule), transparent)",
              }}
            />
            <div className="relative">
              <motion.span
                variants={QUOTE_VARIANTS}
                aria-hidden
                className="absolute -left-1 -top-2 inline-flex h-9 w-9 items-center justify-center rounded-full"
                style={{
                  background: "var(--lms-accent-soft)",
                  color: "var(--lms-accent)",
                }}
              >
                <Quote className="h-4 w-4" />
              </motion.span>
              <div className="space-y-3 pl-12 pr-1">
                {message.highlight_quote && (
                  <motion.p
                    variants={TEXT_VARIANTS}
                    className="text-pretty text-base font-medium italic leading-relaxed sm:text-[1.05rem]"
                    style={{ color: "var(--lms-text)" }}
                  >
                    “{message.highlight_quote}”
                  </motion.p>
                )}
                {message.message_paragraph_1 && (
                  <motion.p
                    variants={TEXT_VARIANTS}
                    className="text-pretty text-sm leading-relaxed sm:text-[15px]"
                    style={{ color: "var(--lms-muted)" }}
                  >
                    {message.message_paragraph_1}
                  </motion.p>
                )}
                {message.message_paragraph_2 && (
                  <motion.p
                    variants={TEXT_VARIANTS}
                    className="text-pretty text-sm leading-relaxed sm:text-[15px]"
                    style={{ color: "var(--lms-muted)" }}
                  >
                    {message.message_paragraph_2}
                  </motion.p>
                )}
              </div>
            </div>
          </>
        )}

        {/* Footer: signature + CTA, revealed last */}
        <motion.div
          variants={FOOTER_VARIANTS}
          className="mt-auto flex flex-wrap items-end justify-between gap-4 pt-6"
        >
          <div className="min-w-0">
            <p
              className="text-base font-semibold tracking-tight"
              style={{ color: "var(--lms-text)" }}
            >
              {message.name}
            </p>
            <p
              className="text-xs"
              style={{ color: "var(--lms-muted)" }}
            >
              {message.designation ?? message.role}
            </p>
          </div>

          <div className="flex items-end gap-4">
            {signature ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={signature}
                alt={`${message.name} signature`}
                className="h-12 w-auto opacity-90 mix-blend-multiply dark:mix-blend-screen dark:opacity-95"
              />
            ) : message.signature ? (
              <span
                className="font-signature text-xl"
                style={{ color: "var(--lms-accent)" }}
              >
                {message.signature}
              </span>
            ) : null}
          </div>
        </motion.div>

        {message.cta_label && message.cta_url && (
          <motion.div variants={TEXT_VARIANTS} className="mt-4">
            <Link
              href={message.cta_url}
              className="inline-flex items-center gap-1 text-sm font-semibold transition-colors hover:opacity-80"
              style={{ color: "var(--lms-accent)" }}
            >
              {message.cta_label}
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}


// ---------------------------------------------------------------------------
// Portrait frame — medium-large (180-240×220-300) per the design spec.
// ---------------------------------------------------------------------------

function PortraitFrame({
  photo,
  initials,
  accent,
  name,
  roleType,
}: {
  photo: string | null;
  initials: string;
  accent: string;
  name: string;
  roleType: string;
}) {
  return (
    <div className="relative">
      {/* Soft accent halo behind the frame */}
      <span
        aria-hidden
        className="pointer-events-none absolute -inset-3 rounded-[2.25rem] blur-2xl opacity-60"
        style={{ background: "var(--lms-glow-a)" }}
      />
      <span
        aria-hidden
        className="pointer-events-none absolute -inset-2 rounded-[2rem]"
        style={{
          background: "linear-gradient(135deg, var(--lms-accent-soft), transparent 60%)",
        }}
      />

      <div
        className={cn(
          "relative aspect-[3/4] w-full overflow-hidden rounded-[1.75rem] border",
          "h-auto",
          // Cap the height so mobile cards don't get a giant portrait.
          "max-h-[300px] sm:max-h-none"
        )}
        style={{
          borderColor: "var(--lms-border)",
          background: "var(--lms-card-bg)",
        }}
      >
        <motion.div
          variants={PHOTO_VARIANTS}
          className="absolute inset-0"
          style={{ willChange: "clip-path, transform" }}
        >
          {photo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={photo}
              alt={name}
              loading="lazy"
              className="h-full w-full object-cover object-[center_22%]"
            />
          ) : (
            <div
              className={cn(
                "flex h-full w-full items-center justify-center bg-gradient-to-br text-4xl font-bold text-white",
                accent
              )}
              aria-label={name}
            >
              {initials}
            </div>
          )}
        </motion.div>

        {/* Subtle bottom gradient over the photo for legibility of role pill */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-24"
          style={{
            background:
              "linear-gradient(180deg, transparent, rgba(15,30,24,0.55))",
          }}
        />

        {/* Role-type chip */}
        <span
          className="absolute bottom-3 left-3 inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-white backdrop-blur-md"
          style={{ background: "rgba(15,30,24,0.45)" }}
        >
          {roleType === "chairman"
            ? "Chairman"
            : roleType === "md"
              ? "Managing Director"
              : roleType.toUpperCase()}
        </span>

        {/* Hairline gold inner ring */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[1.75rem]"
          style={{ boxShadow: "inset 0 0 0 1px var(--lms-accent-soft)" }}
        />
      </div>
    </div>
  );
}
