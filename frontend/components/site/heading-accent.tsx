import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Splits a heading string at the FIRST `((accent))` marker.
 *
 * The convention is "Three pillars, ((one group))" — everything
 * before the first `((` is the base text and the text inside `(( ))`
 * becomes the gold-accented closing phrase. Anything after the
 * closing `))` is treated as plain trailing text (rare in practice).
 *
 * Callers can omit the markers entirely; the helper just returns
 * `{ base: input, accent: "" }` and the heading renders as a plain
 * string. That keeps backwards-compat for admin-typed titles that
 * predate the convention.
 */
export function splitHeadingAccent(input: string): {
  base: string;
  accent: string;
  trail: string;
} {
  if (!input) return { base: "", accent: "", trail: "" };
  const match = input.match(/^(.*?)\(\((.+?)\)\)(.*)$/s);
  if (!match) return { base: input, accent: "", trail: "" };
  const [, base, accent, trail] = match;
  return { base, accent, trail: trail ?? "" };
}

interface HeadingAccentProps {
  /**
   * Heading source string with an optional `((accent))` marker around
   * the closing phrase that should render in the premium gold accent
   * style. The marker characters are stripped from the rendered DOM.
   *
   * Example:
   *   <HeadingAccent value="Three pillars, ((one group))" />
   *
   * Renders:
   *   "Three pillars, <span class=section-heading__accent>one group</span>"
   */
  value: string;
  className?: string;
}

/**
 * Renders a section heading string with the closing words painted in
 * the reusable `.section-heading__accent` style — the same animated
 * gradient-shifting gold treatment the hero uses on
 * "Paris United Group". Use inside an `<h2>` / `<h3>` — this is a
 * span-level component so it composes with whatever heading tag the
 * surrounding section already owns.
 *
 * The accent renders as inline text (no `inline-block`, no reserved
 * padding) so it sits on the exact baseline of the surrounding
 * heading and wraps naturally.
 */
export function HeadingAccent({ value, className }: HeadingAccentProps) {
  const { base, accent, trail } = splitHeadingAccent(value);
  if (!accent) {
    return <span className={className}>{value}</span>;
  }
  return (
    <span className={className}>
      {base}
      <span className={cn("section-heading__accent")}>{accent}</span>
      {trail}
    </span>
  );
}
