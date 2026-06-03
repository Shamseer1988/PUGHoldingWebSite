"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { GripVertical } from "lucide-react";

import { ScoreBadge } from "@/components/hr/score-badge";
import { Select } from "@/components/ui/select";
import { hrApi, HrApiError } from "@/lib/hr/api";
import { useHrDataBump } from "@/lib/hr/data-sync";
import { cn } from "@/lib/utils";

/**
 * Pipeline kanban board (acceptance criterion 4).
 *
 * Six lanes (Sourced → Joined), each backed by a set of application
 * statuses. Cards drag between lanes via framer-motion's ``drag`` gesture
 * (no new DnD library — framer-motion's own ``Reorder`` is single-list,
 * so cross-lane movement uses the lower-level drag + drop-zone hit-test).
 * Dropping — or using the keyboard-accessible "Move…" control — calls the
 * shared status-transition endpoint with the lane's entry status; the
 * backend rejects illegal transitions, so the board never invents a move
 * the workflow disallows.
 */

export interface PipelineLane {
  key: string;
  label: string;
  statuses: string[];
  /** Status applied when a card is dropped into this lane. */
  target: string;
}

export const PIPELINE_LANES: PipelineLane[] = [
  {
    key: "sourced",
    label: "Sourced",
    statuses: ["cv_received", "ai_reviewed"],
    target: "cv_received",
  },
  {
    key: "screening",
    label: "Screening",
    statuses: ["hr_review_pending", "shortlisted"],
    target: "shortlisted",
  },
  {
    key: "interview",
    label: "Interview",
    statuses: ["first_interview", "technical_interview", "final_interview"],
    target: "first_interview",
  },
  {
    key: "selected",
    label: "Selected",
    statuses: ["recommended_for_offer", "selected"],
    target: "selected",
  },
  { key: "offer", label: "Offer", statuses: ["offer_sent"], target: "offer_sent" },
  { key: "joined", label: "Joined", statuses: ["joined"], target: "joined" },
];

/** Lane a status belongs to, or null for side-lane statuses
 *  (waiting_list / rejected / blacklisted / not_joined) which the board
 *  intentionally omits. */
export function laneForStatus(status: string): string | null {
  return PIPELINE_LANES.find((l) => l.statuses.includes(status))?.key ?? null;
}

export interface PipelineCard {
  candidateId: number;
  applicationId: number;
  name: string;
  subtitle?: string | null;
  status: string;
  score: number | null;
  hasPendingReview?: boolean;
}

interface PipelineBoardProps {
  cards: PipelineCard[];
  onMoved: () => void;
  onError?: (message: string) => void;
}

export function PipelineBoard({ cards, onMoved, onError }: PipelineBoardProps) {
  const laneRefs = React.useRef<Record<string, HTMLDivElement | null>>({});
  const [busyId, setBusyId] = React.useState<number | null>(null);
  const bump = useHrDataBump();

  const byLane = React.useMemo(() => {
    const map: Record<string, PipelineCard[]> = {};
    for (const lane of PIPELINE_LANES) map[lane.key] = [];
    for (const card of cards) {
      const lane = laneForStatus(card.status);
      if (lane) map[lane].push(card);
    }
    return map;
  }, [cards]);

  const moveCard = React.useCallback(
    async (card: PipelineCard, laneKey: string) => {
      const lane = PIPELINE_LANES.find((l) => l.key === laneKey);
      if (!lane) return;
      if (laneForStatus(card.status) === laneKey) return; // already here
      setBusyId(card.applicationId);
      try {
        await hrApi.post(
          `/hr/candidates/${card.candidateId}/applications/${card.applicationId}/status`,
          { new_status: lane.target },
        );
        onMoved();
        bump();
      } catch (err) {
        onError?.((err as HrApiError).message);
      } finally {
        setBusyId(null);
      }
    },
    [onMoved, onError, bump],
  );

  function handleDragEnd(card: PipelineCard, point: { x: number; y: number }) {
    for (const lane of PIPELINE_LANES) {
      const el = laneRefs.current[lane.key];
      if (!el) continue;
      const r = el.getBoundingClientRect();
      if (
        point.x >= r.left &&
        point.x <= r.right &&
        point.y >= r.top &&
        point.y <= r.bottom
      ) {
        void moveCard(card, lane.key);
        return;
      }
    }
  }

  return (
    <div className="flex gap-3 overflow-x-auto pb-3">
      {PIPELINE_LANES.map((lane) => (
        <div
          key={lane.key}
          ref={(el) => {
            laneRefs.current[lane.key] = el;
          }}
          className="flex w-64 shrink-0 flex-col rounded-xl border border-border/60 bg-muted/30"
        >
          <header className="flex items-center justify-between gap-2 border-b border-border/60 px-3 py-2">
            <span className="text-sm font-semibold">{lane.label}</span>
            <span className="rounded-full bg-background px-2 py-0.5 text-[11px] tabular-nums text-muted-foreground">
              {byLane[lane.key].length}
            </span>
          </header>
          <div className="flex min-h-[6rem] flex-1 flex-col gap-2 p-2">
            {byLane[lane.key].map((card) => (
              <motion.div
                key={card.applicationId}
                layout
                drag
                dragSnapToOrigin
                whileDrag={{ scale: 1.03, zIndex: 50, cursor: "grabbing" }}
                onDragEnd={(_e, info) => handleDragEnd(card, info.point)}
                className={cn(
                  "rounded-lg border border-border/60 bg-card p-2.5 shadow-sm",
                  busyId === card.applicationId && "opacity-50",
                )}
              >
                <div className="flex items-start gap-1.5">
                  <GripVertical className="mt-0.5 h-3.5 w-3.5 shrink-0 cursor-grab text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium leading-tight">
                      {card.name}
                    </p>
                    {card.subtitle && (
                      <p className="truncate text-[11px] text-muted-foreground">
                        {card.subtitle}
                      </p>
                    )}
                  </div>
                  {card.hasPendingReview && (
                    <span
                      title="Assessment awaiting review"
                      aria-label="Assessment awaiting review"
                      className="shrink-0 rounded-full border border-amber-500/30 bg-amber-500/10 px-1.5 text-[10px] font-semibold text-amber-700 dark:text-amber-300"
                    >
                      ?
                    </span>
                  )}
                </div>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <ScoreBadge total={card.score} compact />
                  <Select
                    aria-label={`Move ${card.name}`}
                    value=""
                    disabled={busyId === card.applicationId}
                    onChange={(e) => {
                      if (e.target.value) void moveCard(card, e.target.value);
                    }}
                    className="h-7 w-24 py-0 text-[11px]"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <option value="">Move…</option>
                    {PIPELINE_LANES.filter((l) => l.key !== lane.key).map((l) => (
                      <option key={l.key} value={l.key}>
                        {l.label}
                      </option>
                    ))}
                  </Select>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
