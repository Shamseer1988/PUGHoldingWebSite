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
  /** Opt into the underline scaleX 0 -> 1 reveal animation. */
  reveal?: boolean;
  className?: string;
}

/**
 * Renders a section heading string with the closing words painted in
 * the reusable `.section-heading__accent` style (gold text + custom
 * pseudo-element underline). Use inside an `<h2>` / `<h3>` — this is
 * a span-level component so it composes with whatever heading tag
 * the surrounding section already owns.
 *
 * The space immediately before the accent is rendered as a
 * non-breaking space so the underline doesn't slip onto the wrong
 * line when the heading wraps. Trailing punctuation that admins
 * sometimes leave outside the marker (e.g. the final ".") is
 * preserved verbatim.
 */
export function HeadingAccent({ value, reveal, className }: HeadingAccentProps) {
  const { base, accent, trail } = splitHeadingAccent(value);
  if (!accent) {
    return <span className={className}>{value}</span>;
  }

  // Trim trailing whitespace off `base` so we can control the gap
  // explicitly with a non-breaking space. Without this the existing
  // " " inside the source string would be rendered as the gap and
  // could break-wrap independently from the accent run.
  const baseTrimmed = base.replace(/\s+$/, "");

  return (
    <span className={className}>
      {baseTrimmed}
      {baseTrimmed && " "}
      <span
        className={cn("section-heading__accent")}
        {...(reveal ? { "data-accent-reveal": "" } : {})}
      >
        {accent}
      </span>
      {trail}
    </span>
  );
}
