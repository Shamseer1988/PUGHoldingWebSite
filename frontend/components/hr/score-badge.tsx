import { cn } from "@/lib/utils";

interface ScoreBadgeProps {
  total: number | null | undefined;
  /** When true, render a smaller pill suitable for table rows. */
  compact?: boolean;
  /** When true, append an "override" hint dot. */
  overridden?: boolean;
  className?: string;
}

/**
 * Coloured score chip used in the candidates list and detail drawer.
 *
 *   ≥ 80 → emerald (strong fit)
 *   ≥ 60 → amber (worth a look)
 *   ≥ 40 → orange (gap)
 *   else → rose (weak fit)
 *
 *   null  → "no score" muted pill
 */
export function ScoreBadge({
  total,
  compact = false,
  overridden = false,
  className,
}: ScoreBadgeProps) {
  if (total == null) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full bg-muted/60 px-2 py-0.5 text-[11px] font-medium text-muted-foreground",
          compact && "px-1.5",
          className
        )}
        title="No score yet"
      >
        —
      </span>
    );
  }

  const tone = scoreTone(total);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold tabular-nums",
        tone,
        compact ? "px-1.5" : "px-2.5 py-1 text-xs",
        className
      )}
      aria-label={`Score ${total} out of 100${overridden ? " (manual override)" : ""}`}
    >
      <span>{total}</span>
      <span className="text-[10px] opacity-70">/100</span>
      {overridden && (
        <span
          aria-hidden
          title="Manual override"
          className="ml-0.5 inline-block h-1.5 w-1.5 rounded-full bg-current"
        />
      )}
    </span>
  );
}

function scoreTone(total: number): string {
  if (total >= 80) {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  }
  if (total >= 60) {
    return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
  }
  if (total >= 40) {
    return "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300";
  }
  return "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300";
}
