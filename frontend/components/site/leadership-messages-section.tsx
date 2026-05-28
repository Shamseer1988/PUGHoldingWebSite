"use client";

import * as React from "react";
import Link from "next/link";
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
  const sectionRef = React.useRef<HTMLDivElement | null>(null);
  const headerRef = React.useRef<HTMLDivElement | null>(null);
  const glowRef = React.useRef<HTMLDivElement | null>(null);
  const cardRefs = React.useRef<(HTMLElement | null)[]>([]);

  const messages = React.useMemo(
    () => data.messages.filter((m) => m.is_active),
    [data.messages]
  );

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    if (!data.animation_enabled) return;
    if (messages.length === 0) return;

    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (reducedMotion) return;

    const isDesktop = window.matchMedia("(min-width: 768px)").matches;

    let cleanup: (() => void) | undefined;
    let cancelled = false;

    (async () => {
      const { gsap } = await import("gsap");
      const { ScrollTrigger } = await import("gsap/ScrollTrigger");
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);

      const section = sectionRef.current;
      const header = headerRef.current;
      const glow = glowRef.current;
      const cards = cardRefs.current.filter(Boolean) as HTMLElement[];
      if (!section || cards.length === 0) return;

      // Safety net for the timeline below — see footer.tsx for
      // rationale. Large leader photos can shift the section's
      // position after ScrollTrigger has already measured it,
      // leaving the cards permanently at gsap.set's opacity:0.
      let safetyTimer: number | undefined;

      const ctx = gsap.context(() => {
        // If the section is already visible at JS-execution time
        // (e.g. hard refresh where the browser preserved scroll
        // position), skip the hide-then-reveal. The SSR HTML is
        // already rendered correctly; hiding it would cause the
        // 3-4s blank flash the user reported on Leadership / Footer.
        const rect = section.getBoundingClientRect();
        const alreadyInView =
          rect.top < window.innerHeight * 0.9 && rect.bottom > 0;
        if (alreadyInView) return;

        // Always start hidden so first paint matches the animation.
        if (header) {
          gsap.set(header, { y: 36, opacity: 0 });
        }
        cards.forEach((card, i) => {
          const photo = card.querySelector<HTMLElement>("[data-lms-photo]");
          const quote = card.querySelector<HTMLElement>("[data-lms-quote]");
          const texts = card.querySelectorAll<HTMLElement>("[data-lms-text]");
          const footer = card.querySelector<HTMLElement>("[data-lms-footer]");
          const fromLeft = i % 2 === 0;
          gsap.set(card, {
            x: isDesktop ? (fromLeft ? -90 : 90) : 0,
            y: isDesktop ? (fromLeft ? 40 : 70) : 40,
            rotate: isDesktop ? (fromLeft ? -1.5 : 1.5) : 0,
            scale: isDesktop ? 0.96 : 1,
            opacity: 0,
          });
          if (photo) {
            // Mask reveal: start with a 12% inset + slight zoom; fully
            // expand to 0% inset + natural scale.
            gsap.set(photo, {
              clipPath: "inset(12% 12% 12% 12% round 28px)",
              scale: 1.08,
            });
          }
          if (quote) {
            gsap.set(quote, { opacity: 0, rotate: -10, scale: 0.75 });
          }
          if (texts.length) {
            gsap.set(texts, { y: 24, opacity: 0 });
          }
          if (footer) {
            gsap.set(footer, { y: 18, opacity: 0 });
          }
        });

        // Reveal timeline — non-scrub, one-shot for a clean premium feel.
        const tl = gsap.timeline({
          scrollTrigger: {
            trigger: section,
            start: "top 75%",
            end: "bottom 35%",
            once: true,
          },
          defaults: { ease: "power3.out" },
        });

        if (header) {
          tl.to(header, { y: 0, opacity: 1, duration: 0.8 }, 0);
        }

        cards.forEach((card, i) => {
          const at = 0.18 + i * 0.18;
          const photo = card.querySelector<HTMLElement>("[data-lms-photo]");
          const quote = card.querySelector<HTMLElement>("[data-lms-quote]");
          const texts = card.querySelectorAll<HTMLElement>("[data-lms-text]");
          const footer = card.querySelector<HTMLElement>("[data-lms-footer]");

          tl.to(
            card,
            {
              x: 0,
              y: 0,
              rotate: 0,
              scale: 1,
              opacity: 1,
              duration: 1.05,
            },
            at
          );
          if (photo) {
            tl.to(
              photo,
              {
                clipPath: "inset(0% 0% 0% 0% round 28px)",
                scale: 1,
                duration: 1.05,
              },
              at + 0.05
            );
          }
          if (quote) {
            tl.to(
              quote,
              {
                opacity: 1,
                rotate: 0,
                scale: 1,
                duration: 0.55,
                ease: "back.out(2)",
              },
              at + 0.25
            );
          }
          if (texts.length) {
            tl.to(
              texts,
              {
                y: 0,
                opacity: 1,
                duration: 0.55,
                stagger: 0.08,
              },
              at + 0.3
            );
          }
          if (footer) {
            tl.to(
              footer,
              { y: 0, opacity: 1, duration: 0.6 },
              at + 0.55
            );
          }
        });

        // Background glow drift — separate, scrubbed for a slow parallax feel.
        if (glow) {
          gsap.to(glow, {
            xPercent: 6,
            yPercent: -4,
            ease: "none",
            scrollTrigger: {
              trigger: section,
              start: "top bottom",
              end: "bottom top",
              scrub: 0.7,
            },
          });
        }

        safetyTimer = window.setTimeout(() => {
          if (!tl.isActive() && tl.progress() === 0) {
            tl.progress(1);
          }
        }, 800);
      }, section);

      cleanup = () => {
        if (safetyTimer !== undefined) window.clearTimeout(safetyTimer);
        ctx.revert();
      };
    })();

    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [data.animation_enabled, messages.length]);

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
      <div
        ref={sectionRef}
        className="relative isolate"
        style={{ color: "var(--lms-text)" }}
      >
        {/* Ambient background glow */}
        <div
          ref={glowRef}
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
        <div
          ref={headerRef}
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
        </div>

        {/* Cards */}
        <div
          className={cn(
            "grid grid-cols-1 gap-10",
            !isSingle && "lg:grid-cols-2 lg:gap-10",
            isSingle && "mx-auto max-w-3xl"
          )}
        >
          {messages.map((message, idx) => (
            <article
              key={message.slug}
              ref={(el) => {
                cardRefs.current[idx] = el;
              }}
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
            </article>
          ))}
        </div>
      </div>
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

  return (
    <div className="relative flex h-full flex-col gap-6 sm:gap-7 md:flex-row md:items-stretch md:gap-7 lg:gap-8">
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
            <p
              data-lms-text
              className="text-[11px] font-semibold uppercase tracking-[0.22em]"
              style={{ color: "var(--lms-accent)" }}
            >
              {message.role_label}
            </p>
          )}
          <h3
            data-lms-text
            className="text-balance text-xl font-semibold leading-tight sm:text-2xl"
            style={{ color: "var(--lms-text)" }}
          >
            {message.name}
          </h3>
          <p
            data-lms-text
            className="text-sm"
            style={{ color: "var(--lms-muted)" }}
          >
            {message.designation ?? message.role}
          </p>
        </header>

        {hasMessage && (
          <>
            <hr
              data-lms-text
              className="my-4 sm:my-5"
              style={{
                border: 0,
                height: 1,
                background:
                  "linear-gradient(90deg, var(--lms-accent-soft), var(--lms-rule), transparent)",
              }}
            />
            <div className="relative">
              <span
                data-lms-quote
                aria-hidden
                className="absolute -left-1 -top-2 inline-flex h-9 w-9 items-center justify-center rounded-full"
                style={{
                  background: "var(--lms-accent-soft)",
                  color: "var(--lms-accent)",
                }}
              >
                <Quote className="h-4 w-4" />
              </span>
              <div className="space-y-3 pl-12 pr-1">
                {message.highlight_quote && (
                  <p
                    data-lms-text
                    className="text-pretty text-base font-medium italic leading-relaxed sm:text-[1.05rem]"
                    style={{ color: "var(--lms-text)" }}
                  >
                    “{message.highlight_quote}”
                  </p>
                )}
                {message.message_paragraph_1 && (
                  <p
                    data-lms-text
                    className="text-pretty text-sm leading-relaxed sm:text-[15px]"
                    style={{ color: "var(--lms-muted)" }}
                  >
                    {message.message_paragraph_1}
                  </p>
                )}
                {message.message_paragraph_2 && (
                  <p
                    data-lms-text
                    className="text-pretty text-sm leading-relaxed sm:text-[15px]"
                    style={{ color: "var(--lms-muted)" }}
                  >
                    {message.message_paragraph_2}
                  </p>
                )}
              </div>
            </div>
          </>
        )}

        {/* Footer: signature + CTA, revealed last */}
        <div
          data-lms-footer
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
        </div>

        {message.cta_label && message.cta_url && (
          <div data-lms-text className="mt-4">
            <Link
              href={message.cta_url}
              className="inline-flex items-center gap-1 text-sm font-semibold transition-colors hover:opacity-80"
              style={{ color: "var(--lms-accent)" }}
            >
              {message.cta_label}
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        )}
      </div>
    </div>
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
        <div
          data-lms-photo
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
        </div>

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
