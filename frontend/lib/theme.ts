/**
 * Admin-driven theme overrides.
 *
 * Site Settings expose four optional theme fields:
 *   - theme_primary_hex   — primary brand color
 *   - theme_accent_hex    — accent / highlight color
 *   - theme_heading_font  — display / heading font family
 *   - theme_body_font     — base body font family
 *
 * The root layout injects the result of `buildThemeStyle()` onto
 * <html style={...}> so the overrides ship in the initial server HTML.
 * Setting these CSS variables overrides the Tailwind defaults defined
 * in globals.css; leaving them all unset keeps the existing palette +
 * Inter font exactly as-is.
 */
import type { CSSProperties } from "react";

import type { SiteSettings } from "@/lib/admin/types";

/**
 * Parse a hex string (#RGB, #RRGGBB, or #RRGGBBAA) into a Tailwind-style
 * "H S% L%" triple. Tailwind's tokens (`--primary`, `--accent`, etc.)
 * are written as bare HSL channel groups so they can be composed with
 * arbitrary alpha (`hsl(var(--primary) / 0.5)`). Returning the same
 * format means the override drops in cleanly.
 */
function hexToHslChannels(hex: string): string | null {
  const trimmed = hex.trim().replace(/^#/, "");
  let r: number;
  let g: number;
  let b: number;
  if (trimmed.length === 3) {
    r = parseInt(trimmed[0] + trimmed[0], 16);
    g = parseInt(trimmed[1] + trimmed[1], 16);
    b = parseInt(trimmed[2] + trimmed[2], 16);
  } else if (trimmed.length === 6 || trimmed.length === 8) {
    r = parseInt(trimmed.slice(0, 2), 16);
    g = parseInt(trimmed.slice(2, 4), 16);
    b = parseInt(trimmed.slice(4, 6), 16);
  } else {
    return null;
  }
  if ([r, g, b].some((n) => Number.isNaN(n))) return null;

  const rN = r / 255;
  const gN = g / 255;
  const bN = b / 255;
  const max = Math.max(rN, gN, bN);
  const min = Math.min(rN, gN, bN);
  const l = (max + min) / 2;

  let h = 0;
  let s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case rN:
        h = (gN - bN) / d + (gN < bN ? 6 : 0);
        break;
      case gN:
        h = (bN - rN) / d + 2;
        break;
      case bN:
        h = (rN - gN) / d + 4;
        break;
    }
    h *= 60;
  }
  return `${Math.round(h)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

/** Build the inline-style object the root layout drops on <html>.
 *  Returns `undefined` (not an empty object) when there's nothing to
 *  override so React doesn't emit a noop `style=""` attribute. */
export function buildThemeStyle(
  settings: SiteSettings | null | undefined
): CSSProperties | undefined {
  if (!settings) return undefined;
  const style: Record<string, string> = {};

  if (settings.theme_primary_hex) {
    const hsl = hexToHslChannels(settings.theme_primary_hex);
    if (hsl) style["--primary"] = hsl;
  }
  if (settings.theme_accent_hex) {
    const hsl = hexToHslChannels(settings.theme_accent_hex);
    if (hsl) style["--accent"] = hsl;
  }

  // Font families are written as plain CSS values so commas + fallbacks
  // are preserved exactly as the admin entered them. Always append the
  // system fallback stack so a typo doesn't ship a blank page.
  if (settings.theme_body_font?.trim()) {
    style["--font-sans"] =
      `${settings.theme_body_font.trim()}, system-ui, -apple-system, sans-serif`;
  }
  if (settings.theme_heading_font?.trim()) {
    style["--font-display"] =
      `${settings.theme_heading_font.trim()}, system-ui, -apple-system, sans-serif`;
  }

  if (Object.keys(style).length === 0) return undefined;
  return style as CSSProperties;
}
