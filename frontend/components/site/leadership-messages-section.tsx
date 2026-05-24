"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight, Quote, Sparkles } from "lucide-react";

import { Section } from "@/components/site/section";
import {
  resolveAssetUrl,
  type HomepageLeadershipCard,
  type HomepageLeadershipSection,
} from "@/lib/public-api";
import { cn } from "@/lib/utils";


interface LeadershipMessagesSectionProps {
  data: HomepageLeadershipSection;
}

/**
 * Unified homepage Leadership Messages section.
 *
 * Renders the Chairman and MD cards inside one section. Layout is a
 * split two-column grid on desktop with the second card sitting a bit
 * lower for an intentional asymmetric premium look; mobile stacks
 * vertically with no offsets.
 *
 * Animation — "Dual Leadership Reveal":
 *   - Background glow moves slowly while scrolling (scrubbed).
 *   - Header fades up first.
 *   - Cards slide in from opposite sides with soft rotation + scale.
 *   - Photos reveal with a clip-path mask animation.
 *   - Quote icons fade + rotate softly into place.
 *   - Inner text elements stagger up.
 *
 * Cleanup, prefers-reduced-motion, and SSR safety are all honoured.
 * Theme tokens are CSS variables defined inline so the section adapts
 * to light + dark with a single source of truth.
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

      const ctx = gsap.context(() => {
        // Always start hidden so first paint matches the animation.
        if (header) {
          gsap.set(header, { y: 40, opacity: 0 });
        }
        cards.forEach((card, i) => {
          const photo = card.querySelector<HTMLElement>("[data-lms-photo]");
          const quote = card.querySelector<HTMLElement>("[data-lms-quote]");
          const texts = card.querySelectorAll<HTMLElement>("[data-lms-text]");
          const fromLeft = i % 2 === 0;
          gsap.set(card, {
            x: isDesktop ? (fromLeft ? -90 : 90) : 0,
            y: isDesktop ? (fromLeft ? 40 : 80) : 40,
            rotate: isDesktop ? (fromLeft ? -2 : 2) : 0,
            scale: isDesktop ? 0.96 : 1,
            opacity: 0,
          });
          if (photo) {
            gsap.set(photo, {
              clipPath: "inset(0 0 100% 0)",
              scale: 1.08,
            });
          }
          if (quote) {
            gsap.set(quote, { opacity: 0, rotate: -10, scale: 0.75 });
          }
          if (texts.length) {
            gsap.set(texts, { y: 24, opacity: 0 });
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
          const at = 0.15 + i * 0.18;
          const photo = card.querySelector<HTMLElement>("[data-lms-photo]");
          const quote = card.querySelector<HTMLElement>("[data-lms-quote]");
          const texts = card.querySelectorAll<HTMLElement>("[data-lms-text]");

          tl.to(
            card,
            {
              x: 0,
              y: 0,
              rotate: 0,
              scale: 1,
              opacity: 1,
              duration: 1,
            },
            at
          );
          if (photo) {
            tl.to(
              photo,
              {
                clipPath: "inset(0 0 0% 0)",
                scale: 1,
                duration: 0.9,
              },
              at + 0.1
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
              at + 0.2
            );
          }
          if (texts.length) {
            tl.to(
              texts,
              {
                y: 0,
                opacity: 1,
                duration: 0.6,
                stagger: 0.08,
              },
              at + 0.3
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
      }, section);

      cleanup = () => {
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
        "[--lms-bg:#f8f5ef]",
        "[--lms-card-bg:rgba(255,255,255,0.78)]",
        "[--lms-text:#18332b]",
        "[--lms-muted:#5f6f68]",
        "[--lms-border:rgba(24,51,43,0.10)]",
        "[--lms-accent:#a3812d]",
        "[--lms-accent-soft:rgba(163,129,45,0.18)]",
        "[--lms-glow-a:rgba(163,129,45,0.18)]",
        "[--lms-glow-b:rgba(24,89,67,0.16)]",
        "dark:[--lms-bg:#07110d]",
        "dark:[--lms-card-bg:rgba(255,255,255,0.06)]",
        "dark:[--lms-text:#f5f2ea]",
        "dark:[--lms-muted:#c7d1ca]",
        "dark:[--lms-border:rgba(245,242,234,0.08)]",
        "dark:[--lms-accent:#d6b46a]",
        "dark:[--lms-accent-soft:rgba(214,180,106,0.18)]",
        "dark:[--lms-glow-a:rgba(214,180,106,0.18)]",
        "dark:[--lms-glow-b:rgba(34,143,108,0.20)]"
      )}
    >
      <div
        ref={sectionRef}
        className="relative isolate"
        style={{
          color: "var(--lms-text)",
        }}
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
              {data.title}
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
            "grid grid-cols-1 gap-8",
            !isSingle && "md:grid-cols-2 md:gap-10"
          )}
        >
          {messages.map((message, idx) => (
            <article
              key={message.slug}
              ref={(el) => {
                cardRefs.current[idx] = el;
              }}
              className={cn(
                "relative flex flex-col gap-6 rounded-[2rem] border p-6 backdrop-blur-xl shadow-[0_10px_40px_-12px_rgba(15,23,42,0.18)] sm:p-8 lg:p-10",
                !isSingle && idx % 2 === 1 && "md:mt-12 lg:mt-20"
              )}
              style={{
                background: "var(--lms-card-bg)",
                borderColor: "var(--lms-border)",
                willChange: "transform, opacity",
              }}
            >
              <CardBody message={message} />
            </article>
          ))}
        </div>
      </div>
    </Section>
  );
}


function CardBody({ message }: { message: HomepageLeadershipCard }) {
  const photo = resolveAssetUrl(message.photo_url ?? null);
  const signature = resolveAssetUrl(message.signature_image_url ?? null);
  const hasMessage =
    Boolean(message.highlight_quote) ||
    Boolean(message.message_paragraph_1) ||
    Boolean(message.message_paragraph_2);

  return (
    <>
      <div className="flex items-start gap-5">
        <PhotoFrame photo={photo} initials={message.initials} accent={message.accent} />
        <div className="min-w-0 flex-1 space-y-1.5 pt-1">
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
            className="text-balance text-lg font-semibold leading-tight sm:text-xl"
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
        </div>
      </div>

      {hasMessage && (
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
                className="text-pretty text-base font-medium leading-relaxed sm:text-lg"
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
      )}

      <div
        data-lms-text
        className="mt-auto flex flex-wrap items-end justify-between gap-4 border-t pt-5"
        style={{ borderColor: "var(--lms-border)" }}
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

      {message.cta_label && message.cta_url && (
        <div data-lms-text>
          <Link
            href={message.cta_url}
            className="inline-flex items-center gap-1 text-sm font-semibold"
            style={{ color: "var(--lms-accent)" }}
          >
            {message.cta_label}
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}
    </>
  );
}


function PhotoFrame({
  photo,
  initials,
  accent,
}: {
  photo: string | null;
  initials: string;
  accent: string;
}) {
  return (
    <div
      className="relative shrink-0 overflow-hidden rounded-2xl border"
      style={{ borderColor: "var(--lms-border)" }}
    >
      <div
        className="relative h-24 w-24 overflow-hidden sm:h-28 sm:w-28"
        data-lms-photo
        style={{ willChange: "clip-path, transform" }}
      >
        {photo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={photo}
            alt=""
            loading="lazy"
            className="h-full w-full object-cover object-[center_25%]"
          />
        ) : (
          <div
            className={cn(
              "flex h-full w-full items-center justify-center bg-gradient-to-br text-2xl font-bold text-white",
              accent
            )}
          >
            {initials}
          </div>
        )}
      </div>
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset"
        style={{ boxShadow: "inset 0 0 0 1px var(--lms-accent-soft)" }}
      />
    </div>
  );
}
